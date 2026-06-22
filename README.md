# Identity Gate 🔐
### Automated Biometric Vehicle Theft Prevention System

A real-time face recognition system that controls physical gate access using deep learning, with remote approval via an installable Android PWA and Arduino-based servo gate control.

---
### These are just the Script files, if you want to run the whole system without any hassle kindly download from the drive link:https://drive.google.com/drive/folders/1Vq1sykqmeJdYUm8tlvz3aYzORjgTmsw9?usp=sharing

## I did take help of Claude for understanding the code (you'll realise it when you'll see those comments) but most of the debugging and functions were fixed and created by me (so NO this is not AI slop 😛)

## What it does

- Detects a driver's face using a webcam in real time
- Recognizes whether the person is authorized using FaceNet embeddings
- **Authorized** → gate opens automatically via Arduino servo motor
- **Unauthorized** → captures a full-frame photo and sends an instant push notification to the owner's Android phone
- Owner can **Approve or Deny** access remotely from anywhere in the world
- Whitelist management — add or remove authorized persons via CLI or directly from the PWA

---

## System Architecture

```
Webcam → YOLOv8 (detect face every frame)
              ↓
         DeepFace/FaceNet (recognize every 30 frames, background thread)
              ↓
    ┌─────────────────────┐
    │    Whitelist match   │
    └─────────────────────┘
         ↙              ↘
  AUTHORIZED          UNAUTHORIZED
      ↓                    ↓
  Gate opens          Save snapshot
  (automatic)         Send push notification
  Arduino servo       → Owner's Android PWA
  0° → 90°           → Approve / Deny
                      → Arduino gate reacts
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Face detection | YOLOv8n-face (Ultralytics) |
| Face recognition | DeepFace + FaceNet (Inception ResNet V1) |
| Camera | OpenCV (`cv2.VideoCapture`) |
| Backend | Flask (REST API + PWA server) |
| Push notifications | Web Push API + VAPID keys (`pywebpush`) |
| Public URL | ngrok (`pyngrok`) |
| Frontend | Progressive Web App (installable on Android) |
| Hardware | Arduino Uno + SG90 Servo Motor |
| Serial communication | pyserial |
| Whitelist storage | NumPy `.npy` embedding files + JSON metadata |
| Language | Python 3.11 |

---

## Hardware Requirements

- USB webcam
- Arduino Uno
- SG90 Servo Motor
- 3 jumper wires
- USB-A to USB-B cable (Arduino to PC)
- Android phone (for PWA)

### Servo wiring

| Servo wire | Arduino pin |
|---|---|
| Brown / Black | GND |
| Red | 5V |
| Orange / Yellow | Pin 9 |

---

## Project Structure

```
identity_gate/
├── venv/                          ← Python virtual environment
└── phase1_recognition/
    ├── whitelist/                 ← authorized face photos (.jpg/.png)
    ├── embeddings/                ← face embedding files (.npy)
    ├── snapshots/                 ← intruder full-frame photos (auto-created)
    ├── static/
    │   ├── manifest.json          ← PWA manifest (installability)
    │   ├── sw.js                  ← Service worker (push notifications)
    │   ├── app.js                 ← PWA logic (alerts, whitelist, polling)
    │   ├── style.css              ← Dark theme UI
    │   └── icon-192.png           ← PWA app icon (192×192)
    ├── templates/
    │   └── index.html             ← PWA shell (alerts + whitelist tabs)
    ├── app.py                     ← Flask server + all API routes
    ├── realtime_pipeline.py       ← Main camera + recognition loop
    ├── whitelist_manager.py       ← CLI whitelist management
    ├── build_whitelist.py         ← Encode face photos to embeddings
    ├── gate_controller.py         ← Arduino serial communication
    ├── run_system.py              ← Master launcher (starts everything)
    ├── generate_vapid.py          ← VAPID key generator (run once)
    ├── vapid_private.pem          ← VAPID private key (auto-generated)
    ├── vapid_public.pem           ← VAPID public key (auto-generated)
    ├── subscriptions.json         ← PWA push subscriptions (auto-created)
    ├── whitelist_db.json          ← Whitelist metadata (auto-created)
    └── public_url.txt             ← Current ngrok URL (auto-created)
```

---

## Installation

### Prerequisites

- Python 3.11 (required — TensorFlow does not support 3.12+ yet)
- Arduino IDE
- ngrok account (free) — https://ngrok.com

## DIY 🥀

## Running the System

```bash
cd identity_gate
venv\Scripts\activate      # Windows
# source venv/bin/activate # Mac/Linux

cd phase1_recognition
python run_system.py
```

### Expected startup output

```
╔══════════════════════════════════════════╗
║       IDENTITY GATE — Starting up        ║
╚══════════════════════════════════════════╝

==================================================
  PWA URL : https://biauricular-suspectless-annie.ngrok-free.dev/
  Open on Android → Install → Enable notifications
==================================================

[+] Arduino connected on COM4
[*] Whitelist loaded: ['apurv_badhe']
[*] Starting real-time pipeline. Press Q to quit.
```

---

## Installing the PWA on Android

1. Open Chrome on your Android phone
2. Navigate to the ngrok URL shown in the terminal
3. Tap the **three-dot menu → Add to Home Screen**
4. Tap **Add**
5. Open the installed app
6. Tap **Enable notifications** and allow

Your phone is now linked to receive unauthorized access alerts.

---

## PWA Features

| Tab | Description |
|---|---|
| **Alerts** | Shows intruder photo + Approve/Deny buttons when unauthorized access is detected |
| **Whitelist** | Add new authorized persons by uploading a photo directly from your phone |

---

## System Configuration

All key parameters are at the top of `realtime_pipeline.py`:

```python
THRESHOLD        = 10.0   # Euclidean distance for face match (lower = stricter)
RECOGNIZE_EVERY  = 30     # Frames between DeepFace recognition calls
CONFIDENCE       = 0.5    # YOLO minimum face detection confidence
ALERT_COOLDOWN   = 30     # Seconds between unauthorized alerts (avoid spam)
MODEL_YOLO       = "yolov8n-face.pt"
MODEL_FACENET    = "Facenet"
ARDUINO_PORT     = "COM4"
BAUD_RATE        = 9600
```

### Threshold tuning guide

| Distance | Meaning |
|---|---|
| 0 – 6 | Very high confidence match |
| 6 – 10 | Good match (default threshold: 10.0) |
| 10 – 15 | Uncertain — possibly same person, poor photo |
| 15+ | Different person |

---

## How Face Recognition Works

1. **Whitelist building** — `build_whitelist.py` passes each authorized photo through DeepFace's `represent()` function using the FaceNet model, producing a 128-dimensional embedding vector saved as a `.npy` file

2. **Real-time matching** — at runtime, the detected face crop is embedded the same way and compared against every whitelist embedding using Euclidean distance:

```
d(A, B) = √Σ(Aᵢ - Bᵢ)²

If d ≤ 10.0  →  AUTHORIZED
If d > 10.0  →  UNAUTHORIZED
```

3. **Threading** — YOLO runs on every frame in the main thread for smooth video. DeepFace runs every 30 frames in a background thread to prevent freezing.

---

## Camera Overlay Guide

| Colour | Meaning |
|---|---|
| 🟠 Orange | Scanning — recognition running |
| 🟢 Green | AUTHORIZED — gate opening |
| 🔴 Red | UNAUTHORIZED — alert sent |

Press **Q** to quit the camera window.
