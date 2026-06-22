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

### 1. Clone the repository

```bash
git clone https://github.com/yourusername/identity-gate.git
cd identity-gate
```

### 2. Create and activate virtual environment

```bash
# Create venv with Python 3.11
py -3.11 -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install tensorflow
python -m pip install deepface tf-keras opencv-python numpy
python -m pip install flask pywebpush cryptography pyngrok pyserial
python -m pip install ultralytics requests pillow
```

### 4. Configure ngrok

Sign up at https://ngrok.com and get your auth token from:
https://dashboard.ngrok.com/get-started/your-authtoken

```bash
ngrok config add-authtoken YOUR_NGROK_TOKEN
```

### 5. Generate VAPID keys (run once)

```bash
cd phase1_recognition
python generate_vapid.py
```

Copy the printed public key and paste it into `static/app.js`:

```javascript
const VAPID_PUBLIC_KEY = "YOUR_VAPID_PUBLIC_KEY_HERE";
```

### 6. Upload Arduino sketch

Open `Arduino/gate_controller.ino` in Arduino IDE:

- Select **Tools → Board → Arduino Uno**
- Select **Tools → Port → COM_** (your Arduino port)
- Click **Upload**
- Open Serial Monitor — confirm it prints `READY`

```cpp
#include <Servo.h>
Servo gateServo;

void setup() {
  Serial.begin(9600);
  gateServo.attach(9);
  gateServo.write(0);
  Serial.println("READY");
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'O') {
      gateServo.write(90);
      Serial.println("GATE_OPENED");
      delay(5000);
      gateServo.write(0);
      Serial.println("GATE_CLOSED");
    } else if (cmd == 'C') {
      gateServo.write(0);
      Serial.println("GATE_CLOSED");
    }
  }
}
```

### 7. Update Arduino COM port

In `gate_controller.py`, set your port:

```python
ARDUINO_PORT = "COM4"   # Windows
# ARDUINO_PORT = "/dev/ttyUSB0"  # Linux/Mac
```

---

## Adding Authorized Persons

### Option A — CLI

```bash
cd phase1_recognition

# Add a person
python whitelist_manager.py add apurv_badhe path/to/photo.jpg

# List all authorized persons
python whitelist_manager.py list

# Remove a person
python whitelist_manager.py remove apurv_badhe

# Re-encode all photos from scratch
python whitelist_manager.py rebuild
```

### Option B — From the PWA (on your phone)

1. Open the PWA on your Android phone
2. Go to the **Whitelist** tab
3. Enter the person's name
4. Tap **Take photo or choose from gallery**
5. Tap **+ Add person**

The system generates the embedding automatically and the pipeline reloads within 100 frames.

---

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

---

## Troubleshooting

**`FileNotFoundError: yolov8n-face.pt`**
```bash
cd phase1_recognition
python -c "from ultralytics import YOLO; YOLO('yolov8n-face.pt')"
```

**`No module named 'cv2'`**
→ Virtual environment is not activated. Run `venv\Scripts\activate` first.

**ngrok tunnel already active error**
→ Add `ngrok.kill()` and `time.sleep(2)` at the top of `run_system.py` before `ngrok.connect()`. Or go to https://dashboard.ngrok.com/endpoints and stop existing tunnels.

**Arduino not detected**
→ Install CH340 driver (common for clone Arduinos). Check Device Manager for the correct COM port. Update `ARDUINO_PORT` in `gate_controller.py`.

**Face always shows UNAUTHORIZED**
→ Lower the threshold: change `THRESHOLD = 10.0` to `THRESHOLD = 12.0`. Use a clearer, well-lit front-facing photo in the whitelist.

**Push notifications not arriving**
→ Make sure the PWA is installed on your Android phone, notifications are allowed, and the phone subscribed (tapped "Enable notifications"). Check `subscriptions.json` has an entry.

**Slow first recognition**
→ Normal — DeepFace loads the FaceNet model (~90MB) on first use. Subsequent recognitions are fast. The startup pre-warm in `run_system.py` eliminates this for the first real detection.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Serves the PWA |
| POST | `/subscribe` | Save phone push subscription |
| GET | `/status` | Get current gate alert state |
| GET | `/snapshot/<filename>` | Serve intruder snapshot |
| POST | `/approve/<token>` | Approve gate access |
| POST | `/deny/<token>` | Deny gate access |
| GET | `/api/whitelist` | List all authorized persons |
| POST | `/api/whitelist/add` | Add person via image path |
| POST | `/api/whitelist/upload-photo` | Add person via base64 photo (PWA upload) |
| POST | `/api/whitelist/remove` | Remove a person |

---

## Performance

| Metric | Value |
|---|---|
| Face detection | ~30 FPS |
| Recognition interval | Every ~1 second (30 frames) |
| Push notification delivery | < 3 seconds |
| Gate response after approval | < 1 second |
| Alert cooldown | 30 seconds |
| Whitelist auto-reload | Every 100 frames |

---

## Future Scope

- Anti-spoofing — detect printed photos vs real faces
- Multi-face support — handle multiple people at gate simultaneously
- Raspberry Pi deployment — fully standalone embedded system
- Database backend — MySQL/Firebase for large-scale whitelist
- Vehicle ignition integration — extend gate signal to engine start/stop
- Audit logging — persistent access event history with timestamps and photos
- Night vision — infrared camera support for low-light environments

---

## Dependencies

```
tensorflow
deepface
tf-keras
opencv-python
numpy
ultralytics
flask
pywebpush
cryptography
pyngrok
pyserial
requests
pillow
```

