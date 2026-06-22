import cv2
import numpy as np
import os
import threading
import time
from ultralytics import YOLO
from deepface import DeepFace
import time
from app import SNAPSHOTS_DIR, new_alert, get_decision, reset_decision, start_flask
from gate_controller import connect_arduino, open_gate, close_gate, disconnect_arduino

import build_whitelist  # for load_whitelist_with_watch functionq

def get_public_url():
    try:
        with open("public_url.txt") as f:
            return f.read().strip()
    except:
        return "http://localhost:5000"
# Add this function
def load_whitelist_with_watch(embeddings_dir):
    """Load whitelist and track last modified time."""
    whitelist = {}
    last_modified = 0

    for f in os.listdir(embeddings_dir):
        if f.endswith(".npy"):
            path = os.path.join(embeddings_dir, f)
            mtime = os.path.getmtime(path)
            if mtime > last_modified:
                last_modified = mtime
            name = os.path.splitext(f)[0]
            whitelist[name] = np.load(path)

    return whitelist, last_modified

# ── Config ──────────────────────────────────────────────────
MODEL_YOLO        = "yolov8n-face.pt"   # swap to yolov8s-face.pt if downloaded
MODEL_FACENET     = "Facenet"
EMBEDDINGS_DIR    = "embeddings"
THRESHOLD         = 10.0
CONFIDENCE        = 0.5
RECOGNIZE_EVERY   = 30   # run DeepFace every N frames
# ────────────────────────────────────────────────────────────

# ── Demo optimizations ───────────────────────────────────────
ALERT_COOLDOWN   = 30    # seconds between unauthorized alerts
last_alert_time  = 0
demo_mode        = True  # shows extra info on screen for demo
# ────────────────────────────────────────────────────────────

yolo = YOLO(MODEL_YOLO)

# ── Shared state between main thread and recognition thread ──
current_name     = "Scanning..."
current_distance = 0.0
current_status   = "scanning"   # "authorized" | "unauthorized" | "scanning"
recognition_lock = threading.Lock()
recognition_running = False

def load_whitelist():
    whitelist = {}
    for f in os.listdir(EMBEDDINGS_DIR):
        if f.endswith(".npy"):
            name = os.path.splitext(f)[0]
            whitelist[name] = np.load(os.path.join(EMBEDDINGS_DIR, f))
    print(f"[*] Whitelist loaded: {list(whitelist.keys())}")
    return whitelist

def euclidean_distance(a, b):
    return np.linalg.norm(a - b)

def run_recognition(face_crop, whitelist, full_frame=None):
    """Runs in background thread — updates global state when done."""
    global current_name, current_distance, current_status, recognition_running

    temp_path = "temp_face.jpg"
    cv2.imwrite(temp_path, face_crop)

    try:
        result = DeepFace.represent(
            img_path=temp_path,
            model_name=MODEL_FACENET,
            enforce_detection=False
        )
        test_emb = np.array(result[0]["embedding"])

        best_name = "Unknown"
        best_dist = float("inf")
        for name, emb in whitelist.items():
            d = euclidean_distance(test_emb, emb)
            if d < best_dist:
                best_dist = d
                best_name = name

        with recognition_lock:
            if best_dist <= THRESHOLD:
                current_name     = best_name
                current_distance = best_dist
                current_status   = "authorized"
                # to open the gate
                print(f"[*] Authorized: {best_name} - opening gate automatically")
                threading.Thread(target=open_gate, daemon=True).start()
            else:
                current_name     = "Unknown"
                current_distance = best_dist
                current_status   = "unauthorized"
                # ── Cooldown check — avoid alert spam ──
                now = time.time()
                global last_alert_time
                if now - last_alert_time >= ALERT_COOLDOWN:
                    last_alert_time = now
                    snapshot_path   = f"snapshots/intruder_{int(now)}.jpg"
                    cv2.imwrite(snapshot_path, face_crop)
                    public_url = get_public_url()
                    new_alert(snapshot_path, public_url)
                    print("[*] Alert sent to PWA")
                else:
                    remaining = int(ALERT_COOLDOWN - (now - last_alert_time))
                    print(f"[*] Cooldown active — next alert in {remaining}s")

                # Save snapshot
                save_img = full_frame if full_frame is not None else face_crop
                snapshot_path = os.path.join(SNAPSHOTS_DIR, f"intruder_{int(now)}.jpg")
                cv2.imwrite(snapshot_path, save_img)

                # Send push notification via PWA
                public_url = get_public_url()
                new_alert(snapshot_path, public_url)
                print(f"[*] Alert sent — approval URL generated")

    except Exception as e:
        print(f"[!] Recognition error: {e}")
        with recognition_lock:
            current_status = "unauthorized"

    recognition_running = False

def draw_overlay(frame, x1, y1, x2, y2):
    """Draw bounding box and label based on current recognition state."""
    with recognition_lock:
        name   = current_name
        dist   = current_distance
        status = current_status

    if status == "authorized":
        color = (0, 255, 0)        # green
        label = f"AUTHORIZED: {name} ({dist:.1f})"
    elif status == "unauthorized":
        color = (0, 0, 255)        # red
        label = "UNAUTHORIZED"
    else:
        color = (0, 165, 255)      # orange — scanning
        label = "Scanning..."

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.putText(frame, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

def main():
    global recognition_running

    whitelist, last_mod = load_whitelist_with_watch(EMBEDDINGS_DIR)

# Inside the while loop, add this check every 100 frames:

    if not whitelist:
        print("[!] No embeddings found. Run build_whitelist.py first.")
        return

    cap = cv2.VideoCapture(0)   # 0 = default webcam
    if not cap.isOpened():
        print("[!] Cannot open webcam.")
        return
    # Start Flask server in background
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()
    print("[*] Flask PWA server started on port 5000")

    # Start Flask + Arduino only if running directly
    if not os.path.exists("public_url.txt"):
        flask_thread = threading.Thread(target=start_flask, daemon=True)
        flask_thread.start()
        print("[*] Flask PWA server started on port 5000")

    connect_arduino()

    print("[*] Starting real-time pipeline. Press Q to quit.")
    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[!] Failed to read frame.")
            break

        frame_count += 1
        if frame_count % 100 == 0:
            _, new_mod = load_whitelist_with_watch(EMBEDDINGS_DIR)
            if new_mod != last_mod:
                whitelist, last_mod = load_whitelist_with_watch(EMBEDDINGS_DIR)
                print("[*] Whitelist reloaded — changes detected")
        # ── YOLO detection every frame ──
        results = yolo(frame, conf=CONFIDENCE, verbose=False)
        boxes   = results[0].boxes

        if len(boxes) > 0:
            # Use the highest-confidence face
            best_box  = max(boxes, key=lambda b: float(b.conf[0]))
            x1, y1, x2, y2 = map(int, best_box.xyxy[0])

            # ── Trigger recognition every N frames ──
            if frame_count % RECOGNIZE_EVERY == 0 and not recognition_running:
                face_crop = frame[y1:y2, x1:x2]
                if face_crop.size > 0:
                    recognition_running = True
                    t = threading.Thread(
                        target=run_recognition,
                        args=(face_crop.copy(), whitelist, frame.copy()),
                        daemon=True
                    )
                    t.start()

            draw_overlay(frame, x1, y1, x2, y2)

        else:
            # No face detected — reset status
            with recognition_lock:
                current_status = "scanning"
            cv2.putText(frame, "No face detected", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 2)

        # ── FPS counter ──
        cv2.putText(frame, f"Frame: {frame_count}", (10, frame.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)

        # ── Check for approval decision ──
        decision = get_decision()
        if decision == "approved":
            print("[*] Approved — opening gate!")
            open_gate()
            reset_decision()
        elif decision == "denied":
            print("[*] Denied — gate stays closed.")
            close_gate()
            reset_decision()
        # ── Demo status bar ──
        if demo_mode:
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (0, h-36), (w, h), (20, 20, 20), -1)
            wl_count = len(os.listdir(EMBEDDINGS_DIR))
            bar_text = f"Whitelist: {wl_count} person(s) | Frame: {frame_count} | Press Q to quit"
            cv2.putText(frame, bar_text, (10, h-12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

        cv2.imshow("Identity Gate — Real Time", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("[*] Quit.")
            break

    cap.release()
    cv2.destroyAllWindows()
    disconnect_arduino()

if __name__ == "__main__":
    main()