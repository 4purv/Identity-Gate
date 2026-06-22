import os
import json
import shutil
import numpy as np
from deepface import DeepFace

# ── Config ──────────────────────────────────────────────────
WHITELIST_DIR  = "whitelist"
EMBEDDINGS_DIR = "embeddings"
DB_FILE        = "whitelist_db.json"   # tracks names + metadata
MODEL          = "Facenet"
# ────────────────────────────────────────────────────────────

os.makedirs(WHITELIST_DIR, exist_ok=True)
os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

def load_db():
    """Load whitelist metadata from JSON file."""
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_db(db):
    """Save whitelist metadata to JSON file."""
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def add_person(name, image_path):
    """
    Add a person to the whitelist.
    Returns (True, "success message") or (False, "error message")
    """
    print(f"\n[*] Adding: {name}")

    if not os.path.exists(image_path):
        msg = f"Image not found: {image_path}"
        print(f"[!] {msg}")
        return False, msg

    # Generate embedding
    try:
        from deepface import DeepFace
        import numpy as np

        print(f"[*] Generating embedding for {name}...")
        result = DeepFace.represent(
            img_path=image_path,
            model_name=MODEL,
            enforce_detection=True
        )
        embedding = np.array(result[0]["embedding"])
        print(f"[*] Embedding shape: {embedding.shape}")

    except Exception as e:
        # Try again with enforce_detection=False
        try:
            result = DeepFace.represent(
                img_path=image_path,
                model_name=MODEL,
                enforce_detection=False
            )
            embedding = np.array(result[0]["embedding"])
            print(f"[*] Embedding generated (detection relaxed)")
        except Exception as e2:
            msg = f"Could not extract face: {str(e2)}"
            print(f"[!] {msg}")
            return False, msg

    # Save embedding
    os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
    npy_path = os.path.join(EMBEDDINGS_DIR, f"{name}.npy")
    np.save(npy_path, embedding)
    print(f"[+] Embedding saved: {npy_path}")

    # Verify it was saved
    if not os.path.exists(npy_path):
        msg = "Embedding file was not saved correctly"
        print(f"[!] {msg}")
        return False, msg

    # Update DB
    db = load_db()
    db[name] = {
        "image"    : image_path,
        "embedding": npy_path,
        "added_on" : __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    save_db(db)

    print(f"[+] Successfully added: {name}")
    return True, f"{name} added successfully"

def remove_person(name):
    """Remove a person from the whitelist."""
    print(f"\n[*] Removing: {name}")

    db = load_db()
    if name not in db:
        print(f"[!] '{name}' not found in whitelist.")
        list_persons()
        return False

    # Delete embedding file
    npy_path = os.path.join(EMBEDDINGS_DIR, f"{name}.npy")
    if os.path.exists(npy_path):
        os.remove(npy_path)

    # Delete image from whitelist folder
    for ext in [".jpg", ".jpeg", ".png"]:
        img_path = os.path.join(WHITELIST_DIR, f"{name}{ext}")
        if os.path.exists(img_path):
            os.remove(img_path)

    # Update DB
    del db[name]
    save_db(db)

    print(f"[+] Removed: {name}")
    return True

def list_persons():
    """Print all authorized persons."""
    db = load_db()

    if not db:
        print("\n[*] Whitelist is empty.")
        return

    print(f"\n[*] Authorized persons ({len(db)}):")
    print("-" * 40)
    for name, info in db.items():
        print(f"  Name    : {name}")
        print(f"  Added   : {info.get('added_on', 'N/A')}")
        print("-" * 40)

def rebuild_all():
    """Re-encode all images in whitelist/ folder from scratch."""
    print("\n[*] Rebuilding all embeddings...")
    db = load_db()

    for filename in os.listdir(WHITELIST_DIR):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        name = os.path.splitext(filename)[0]
        img_path = os.path.join(WHITELIST_DIR, filename)
        try:
            result = DeepFace.represent(
                img_path=img_path,
                model_name=MODEL,
                enforce_detection=True
            )
            embedding = np.array(result[0]["embedding"])
            npy_path = os.path.join(EMBEDDINGS_DIR, f"{name}.npy")
            np.save(npy_path, embedding)
            print(f"  [+] Re-encoded: {name}")
        except Exception as e:
            print(f"  [!] Failed for {name}: {e}")

    print("[*] Rebuild complete.")

# ── CLI Interface ────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("""
Usage:
  python whitelist_manager.py list
  python whitelist_manager.py add <name> <image_path>
  python whitelist_manager.py remove <name>
  python whitelist_manager.py rebuild
        """)
        sys.exit(0)

    command = sys.argv[1].lower()

    if command == "list":
        list_persons()

    elif command == "add":
        if len(sys.argv) < 4:
            print("[!] Usage: python whitelist_manager.py add <name> <image_path>")
        else:
            add_person(sys.argv[2], sys.argv[3])

    elif command == "remove":
        if len(sys.argv) < 3:
            print("[!] Usage: python whitelist_manager.py remove <name>")
        else:
            remove_person(sys.argv[2])

    elif command == "rebuild":
        rebuild_all()

    else:
        print(f"[!] Unknown command: {command}")