import threading
import time
import os
import sys
from pyngrok import ngrok
ngrok.kill()  # kill any existing tunnels
time.sleep(1)
print("""
╔══════════════════════════════════════════╗
║       IDENTITY GATE — Starting up        ║
╚══════════════════════════════════════════╝
""")

# ── Step 1: Start Flask + ngrok ──────────────────────────────
from app import start_flask

flask_thread = threading.Thread(target=start_flask, daemon=True)
flask_thread.start()
time.sleep(1)   # wait for Flask to start

# Kill existing tunnels
ngrok.kill()
time.sleep(1)

# Use your static domain
tunnel = ngrok.connect(
    addr=5000,
    proto="http",
    hostname="biauricular-suspectless-annie.ngrok-free.dev"
)
public_url = f"https://biauricular-suspectless-annie.ngrok-free.dev"

print(f"\n{'='*50}")
print(f"  PWA URL : {public_url}")
print(f"  Open on Android → Install → Enable notifications")
print(f"{'='*50}\n")

with open("public_url.txt", "w") as f:
    f.write(public_url)

# ── Step 2: Connect Arduino ───────────────────────────────────
from gate_controller import connect_arduino
connect_arduino()

# ── Step 3: Start real-time pipeline ─────────────────────────
print("[*] Starting camera pipeline in 2 seconds...")
time.sleep(2)

from realtime_pipeline import main as run_pipeline

try:
    run_pipeline()
except KeyboardInterrupt:
    print("\n[*] Shutting down...")
finally:
    from gate_controller import disconnect_arduino
    disconnect_arduino()
    ngrok.disconnect(tunnel.public_url)
    print("[*] System stopped cleanly.")