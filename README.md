# VCloud: Video Surveillance as a Service

![Status](https://img.shields.io/badge/Status-Production_Ready-brightgreen.svg)
![React Native](https://img.shields.io/badge/React_Native-Expo_SDK_54-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)
![FFmpeg](https://img.shields.io/badge/FFmpeg-HLS_Encoding-orange.svg)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-lightgreen.svg)
![MinIO](https://img.shields.io/badge/MinIO-S3_Compatible-red.svg)

VCloud is a cloud-native, **offline-first** Video Surveillance system. It bridges local RTSP cameras to a cloud storage layer using a Python Bridge powered by FFmpeg, providing real-time HLS live streaming and continuous daily archive playback through a premium React Native mobile application.

Designed to survive real-world network instability — if the internet drops at a shop, VCloud caches footage locally and automatically syncs everything the moment connectivity is restored.

---

## Architecture

```
+------------------+      RTSP       +------------------+
|   RTSP Camera    | --------------> |  Python Bridge   |
+------------------+                 +--------+---------+
                                              |
                    +-------------------------+-------------------------+
                    |                                                   |
             HLS Live (2s)                                   60s TS Archive Chunks
                    |                                                   |
                    v                                                   v
          +-------------------+                              +-------------------+
          |   MinIO S3 Bucket  |                              |   MinIO S3 Bucket  |
          |  /live/index.m3u8  |                              |  /2026/05/31/*.ts  |
          +-------------------+                              +-------------------+
                                                                        |
                                                             +-------------------+
                                                             | Supabase (Postgres)|
                                                             | camera_recordings  |
                                                             +-------------------+
                    +------------------+--------------------+
                                       |
                              +------------------+
                              | React Native App |
                              |  - Live Feed     |
                              |  - Daily Archive |
                              +------------------+
```

---

## Key Features

### 1. Offline-First Resilient Queue
The most critical feature for real-world deployments where shop Wi-Fi is unreliable.

- A dedicated background **UploadWorker** thread manages a `queue.Queue` of pending video chunks.
- If an upload fails (network drop), the worker sleeps briefly and retries the **same chunk** indefinitely — zero data loss.
- The Boto3 connection timeout is reduced to **5 seconds** so network failures are detected instantly.
- On startup, any leftover chunks from a previous crash are automatically re-enqueued.

### 2. Dual-Pipeline FFmpeg Encoding
One FFmpeg process simultaneously produces two outputs:
- **Live HLS Stream**: 2-second segments in a rolling 5-segment playlist for ~10s latency live viewing.
- **60-second Archive Chunks**: Full-quality `.ts` segments timestamped by filename for long-term storage.

### 3. Smart Live Feed Recovery
During a network outage, live HLS segments are intentionally **dropped** (not queued). When connectivity returns, the live feed instantly jumps to **now** rather than playing stale delayed footage.

### 4. Premium Mobile Interface
- **Daily Cards**: Groups archive chunks by day and stitches them into seamless continuous playback.
- **Live View**: One-tap live streaming from the MinIO HLS endpoint.
- Dark-mode premium UI built with React Native and Expo SDK 54.

### 5. Automated Resilience Tests
Includes a self-contained test (`bridge/test_offline.py`) that simulates network failures and verifies queue behaviour without a real network.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Video Encoding | FFmpeg (HLS + MPEG-TS segment muxer) |
| Bridge Language | Python 3.10+ |
| Object Storage | MinIO (S3-compatible, self-hosted) |
| Database | Supabase (PostgreSQL + RLS) |
| Mobile App | React Native + Expo SDK 54 |
| File Watching | Python `watchdog` library |
| S3 Client | `boto3` with custom timeout config |
| Containerization | Docker Compose |

---

## Project Structure

```
VCloud/
├── bridge/                  # Python recording & upload bridge
│   ├── bridge.py            # Main bridge with FFmpeg + upload queue
│   ├── test_offline.py      # Automated resilience test suite
│   ├── requirements.txt
│   └── .env.template
├── mobile/                  # React Native Expo mobile app
│   ├── App.js
│   ├── src/
│   │   ├── screens/
│   │   │   ├── RecordingsScreen.js
│   │   │   └── VideoPlayerScreen.js
│   │   ├── components/
│   │   │   └── RecordingCard.js
│   │   └── lib/
│   │       └── supabase.js
│   ├── package.json
│   └── .env.template
├── docker/
│   └── docker-compose.yml   # MinIO + auto-bucket-init
├── database/
│   └── schema.sql           # Supabase schema with RLS
├── LICENSE
└── README.md
```

---

## Setup & Installation

> **Security Note**: All credentials are loaded from `.env` files excluded from version control. Never commit a `.env` file.

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- FFmpeg (available on PATH)
- Docker Desktop
- A Supabase project (free tier works)

### 1. Storage — MinIO via Docker
```bash
cd docker
docker compose up -d
```
MinIO Console: http://localhost:9001 (user: `minioadmin`, pass: `minioadmin`)
The `vsaas-storage` bucket is created automatically.

### 2. Database — Supabase
1. Go to your Supabase project SQL Editor.
2. Paste the contents of `database/schema.sql` and run it.

### 3. Python Bridge
```bash
cd bridge
pip install -r requirements.txt
cp .env.template .env
# Edit .env with your credentials
python bridge.py
```

To simulate a camera with a local video file, set in `.env`:
```
SIMULATE_WITH_FILE=C:/path/to/your/video.mp4
```

### 4. Mobile App
```bash
cd mobile
npm install
cp .env.template .env
# Edit .env with your Supabase credentials and MinIO IP
npx expo start
```
Scan the QR code with the **Expo Go** app on Android or iOS.

---

## Testing Offline Resilience

```bash
cd bridge
python test_offline.py
```

Expected output:
```
[MOCK S3] [NETWORK DOWN] (Attempt 1) Rejecting...
[MOCK S3] [NETWORK DOWN] (Attempt 2) Rejecting...
[MOCK S3] [NETWORK DOWN] (Attempt 3) Rejecting...
[MOCK S3] [NETWORK RESTORED] Successfully uploaded...

[PASS] Chunk uploaded successfully after network restoration.
[PASS] Local file deleted only after successful upload.
```

---

## License & Copyright

Copyright (c) 2026 KT. All Rights Reserved.

This project is proprietary software. No part of this project may be copied, modified, distributed, or used without explicit written permission from the copyright owner.
