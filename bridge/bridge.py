"""
VCloud Bridge
=============
Records from RTSP (or a local simulation file), segments into 60-second
MPEG-TS archive chunks AND a rolling HLS live playlist, then uploads
both to MinIO with an offline-first resilient queue.

Resilience guarantees:
  - UploadWorker retries failed chunks indefinitely (no data loss).
  - Boto3 connect timeout = 5s for fast failure detection.
  - Leftover chunks from previous crashes are re-enqueued on startup.
  - Live feed drops frames during outages so it instantly catches up on recovery.

Usage:
  cp .env.template .env   # fill in your values
  pip install -r requirements.txt
  python bridge.py
"""

import os
import sys
import time
import signal
import logging
import subprocess
import threading
import queue
from pathlib import Path
from datetime import datetime, timezone, timedelta

import boto3
from botocore.client import Config
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from supabase import create_client
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("vcloud-bridge")


class Cfg:
    """Runtime configuration loaded from .env."""
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_use_ssl: bool
    supabase_url: str
    supabase_key: str
    rtsp_url: str
    simulate_with_file: str
    shop_id: str
    camera_name: str
    segment_duration: int
    temp_dir: Path

    @classmethod
    def load(cls):
        cls.minio_endpoint    = os.environ["MINIO_ENDPOINT"]
        cls.minio_access_key  = os.environ["MINIO_ACCESS_KEY"]
        cls.minio_secret_key  = os.environ["MINIO_SECRET_KEY"]
        cls.minio_bucket      = os.environ.get("MINIO_BUCKET", "vsaas-storage")
        cls.minio_use_ssl     = os.environ.get("MINIO_USE_SSL", "false").lower() == "true"
        cls.supabase_url      = os.environ["SUPABASE_URL"]
        cls.supabase_key      = os.environ["SUPABASE_KEY"]
        cls.rtsp_url          = os.environ.get("RTSP_URL", "rtsp://rtsp.stream/pattern")
        cls.simulate_with_file = os.environ.get("SIMULATE_WITH_FILE", "").strip()
        cls.shop_id           = os.environ.get("SHOP_ID", "00000000-0000-0000-0000-000000000001")
        cls.camera_name       = os.environ.get("CAMERA_NAME", "cam-01")
        cls.segment_duration  = int(os.environ.get("SEGMENT_DURATION", "60"))
        cls.temp_dir          = Path(os.environ.get("TEMP_DIR", "./temp"))


class FFmpegRecorder:
    """Spawns FFmpeg to simultaneously produce live HLS and 60s archive segments."""

    def __init__(self):
        self._process = None
        self._stopped = threading.Event()

    def start(self):
        output_pattern = str(Cfg.temp_dir / "chunk_%Y%m%d_%H%M%S.ts")
        cmd = self._build_command(output_pattern)
        log.info("Starting FFmpeg ...")
        self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log.info("FFmpeg PID %d is recording.", self._process.pid)
        threading.Thread(target=self._drain_stderr, daemon=True, name="ffmpeg-stderr").start()

    def stop(self):
        self._stopped.set()
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _build_command(self, output_pattern: str) -> list:
        cmd = ["ffmpeg", "-y"]
        if Cfg.simulate_with_file:
            log.info("Simulating RTSP with: %s", Cfg.simulate_with_file)
            cmd += ["-stream_loop", "-1", "-re", "-i", Cfg.simulate_with_file]
        else:
            cmd += ["-rtsp_transport", "tcp", "-i", Cfg.rtsp_url]

        live_dir = Cfg.temp_dir / "live"
        live_dir.mkdir(parents=True, exist_ok=True)

        # Output 1: rolling HLS for live viewing
        cmd += [
            "-c:v", "copy", "-c:a", "copy",
            "-f", "hls", "-hls_time", "2", "-hls_list_size", "5",
            "-hls_flags", "delete_segments",
            "-hls_segment_filename", str(live_dir / "live_%03d.ts"),
            str(live_dir / "index.m3u8"),
        ]
        # Output 2: 60-second archive segments
        cmd += [
            "-c:v", "copy", "-c:a", "copy",
            "-f", "segment", "-segment_time", str(Cfg.segment_duration),
            "-segment_format", "mpegts", "-reset_timestamps", "1",
            "-strftime", "1", output_pattern,
        ]
        return cmd

    def _drain_stderr(self):
        for raw in self._process.stderr:
            if self._stopped.is_set():
                break
            log.debug("ffmpeg: %s", raw.decode("utf-8", errors="replace").rstrip())


# Global upload queue
upload_queue = queue.Queue()


class UploadWorker(threading.Thread):
    """Single background thread that drains the upload queue.
    Retries failed uploads indefinitely with a 10s pause between attempts.
    """

    def __init__(self, uploader):
        super().__init__(daemon=True, name="upload-worker")
        self.uploader = uploader

    def run(self):
        log.info("Upload Worker started.")
        while True:
            filepath = upload_queue.get()
            while True:
                if self.uploader._upload_chunk(filepath):
                    break
                log.warning("Network issue. Retrying %s in 10s...", filepath.name)
                time.sleep(10)
            upload_queue.task_done()


class ChunkUploader(FileSystemEventHandler):
    """Watchdog handler: enqueues the previous (complete) chunk when a new one is created."""

    def __init__(self, s3, sb):
        super().__init__()
        self._s3 = s3
        self._sb = sb
        self._prev = None
        self._lock = threading.Lock()

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() != ".ts":
            return
        log.info("New chunk: %s", path.name)
        with self._lock:
            if self._prev:
                upload_queue.put(self._prev)
            self._prev = path

    def flush_last_chunk(self):
        with self._lock:
            if self._prev and self._prev.exists():
                time.sleep(2)
                upload_queue.put(self._prev)
                self._prev = None

    def _upload_chunk(self, filepath: Path) -> bool:
        time.sleep(2)  # let Windows release the file handle
        if not filepath.exists():
            return True

        try:
            ts_str = filepath.stem.replace("chunk_", "")
            start = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            log.error("Bad filename, skipping: %s", filepath.name)
            return True

        end = start + timedelta(seconds=Cfg.segment_duration)
        s3_key = f"{Cfg.shop_id}/{Cfg.camera_name}/{start.strftime('%Y/%m/%d')}/{filepath.name}"

        try:
            log.info("Uploading %s ...", filepath.name)
            self._s3.upload_file(str(filepath), Cfg.minio_bucket, s3_key,
                                 ExtraArgs={"ContentType": "video/MP2T"})

            if Cfg.minio_endpoint.startswith(("http://", "https://")):
                url = f"{Cfg.minio_endpoint}/{Cfg.minio_bucket}/{s3_key}"
            else:
                proto = "https" if Cfg.minio_use_ssl else "http"
                url = f"{proto}://{Cfg.minio_endpoint}/{Cfg.minio_bucket}/{s3_key}"

            self._sb.table("camera_recordings").insert({
                "shop_id": Cfg.shop_id,
                "camera_name": Cfg.camera_name,
                "s3_video_url": url,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }).execute()

            size = filepath.stat().st_size
            filepath.unlink()
            log.info("Done: %s (%d bytes)", filepath.name, size)
            return True
        except Exception as exc:
            log.error("Upload failed for %s: %s", filepath.name, exc)
            return False


class LiveSyncHandler(FileSystemEventHandler):
    """Uploads HLS live segments to MinIO; silently drops errors during outages."""

    def __init__(self, s3):
        super().__init__()
        self._s3 = s3

    def on_any_event(self, event):
        if event.is_directory:
            return
        path = Path(getattr(event, "dest_path", event.src_path))
        if path.suffix.lower() not in (".m3u8", ".ts"):
            return
        s3_key = f"{Cfg.shop_id}/{Cfg.camera_name}/live/{path.name}"
        ct = "application/vnd.apple.mpegurl" if path.suffix == ".m3u8" else "video/MP2T"
        extra = {"ContentType": ct}
        if path.suffix == ".m3u8":
            extra["CacheControl"] = "no-cache, no-store, must-revalidate"
        try:
            self._s3.upload_file(str(path), Cfg.minio_bucket, s3_key, ExtraArgs=extra)
        except Exception:
            pass


def upload_leftovers():
    leftovers = sorted(Cfg.temp_dir.glob("chunk_*.ts"))
    if leftovers:
        log.info("Enqueueing %d leftover chunk(s) from previous run.", len(leftovers))
        for c in leftovers:
            upload_queue.put(c)


def ensure_bucket(s3):
    try:
        s3.head_bucket(Bucket=Cfg.minio_bucket)
    except Exception:
        s3.create_bucket(Bucket=Cfg.minio_bucket)
        log.info("Bucket '%s' created.", Cfg.minio_bucket)


def main():
    # Windows: add WinGet FFmpeg to PATH if present
    winget_bin = os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
        r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        r"\ffmpeg-8.1.1-full_build\bin"
    )
    if os.path.isdir(winget_bin):
        os.environ["PATH"] = winget_bin + os.pathsep + os.environ.get("PATH", "")

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        log.error(".env not found. Copy .env.template -> .env and fill in values.")
        sys.exit(1)
    load_dotenv(env_path)
    Cfg.load()

    log.info("=" * 55)
    log.info("  VCloud Bridge - Starting")
    log.info("  MinIO  : %s", Cfg.minio_endpoint)
    log.info("  Camera : %s / shop %s", Cfg.camera_name, Cfg.shop_id)
    log.info("=" * 55)

    Cfg.temp_dir.mkdir(parents=True, exist_ok=True)

    ep = Cfg.minio_endpoint
    if not ep.startswith(("http://", "https://")):
        ep = f"{'https' if Cfg.minio_use_ssl else 'http'}://{ep}"

    s3 = boto3.client(
        "s3", endpoint_url=ep,
        aws_access_key_id=Cfg.minio_access_key,
        aws_secret_access_key=Cfg.minio_secret_key,
        config=Config(signature_version="s3v4", connect_timeout=5,
                      read_timeout=10, retries={"max_attempts": 1}),
        region_name="us-east-1",
    )
    ensure_bucket(s3)

    sb = create_client(Cfg.supabase_url, Cfg.supabase_key)
    log.info("Supabase connected.")

    upload_leftovers()

    uploader = ChunkUploader(s3, sb)
    UploadWorker(uploader).start()

    recorder = FFmpegRecorder()
    recorder.start()

    observer = Observer()
    observer.schedule(uploader, str(Cfg.temp_dir), recursive=False)
    live_dir = Cfg.temp_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    observer.schedule(LiveSyncHandler(s3), str(live_dir), recursive=False)
    observer.start()
    log.info("Watching %s for new chunks.", Cfg.temp_dir.resolve())

    stop = threading.Event()

    def _sig(signum, _):
        log.info("Signal %s received — shutting down.", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    log.info("Bridge running. Press Ctrl+C to stop.")
    try:
        while not stop.is_set():
            if not recorder.is_running:
                log.error("FFmpeg died! Restarting in 5s ...")
                time.sleep(5)
                recorder.start()
            stop.wait(timeout=5)
    except KeyboardInterrupt:
        pass

    recorder.stop()
    observer.stop()
    observer.join(timeout=5)
    uploader.flush_last_chunk()
    log.info("VCloud Bridge stopped.")


if __name__ == "__main__":
    main()
