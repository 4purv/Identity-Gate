import os
import numpy as np
from deepface import DeepFace

WHITELIST_DIR="whitelist/"
EMBEDDINGS_DIR="embeddings/"
MODEL="Facenet"  # options: "Facenet", "ArcFace", "VGG-Face"

os.makedirs(EMBEDDINGS_DIR, exist_ok=True)

print("[*] Building whitelist embeddings...")

for filename in os.listdir(WHITELIST_DIR):
    if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
        continue
    name = os.path.splitext(filename)[0]  # e.g. "john_doe"
    img_path = os.path.join(WHITELIST_DIR, filename)

    try:
        result = DeepFace.represent(
            img_path=img_path,
            model_name=MODEL,
            enforce_detection=True   # set False if image gives errors
        )
        embedding = np.array(result[0]["embedding"])

        save_path = os.path.join(EMBEDDINGS_DIR, f"{name}.npy")
        np.save(save_path, embedding)
        print(f"  [+] Encoded: {name}")

    except Exception as e:
        print(f"  [!] Failed for {filename}: {e}")

print("[*] Done. Embeddings saved to:", EMBEDDINGS_DIR)