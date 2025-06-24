import os
import sys
import pyzipper
import requests
from flask import Flask, request, send_file, jsonify
from dotenv import load_dotenv
import subprocess

# === Flask app ===
app = Flask(__name__)

# === Decrypt .env.enc ===
ENV_SECRET_PASSWORD = os.getenv("ENV_SECRET_PASSWORD")

if ENV_SECRET_PASSWORD:
    subprocess.run([
        "openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-d",
        "-in", ".env.enc",
        "-out", ".env",
        "-pass", f"pass:{ENV_SECRET_PASSWORD}"
    ], check=True)

# === Load environment ===
load_dotenv(".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ZIP_PASSWORD = os.getenv("ZIP_PASSWORD")

API_URL = "https://api.openai.com/v1/chat/completions"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {OPENAI_API_KEY}"
}


@app.route('/generate', methods=['POST'])
def generate():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Missing file parameter"}), 400

        file = request.files['file']
        if file.filename != "input.zip":
            return jsonify({"error": "Uploaded file must be named 'input.zip'"}), 400

        input_path = "input.zip"
        output_path = "output.zip"
        plain_output = "output.txt"

        file.save(input_path)

        # Step 1: Read prompt from ZIP
        with pyzipper.AESZipFile(input_path, "r") as zf:
            zf.pwd = ZIP_PASSWORD.encode("utf-8")
            if "input.txt" not in zf.namelist():
                return jsonify({"error": "input.txt not found in ZIP"}), 400
            user_prompt = zf.read("input.txt").decode("utf-8").strip()

        if not user_prompt:
            return jsonify({"error": "Prompt is empty"}), 400

        # Step 2: Send to OpenAI
        data = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": user_prompt}]
        }

        response = requests.post(API_URL, headers=HEADERS, json=data)
        if response.status_code != 200:
            return jsonify({"error": f"OpenAI Error: {response.text}"}), 500

        reply = response.json()["choices"][0]["message"]["content"]

        # Step 3: Save and ZIP result
        with open(plain_output, "w", encoding="utf-8") as out:
            out.write(reply)

        with pyzipper.AESZipFile(output_path, "w", compression=pyzipper.ZIP_DEFLATED,
                                 encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(ZIP_PASSWORD.encode("utf-8"))
            zf.write(plain_output)

        # Clean up
        os.remove(input_path)
        os.remove(plain_output)

        return send_file(output_path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/", methods=["GET"])
def index():
    return "✅ OpenAI ZIP API is running!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
