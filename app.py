from flask import Flask, request, jsonify, render_template, send_file
from pywebpush import webpush, WebPushException
import threading, time, os, json, uuid, cv2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder="static", template_folder="templates")

# ── Config ──────────────────────────────────────────────────
VAPID_PRIVATE_KEY  = "vapid_private.pem"
VAPID_CLAIMS       = {"sub": "mailto:you@example.com"}
SNAPSHOTS_DIR      = "snapshots"
SUBSCRIPTIONS_FILE = "subscriptions.json"
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
# ────────────────────────────────────────────────────────────

# ── Gate state ───────────────────────────────────────────────
gate_state = {
    "decision"  : "pending",
    "snapshot"  : None,
    "timestamp" : None,
    "token"     : None,
}
gate_lock = threading.Lock()

# ── Push subscriptions storage ───────────────────────────────
def load_subscriptions():
    if os.path.exists(SUBSCRIPTIONS_FILE):
        with open(SUBSCRIPTIONS_FILE) as f:
            return json.load(f)
    return []

def save_subscriptions(subs):
    with open(SUBSCRIPTIONS_FILE, "w") as f:
        json.dump(subs, f, indent=2)

# ── PWA Routes ───────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/subscribe", methods=["POST"])
def subscribe():
    """Save browser push subscription from PWA."""
    sub = request.json
    subs = load_subscriptions()
    # Avoid duplicates
    endpoints = [s["endpoint"] for s in subs]
    if sub["endpoint"] not in endpoints:
        subs.append(sub)
        save_subscriptions(subs)
        print(f"[+] New push subscription saved ({len(subs)} total)")
    return jsonify({"status": "ok"})

@app.route("/snapshot/<filename>")
def serve_snapshot(filename):
    path = os.path.join(SNAPSHOTS_DIR, filename)
    if os.path.exists(path):
        return send_file(path, mimetype="image/jpeg")
    return "Not found", 404

# ── Gate decision routes ─────────────────────────────────────
@app.route("/approve/<token>", methods=["POST"])
def approve(token):
    with gate_lock:
        if gate_state["token"] != token:
            return jsonify({"status": "error"}), 403
        gate_state["decision"] = "approved"
    print("[*] Gate APPROVED via PWA")
    return jsonify({"status": "approved"})

@app.route("/deny/<token>", methods=["POST"])
def deny(token):
    with gate_lock:
        if gate_state["token"] != token:
            return jsonify({"status": "error"}), 403
        gate_state["decision"] = "denied"
    print("[*] Gate DENIED via PWA")
    return jsonify({"status": "denied"})

@app.route("/status")
def status():
    with gate_lock:
        return jsonify({
            "decision"  : gate_state["decision"],
            "token"     : gate_state["token"],
            "timestamp" : gate_state["timestamp"],
            "snapshot"  : os.path.basename(gate_state["snapshot"]) if gate_state["snapshot"] else None
        })

# ── Whitelist API ─────────────────────────────────────────────
import base64
from werkzeug.utils import secure_filename

@app.route("/api/whitelist/upload-photo", methods=["POST"])
def api_upload_photo():
    from whitelist_manager import add_person
    import base64

    data       = request.json
    name       = data.get("name", "").strip().lower().replace(" ", "_")
    image_data = data.get("image_data", "")

    if not name:
        return jsonify({"status": "error", "msg": "Name is required"}), 400
    if not image_data:
        return jsonify({"status": "error", "msg": "Image is required"}), 400

    try:
        # Decode base64 image
        if "," in image_data:
            header, encoded = image_data.split(",", 1)
        else:
            encoded = image_data

        img_bytes = base64.b64decode(encoded)

        # Save image to whitelist folder
        os.makedirs("whitelist", exist_ok=True)
        filename  = f"{name}.jpg"
        save_path = os.path.join(BASE_DIR, "whitelist", filename)

        with open(save_path, "wb") as f:
            f.write(img_bytes)

        print(f"[*] Image saved: {save_path}")
        print(f"[*] Image size: {os.path.getsize(save_path)} bytes")

        # Generate embedding — this is the key step
        success, message = add_person(name, save_path)

        if success:
            # Verify .npy file exists
            npy_path = os.path.join(BASE_DIR, "embeddings", f"{name}.npy")
            npy_exists = os.path.exists(npy_path)
            print(f"[*] NPY file exists: {npy_exists} at {npy_path}")

            return jsonify({
                "status" : "ok",
                "msg"    : message,
                "npy"    : npy_exists
            })
        else:
            # Clean up saved image if embedding failed
            if os.path.exists(save_path):
                os.remove(save_path)
            return jsonify({"status": "error", "msg": message}), 400

    except Exception as e:
        print(f"[!] Upload error: {e}")
        return jsonify({"status": "error", "msg": str(e)}), 500
@app.route("/api/whitelist", methods=["GET"])
def api_whitelist_list():
    from whitelist_manager import load_db
    return jsonify(load_db())

@app.route("/api/whitelist/add", methods=["POST"])
def api_whitelist_add():
    from whitelist_manager import add_person
    data = request.json
    name = data.get("name", "").strip().lower().replace(" ", "_")
    image_path = data.get("image_path", "")
    success = add_person(name, image_path)
    return jsonify({"status": "ok" if success else "error"})

@app.route("/api/whitelist/remove", methods=["POST"])
def api_whitelist_remove():
    from whitelist_manager import remove_person
    name = request.json.get("name", "")
    success = remove_person(name)
    return jsonify({"status": "ok" if success else "error"})

# ── Internal API (called by pipeline) ────────────────────────
def new_alert(snapshot_path, public_url):
    """Called by pipeline — sets up new alert and sends push."""
    token = str(uuid.uuid4())[:8]
    with gate_lock:
        gate_state["decision"]  = "pending"
        gate_state["snapshot"]  = snapshot_path
        gate_state["timestamp"] = time.strftime("%d %b %Y, %H:%M:%S")
        gate_state["token"]     = token

    approval_url = f"{public_url}/decision/{token}"
    snap_filename = os.path.basename(snapshot_path)

    # Send push notification to all subscribed devices
    _send_push_to_all({
        "title"       : "🚨 Unauthorized Access Attempt",
        "body"        : f"Unknown person at gate — {gate_state['timestamp']}",
        "url"         : approval_url,
        "snapshot"    : f"{public_url}/snapshot/{snap_filename}",
        "token"       : token,
    })
    return approval_url

def _send_push_to_all(payload):
    subs = load_subscriptions()
    dead = []
    for sub in subs:
        try:
            webpush(
                subscription_info=sub,
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )
        except WebPushException as e:
            if "410" in str(e) or "404" in str(e):
                dead.append(sub)   # subscription expired
            print(f"[!] Push failed: {e}")
    # Remove expired subscriptions
    if dead:
        subs = [s for s in subs if s not in dead]
        save_subscriptions(subs)

def get_decision():
    with gate_lock:
        return gate_state["decision"]

def reset_decision():
    with gate_lock:
        gate_state["decision"] = "pending"

def start_flask():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)