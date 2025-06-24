import os
import sys
import subprocess
from dotenv import load_dotenv
import requests
import pyzipper

# === CONFIG ===
ENV_ENCRYPTED_FILE = ".env.enc"
ENV_DECRYPTED_FILE = ".env"
DECRYPTION_PASSWORD = os.getenv("ENV_SECRET_PASSWORD")  # Set this securely!

# === STEP 1: Decrypt .env.enc ===
if not DECRYPTION_PASSWORD:
    print("❌ Missing ENV_SECRET_PASSWORD for decryption.")
    sys.exit(1)

try:
    subprocess.run([
        "openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-d",
        "-in", ENV_ENCRYPTED_FILE,
        "-out", ENV_DECRYPTED_FILE,
        "-pass", f"pass:{DECRYPTION_PASSWORD}"
    ], check=True)
except subprocess.CalledProcessError:
    print("❌ Failed to decrypt .env.enc")
    sys.exit(1)

# === STEP 2: Load environment variables ===
load_dotenv(dotenv_path=ENV_DECRYPTED_FILE)

API_KEY = os.getenv("OPENAI_API_KEY")
ZIP_PASSWORD = os.getenv("ZIP_PASSWORD")

if not API_KEY or not ZIP_PASSWORD:
    print("❌ Missing required environment variables.")
    sys.exit(1)

# === Optional: Clean up the decrypted .env ===
try:
    os.remove(ENV_DECRYPTED_FILE)
except Exception as e:
    print(f"⚠️ Warning: Could not delete .env: {e}")

# === STEP 3: Main Logic ===
API_URL = "https://api.openai.com/v1/chat/completions"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

INPUT_ZIP = "input.zip"
OUTPUT_ZIP = "output.zip"
PLAIN_OUTPUT = "output.txt"
INPUT_FILENAME = "input.txt"

try:
    # Step 4: Extract input
    if not os.path.exists(INPUT_ZIP):
        raise FileNotFoundError(f"ZIP file not found: {INPUT_ZIP}")

    with pyzipper.AESZipFile(INPUT_ZIP, "r") as zf:
        zf.pwd = ZIP_PASSWORD.encode("utf-8")
        if INPUT_FILENAME not in zf.namelist():
            raise FileNotFoundError(f"{INPUT_FILENAME} not found in ZIP")
        user_prompt = zf.read(INPUT_FILENAME).decode("utf-8").strip()

    if not user_prompt:
        raise ValueError("Input prompt is empty.")

    # Step 5: Send request
    data = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": user_prompt}]
    }

    response = requests.post(API_URL, headers=HEADERS, json=data)
    if response.status_code != 200:
        raise RuntimeError(f"API error {response.status_code}: {response.text}")

    reply = response.json()["choices"][0]["message"]["content"]

    # Step 6: Save plain output
    with open(PLAIN_OUTPUT, "w", encoding="utf-8") as out:
        out.write(reply)

    # Step 7: Encrypt output
    with pyzipper.AESZipFile(OUTPUT_ZIP, "w", compression=pyzipper.ZIP_DEFLATED,
                             encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(ZIP_PASSWORD.encode("utf-8"))
        zf.write(PLAIN_OUTPUT)

    os.remove(PLAIN_OUTPUT)
    print(f"✅ Success! Response saved to {OUTPUT_ZIP}")

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
