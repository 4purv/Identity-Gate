import serial
import time
import threading

# ── Config ──────────────────────────────────────────────────
ARDUINO_PORT  = "COM4"    # change to your port
BAUD_RATE     = 9600
# ────────────────────────────────────────────────────────────

arduino   = None
gate_lock = threading.Lock()

def connect_arduino():
    global arduino
    try:
        arduino = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=2)
        time.sleep(2)   # wait for Arduino to reset
        response = arduino.readline().decode().strip()
        if response == "READY":
            print(f"[+] Arduino connected on {ARDUINO_PORT}")
        else:
            print(f"[*] Arduino connected (response: {response})")
        return True
    except Exception as e:
        print(f"[!] Could not connect to Arduino: {e}")
        print(f"    Running in simulation mode.")
        return False

def open_gate():
    with gate_lock:
        if arduino and arduino.is_open:
            arduino.write(b'O')
            print("[*] Gate command sent: OPEN")
            time.sleep(0.2)
            while arduino.in_waiting:
                line = arduino.readline().decode().strip()
                print(f"  Arduino: {line}")
        else:
            print("[*] >>> GATE OPEN (simulated) <<<")

def close_gate():
    with gate_lock:
        if arduino and arduino.is_open:
            arduino.write(b'C')
            print("[*] Gate command sent: CLOSE")
        else:
            print("[*] >>> GATE CLOSED (simulated) <<<")

def disconnect_arduino():
    global arduino
    if arduino and arduino.is_open:
        arduino.close()
        print("[*] Arduino disconnected.")

# ── Test standalone ──────────────────────────────────────────
if __name__ == "__main__":
    if connect_arduino():
        print("\n[*] Testing gate — opening...")
        open_gate()
        time.sleep(6)
        print("[*] Test complete.")
        disconnect_arduino()
    else:
        print("\n[*] Simulation mode:")
        open_gate()
        time.sleep(2)
        close_gate()