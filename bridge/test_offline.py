"""
VCloud Offline Resilience Test
==============================
Simulates a network outage and validates the upload queue behaviour.

Test scenario:
  1. Create a dummy .ts chunk (simulating FFmpeg output).
  2. Block all uploads for the first 3 attempts (network down).
  3. Allow upload on attempt 4 (network restored).
  4. Assert chunk is uploaded and local file is cleaned up.

Run: python test_offline.py
"""
import time
from pathlib import Path

from bridge import ChunkUploader, UploadWorker, upload_queue, Cfg


class MockSupabase:
    def table(self, _): return self
    def insert(self, _): return self
    def execute(self): pass


class MockS3Client:
    def __init__(self):
        self.attempts = 0
        self.successful_uploads = []

    def upload_file(self, Filename, Bucket, Key, ExtraArgs=None):
        self.attempts += 1
        if self.attempts <= 3:
            print(f"[MOCK S3] [NETWORK DOWN] Attempt {self.attempts}: rejecting {Filename}")
            raise Exception("Connect timeout")
        print(f"[MOCK S3] [NETWORK RESTORED] Uploaded: {Filename}")
        self.successful_uploads.append(Filename)


def run_test() -> bool:
    print("=" * 50)
    print("AGENTIC TEST: Offline Resilient Queue")
    print("=" * 50)

    Cfg.shop_id = "test-shop"
    Cfg.camera_name = "test-cam"
    Cfg.segment_duration = 60
    Cfg.temp_dir = Path("./test_temp")
    Cfg.minio_bucket = "test-bucket"
    Cfg.minio_endpoint = "http://localhost:9000"
    Cfg.minio_use_ssl = False
    Cfg.temp_dir.mkdir(exist_ok=True)

    dummy = Cfg.temp_dir / "chunk_20260525_120000.ts"
    dummy.write_text("fake video data")
    print(f"[SETUP] Created dummy chunk: {dummy.name}")

    mock_s3 = MockS3Client()
    uploader = ChunkUploader(mock_s3, MockSupabase())
    worker = UploadWorker(uploader)

    # Speed up: patch sleep to 0.5s so the test finishes quickly
    import time as _time
    import bridge
    _orig = _time.sleep
    bridge.time.sleep = lambda s: _orig(0.5)

    worker.start()
    print("[QUEUE] Enqueuing chunk (network is DOWN) ...")
    upload_queue.put(dummy)
    print("[WAIT]  Processing ...")
    upload_queue.join()

    print()
    print("=" * 50)
    print("RESULTS")
    print("=" * 50)
    passed = True

    if len(mock_s3.successful_uploads) == 1:
        print("[PASS] Chunk uploaded after network restoration.")
    else:
        print("[FAIL] Chunk was lost or not uploaded.")
        passed = False

    if not dummy.exists():
        print("[PASS] Local file deleted only after successful upload.")
    else:
        print("[FAIL] Local file was not cleaned up.")
        passed = False

    print("=" * 50)
    return passed


if __name__ == "__main__":
    raise SystemExit(0 if run_test() else 1)
