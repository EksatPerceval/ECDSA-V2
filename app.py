import base64
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from werkzeug.utils import secure_filename

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(APP_ROOT, "storage")
KEYS_DIR = os.path.join(STORAGE_DIR, "keys")
UPLOADS_DIR = os.path.join(STORAGE_DIR, "uploads")
SIGNATURES_DIR = os.path.join(STORAGE_DIR, "signatures")

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = {"pdf"}

for path in [STORAGE_DIR, KEYS_DIR, UPLOADS_DIR, SIGNATURES_DIR]:
    os.makedirs(path, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE


# Menghasilkan response error JSON standar agar format error konsisten di semua endpoint.
def error_response(message: str, status_code: int = 400):
    return jsonify({"ok": False, "error": message}), status_code


# Memvalidasi apakah nama file memiliki ekstensi yang diizinkan (saat ini hanya .pdf).
def is_allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


# Menyimpan file upload ke target directory dengan nama acak agar aman dan unik.
# Jika must_be_pdf=True, fungsi juga memaksa file harus berekstensi PDF.
def save_uploaded_file(file_storage, target_dir: str, must_be_pdf: bool = False):
    if file_storage is None:
        raise ValueError("File tidak ditemukan pada request.")

    filename = secure_filename(file_storage.filename or "")
    if not filename:
        raise ValueError("Nama file tidak valid.")

    if must_be_pdf and not is_allowed_file(filename):
        raise ValueError("Hanya file PDF (.pdf) yang diizinkan.")

    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[1].lower()

    new_name = f"{uuid.uuid4().hex}{ext}"
    target_path = os.path.join(target_dir, new_name)
    file_storage.save(target_path)

    if not os.path.exists(target_path) or os.path.getsize(target_path) == 0:
        raise ValueError("File gagal disimpan atau kosong.")

    return target_path, filename


# Membaca seluruh isi file dalam bentuk bytes (binary mode).
def read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


# Menghasilkan digest SHA-256 dalam format string heksadesimal.
def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# Memuat private key dari bytes PEM menjadi objek key cryptography.
def load_private_key_from_pem_bytes(pem_bytes: bytes):
    return serialization.load_pem_private_key(pem_bytes, password=None)


# Memuat public key dari bytes PEM menjadi objek key cryptography.
def load_public_key_from_pem_bytes(pem_bytes: bytes):
    return serialization.load_pem_public_key(pem_bytes)


@app.route("/")
# Menyajikan halaman utama aplikasi web.
def home():
    return render_template("index.html")


@app.route("/api/generate-keys", methods=["POST"])
# Membuat pasangan kunci ECDSA (private/public), menyimpannya, lalu mengembalikan kontennya.
def generate_keys():
    try:
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        private_name = f"ecdsa_private_{ts}.pem"
        public_name = f"ecdsa_public_{ts}.pem"

        private_path = os.path.join(KEYS_DIR, private_name)
        public_path = os.path.join(KEYS_DIR, public_name)

        with open(private_path, "wb") as f:
            f.write(private_pem)

        with open(public_path, "wb") as f:
            f.write(public_pem)

        return jsonify(
            {
                "ok": True,
                "message": "Keypair berhasil dibuat.",
                "private_key": {
                    "filename": private_name,
                    "content": private_pem.decode("utf-8"),
                },
                "public_key": {
                    "filename": public_name,
                    "content": public_pem.decode("utf-8"),
                },
            }
        )
    except Exception:
        return error_response("Gagal membuat keypair ECDSA.", 500)


@app.route("/api/sign", methods=["POST"])
# Menandatangani hash PDF menggunakan private key, lalu menyimpan payload signature JSON.
def sign_pdf():
    pdf_file = request.files.get("pdf")
    private_key_file = request.files.get("private_key")

    if pdf_file is None or private_key_file is None:
        return error_response("Field wajib: pdf dan private_key.")

    try:
        pdf_path, original_pdf_name = save_uploaded_file(pdf_file, UPLOADS_DIR, must_be_pdf=True)
        private_path, _ = save_uploaded_file(private_key_file, UPLOADS_DIR, must_be_pdf=False)

        pdf_bytes = read_file_bytes(pdf_path)
        pdf_hash_hex = sha256_hex(pdf_bytes)

        private_key_pem = read_file_bytes(private_path)
        private_key = load_private_key_from_pem_bytes(private_key_pem)

        signature = private_key.sign(
            pdf_hash_hex.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        sig_payload = {
            "algorithm": "ECDSA",
            "curve": "SECP256R1",
            "hash_algorithm": "SHA256",
            "document_name": original_pdf_name,
            "document_hash_hex": pdf_hash_hex,
            "signature_b64": signature_b64,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }

        sig_name = f"signature_{uuid.uuid4().hex}.sig.json"
        sig_path = os.path.join(SIGNATURES_DIR, sig_name)
        with open(sig_path, "w", encoding="utf-8") as f:
            json.dump(sig_payload, f, ensure_ascii=False, indent=2)

        return jsonify(
            {
                "ok": True,
                "message": "PDF berhasil ditandatangani.",
                "signature": {
                    "filename": sig_name,
                    "content": json.dumps(sig_payload, ensure_ascii=False, indent=2),
                },
            }
        )
    except ValueError as ve:
        return error_response(str(ve), 400)
    except Exception:
        return error_response("Proses sign gagal. Pastikan private key valid.", 400)


@app.route("/api/verify", methods=["POST"])
# Memverifikasi signature ECDSA dan memastikan isi PDF belum berubah (hash match).
def verify_pdf():
    pdf_file = request.files.get("pdf")
    signature_file = request.files.get("signature")
    public_key_file = request.files.get("public_key")

    if pdf_file is None or signature_file is None or public_key_file is None:
        return error_response("Field wajib: pdf, signature, dan public_key.")

    try:
        pdf_path, _ = save_uploaded_file(pdf_file, UPLOADS_DIR, must_be_pdf=True)
        sig_path, _ = save_uploaded_file(signature_file, UPLOADS_DIR, must_be_pdf=False)
        pub_path, _ = save_uploaded_file(public_key_file, UPLOADS_DIR, must_be_pdf=False)

        pdf_bytes = read_file_bytes(pdf_path)
        current_pdf_hash_hex = sha256_hex(pdf_bytes)

        with open(sig_path, "r", encoding="utf-8") as f:
            sig_payload = json.load(f)

        required_fields = [
            "algorithm",
            "curve",
            "hash_algorithm",
            "document_hash_hex",
            "signature_b64",
        ]
        for field in required_fields:
            if field not in sig_payload:
                return error_response(f"Signature file tidak valid. Field '{field}' tidak ditemukan.", 400)

        if sig_payload["algorithm"] != "ECDSA":
            return jsonify(
                {
                    "ok": True,
                    "valid": False,
                    "reason": "Algoritma pada signature tidak didukung.",
                }
            )

        signed_hash_hex = sig_payload["document_hash_hex"]

        if not re.fullmatch(r"[0-9a-f]{64}", signed_hash_hex):
            return error_response("Hash dalam signature tidak valid.", 400)

        signature = base64.b64decode(sig_payload["signature_b64"])
        public_key_pem = read_file_bytes(pub_path)
        public_key = load_public_key_from_pem_bytes(public_key_pem)

        # 1) Verifikasi kriptografi signature terhadap hash di file signature.
        # Jika gagal di tahap ini, berarti signature/public key tidak cocok.
        public_key.verify(
            signature,
            signed_hash_hex.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )

        # 2) Setelah signature valid, baru cek apakah isi PDF saat ini sama dengan hash yang ditandatangani.
        if current_pdf_hash_hex != signed_hash_hex:
            return jsonify(
                {
                    "ok": True,
                    "valid": False,
                    "reason": "Konten PDF telah berubah (hash mismatch).",
                    "details": {
                        "signed_hash": signed_hash_hex,
                        "current_hash": current_pdf_hash_hex,
                    },
                }
            )

        return jsonify(
            {
                "ok": True,
                "valid": True,
                "reason": "Signature valid dan PDF tidak berubah.",
                "details": {
                    "hash": current_pdf_hash_hex,
                },
            }
        )
    except InvalidSignature:
        return jsonify(
            {
                "ok": True,
                "valid": False,
                "reason": "Signature kriptografi tidak valid (signature/public key tidak cocok).",
            }
        )
    except json.JSONDecodeError:
        return error_response("Signature file harus format JSON yang valid.", 400)
    except ValueError as ve:
        return error_response(str(ve), 400)
    except Exception:
        return error_response("Verifikasi gagal. Pastikan file signature dan public key valid.", 400)


@app.errorhandler(413)
# Menangani request dengan ukuran payload melebihi batas maksimum upload.
def request_entity_too_large(_):
    return error_response("Ukuran file terlalu besar. Maksimal 20 MB.", 413)


if __name__ == "__main__":
    app.run(debug=True)
