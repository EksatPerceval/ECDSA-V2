import base64
import hashlib
import io
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone, date

import qrcode
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from flask import Flask, jsonify, render_template, request, session
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(APP_ROOT, "storage")
KEYS_DIR = os.path.join(STORAGE_DIR, "keys")
UPLOADS_DIR = os.path.join(STORAGE_DIR, "uploads")
SIGNATURES_DIR = os.path.join(STORAGE_DIR, "signatures")
DB_DIR = os.path.join(STORAGE_DIR, "db")
USERS_DB_PATH = os.path.join(DB_DIR, "users.json")

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = {"pdf"}
SIGNATURE_EXPIRE_DAYS_DEFAULT = 30

for path in [STORAGE_DIR, KEYS_DIR, UPLOADS_DIR, SIGNATURES_DIR, DB_DIR]:
    os.makedirs(path, exist_ok=True)

if not os.path.exists(USERS_DB_PATH):
    with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump({"users": []}, f, ensure_ascii=False, indent=2)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")


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


# Membaca database user sederhana berbasis JSON.
def load_users_db():
    with open(USERS_DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# Menyimpan database user sederhana berbasis JSON.
def save_users_db(db_data):
    with open(USERS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db_data, f, ensure_ascii=False, indent=2)


def find_user_by_username(username: str):
    db = load_users_db()
    for user in db.get("users", []):
        if user.get("username") == username:
            return user
    return None


def find_user_by_id(user_id: str):
    db = load_users_db()
    for user in db.get("users", []):
        if user.get("id") == user_id:
            return user
    return None


def ensure_logged_in():
    uid = session.get("user_id")
    if not uid:
        return None
    return find_user_by_id(uid)


def parse_iso_utc(dt_str: str):
    if not dt_str:
        return None
    normalized = dt_str.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_signature_expired(expires_at_utc: str):
    if not expires_at_utc:
        return False, None
    expires_dt = parse_iso_utc(expires_at_utc)
    now_dt = datetime.now(timezone.utc)
    return now_dt > expires_dt, expires_dt


def create_qr_data_uri(payload_dict):
    payload_json = json.dumps(payload_dict, ensure_ascii=False, separators=(",", ":"))
    qr_img = qrcode.make(payload_json)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def create_qr_png_bytes(payload_dict) -> bytes:
    payload_json = json.dumps(payload_dict, ensure_ascii=False, separators=(",", ":"))
    qr_img = qrcode.make(payload_json)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    return buf.getvalue()


def parse_ratio(value, default_value):
    try:
        parsed = float(value)
        if parsed < 0:
            return 0.0
        if parsed > 1:
            return 1.0
        return parsed
    except Exception:
        return default_value


def format_indonesian_date(dt_obj) -> str:
    if isinstance(dt_obj, datetime):
        d = dt_obj.date()
    elif isinstance(dt_obj, date):
        d = dt_obj
    else:
        d = datetime.now(timezone(timedelta(hours=7))).date()

    bulan_id = [
        "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    ]
    return f"{d.day} {bulan_id[d.month - 1]} {d.year}"


def build_signed_pdf_with_qr_and_name(
    src_pdf_path: str,
    qr_png_bytes: bytes,
    signer_name: str,
    signer_nip: str = "",
    qr_x_ratio: float = 0.03,
    qr_y_ratio: float = 0.05,
    signed_location_date: str = "",
) -> str:
    reader = PdfReader(src_pdf_path)
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        if i != len(reader.pages) - 1:
            writer.add_page(page)
            continue

        width = float(page.mediabox.width)
        height = float(page.mediabox.height)

        overlay_stream = io.BytesIO()
        c = canvas.Canvas(overlay_stream, pagesize=(width, height))

        qr_size = 72
        block_width = 190
        line_gap = 12  # approx single spacing (1.0)
        block_height = 172
        max_x = max(width - block_width - 12, 0)
        max_y = max(height - block_height - 12, 0)

        margin_x = qr_x_ratio * max_x
        # sinkronkan orientasi Y dari preview (top-left) ke PDF (bottom-left)
        margin_y = (1.0 - qr_y_ratio) * max_y

        top_y = margin_y + block_height
        center_x = margin_x + (block_width / 2)

        # Lokasi + tanggal (center)
        c.setFont("Helvetica", 9)
        c.drawCentredString(center_x, top_y - 2, signed_location_date or "Jimbaran, 1 Juli 2026")

        # Jabatan (tidak bold) + spacing 1.0
        c.setFont("Helvetica", 9)
        c.drawCentredString(center_x, top_y - 2 - line_gap, "Pembimbing Akademik")

        # QR (center)
        qr_reader = ImageReader(io.BytesIO(qr_png_bytes))
        qr_x = center_x - (qr_size / 2)
        qr_y = top_y - 2 - (line_gap * 2) - qr_size
        c.drawImage(
            qr_reader,
            qr_x,
            qr_y,
            width=qr_size,
            height=qr_size,
            preserveAspectRatio=True,
            mask="auto",
        )

        # Nama pembimbing (center + underline)
        c.setFont("Helvetica", 9)
        name_text = signer_name or "-"
        name_y = qr_y - 16
        c.drawCentredString(center_x, name_y, name_text)
        name_width = c.stringWidth(name_text, "Helvetica", 9)
        c.line(center_x - (name_width / 2), name_y - 2, center_x + (name_width / 2), name_y - 2)

        # NIP (center)
        c.drawCentredString(center_x, name_y - 14, f"NIP: {signer_nip or '-'}")

        c.save()
        overlay_stream.seek(0)

        overlay_pdf = PdfReader(overlay_stream)
        page.merge_page(overlay_pdf.pages[0])
        writer.add_page(page)

    out_name = f"signed_{uuid.uuid4().hex}.pdf"
    out_path = os.path.join(SIGNATURES_DIR, out_name)
    with open(out_path, "wb") as f:
        writer.write(f)

    return out_path


@app.route("/api/register", methods=["POST"])
def register():
    try:
        payload = request.get_json(silent=True) or {}
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        full_name = (payload.get("full_name") or "").strip()
        nip = (payload.get("nip") or "").strip()

        if not username or not password or not full_name or not nip:
            return error_response("Field wajib: username, password, full_name, nip.", 400)

        if find_user_by_username(username):
            return error_response("Username sudah digunakan.", 400)

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

        uid = uuid.uuid4().hex
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        private_name = f"user_{uid}_private_{ts}.pem"
        public_name = f"user_{uid}_public_{ts}.pem"

        private_path = os.path.join(KEYS_DIR, private_name)
        public_path = os.path.join(KEYS_DIR, public_name)

        with open(private_path, "wb") as f:
            f.write(private_pem)
        with open(public_path, "wb") as f:
            f.write(public_pem)

        db = load_users_db()
        db["users"].append(
            {
                "id": uid,
                "username": username,
                "password_hash": generate_password_hash(password),
                "full_name": full_name,
                "nip": nip,
                "private_key_path": private_path,
                "public_key_path": public_path,
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        )
        save_users_db(db)

        return jsonify(
            {
                "ok": True,
                "message": "Registrasi berhasil. Keypair ECDSA telah dibuat untuk akun.",
            }
        )
    except Exception:
        return error_response("Registrasi gagal.", 500)


@app.route("/api/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return error_response("Field wajib: username dan password.", 400)

    user = find_user_by_username(username)
    if not user or not check_password_hash(user.get("password_hash", ""), password):
        return error_response("Username atau password salah.", 401)

    session["user_id"] = user["id"]
    return jsonify(
        {
            "ok": True,
            "message": "Login berhasil.",
            "user": {
                "username": user["username"],
                "full_name": user["full_name"],
                "nip": user["nip"],
            },
        }
    )


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True, "message": "Logout berhasil."})


@app.route("/api/me", methods=["GET"])
def me():
    user = ensure_logged_in()
    if not user:
        return jsonify({"ok": True, "authenticated": False})

    return jsonify(
        {
            "ok": True,
            "authenticated": True,
            "user": {
                "username": user["username"],
                "full_name": user["full_name"],
                "nip": user["nip"],
            },
        }
    )


@app.route("/api/my-keys", methods=["GET"])
def my_keys():
    user = ensure_logged_in()
    if not user:
        return error_response("Harus login terlebih dahulu.", 401)

    try:
        private_key_pem = read_file_bytes(user["private_key_path"]).decode("utf-8")
        public_key_pem = read_file_bytes(user["public_key_path"]).decode("utf-8")

        return jsonify(
            {
                "ok": True,
                "private_key": {
                    "filename": os.path.basename(user["private_key_path"]),
                    "content": private_key_pem,
                },
                "public_key": {
                    "filename": os.path.basename(user["public_key_path"]),
                    "content": public_key_pem,
                },
            }
        )
    except Exception:
        return error_response("Gagal mengambil key milik user.", 500)


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
# Menandatangani hash PDF menggunakan private key user login, menyimpan signature, dan menyiapkan QR.
def sign_pdf():
    user = ensure_logged_in()
    if not user:
        return error_response("Harus login terlebih dahulu.", 401)

    pdf_file = request.files.get("pdf")
    if pdf_file is None:
        return error_response("Field wajib: pdf.")

    try:
        pdf_path, original_pdf_name = save_uploaded_file(pdf_file, UPLOADS_DIR, must_be_pdf=True)

        sig_id = uuid.uuid4().hex
        created_at_utc = datetime.now(timezone.utc)
        expires_at_utc = (created_at_utc + timedelta(days=SIGNATURE_EXPIRE_DAYS_DEFAULT)).isoformat()

        qr_payload = {
            "type": "ECDSA_SIGNATURE",
            "signature_id": sig_id,
            "expires_at_utc": expires_at_utc,
            "signer": {
                "full_name": user["full_name"],
                "nip": user["nip"],
                "username": user["username"],
            },
        }

        qr_png_bytes = create_qr_png_bytes(qr_payload)
        qr_data_uri = "data:image/png;base64," + base64.b64encode(qr_png_bytes).decode("utf-8")

        qr_x_ratio = parse_ratio(request.form.get("qr_x_ratio"), 0.03)
        qr_y_ratio = parse_ratio(request.form.get("qr_y_ratio"), 0.05)

        signer_name_input = (request.form.get("signer_name") or "").strip()
        signer_nip_input = (request.form.get("signer_nip") or "").strip()
        signer_name = signer_name_input if signer_name_input else user["full_name"]
        signer_nip = signer_nip_input if signer_nip_input else user["nip"]

        signed_location_input = (request.form.get("signed_location") or "").strip()
        final_location = signed_location_input if signed_location_input else "Jimbaran"
        date_local = created_at_utc.astimezone(timezone(timedelta(hours=7)))
        date_local_str = format_indonesian_date(date_local)
        signed_location_date = f"{final_location}, {date_local_str}"

        # Guard agar variabel selalu tersedia walau ada mismatch runtime/cached code path
        if "signed_location_date" not in locals() or not signed_location_date:
            fallback_location = signed_location_input if signed_location_input else "Jimbaran"
            signed_location_date = f"{fallback_location}, {date_local_str}"

        signed_pdf_path = build_signed_pdf_with_qr_and_name(
            pdf_path,
            qr_png_bytes,
            signer_name,
            signer_nip=signer_nip,
            qr_x_ratio=qr_x_ratio,
            qr_y_ratio=qr_y_ratio,
            signed_location_date=signed_location_date,
        )
        signed_pdf_bytes = read_file_bytes(signed_pdf_path)
        signed_pdf_hash_hex = sha256_hex(signed_pdf_bytes)

        private_key_pem = read_file_bytes(user["private_key_path"])
        private_key = load_private_key_from_pem_bytes(private_key_pem)

        signature = private_key.sign(
            signed_pdf_hash_hex.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        sig_payload = {
            "signature_id": sig_id,
            "algorithm": "ECDSA",
            "curve": "SECP256R1",
            "hash_algorithm": "SHA256",
            "document_name": original_pdf_name,
            "signed_pdf_filename": os.path.basename(signed_pdf_path),
            "document_hash_hex": signed_pdf_hash_hex,
            "signature_b64": signature_b64,
            "created_at_utc": created_at_utc.isoformat(),
            "expires_at_utc": expires_at_utc,
            "signer": {
                "user_id": user["id"],
                "username": user["username"],
                "full_name": user["full_name"],
                "nip": user["nip"],
            },
        }

        sig_name = f"signature_{sig_id}.sig.json"
        sig_path = os.path.join(SIGNATURES_DIR, sig_name)
        with open(sig_path, "w", encoding="utf-8") as f:
            json.dump(sig_payload, f, ensure_ascii=False, indent=2)

        return jsonify(
            {
                "ok": True,
                "message": "PDF berhasil ditandatangani. File PDF hasil sign sudah berisi QR dan nama dosen sesuai posisi yang dipilih.",
                "signature": {
                    "filename": sig_name,
                    "content": json.dumps(sig_payload, ensure_ascii=False, indent=2),
                },
                "signed_pdf": {
                    "filename": os.path.basename(signed_pdf_path),
                    "content_base64": base64.b64encode(signed_pdf_bytes).decode("utf-8"),
                },
                "qr": {
                    "payload": qr_payload,
                    "image_data_uri": qr_data_uri,
                    "placement_hint": "QR ditempel sesuai posisi drag-and-drop yang Anda pilih pada form sign.",
                },
            }
        )
    except ValueError as ve:
        return error_response(str(ve), 400)
    except Exception as e:
        return error_response(f"Proses sign gagal: {str(e)}", 400)


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

        public_key.verify(
            signature,
            signed_hash_hex.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )

        expired, expires_dt = is_signature_expired(sig_payload.get("expires_at_utc"))
        if expired:
            return jsonify(
                {
                    "ok": True,
                    "valid": False,
                    "reason": "Signature expired (masa berlaku habis).",
                    "details": {
                        "expired": True,
                        "expires_at_utc": expires_dt.isoformat() if expires_dt else sig_payload.get("expires_at_utc"),
                        "current_hash": current_pdf_hash_hex,
                        "signed_hash": signed_hash_hex,
                    },
                    "signer": sig_payload.get("signer"),
                }
            )

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
                    "signer": sig_payload.get("signer"),
                }
            )

        return jsonify(
            {
                "ok": True,
                "valid": True,
                "reason": "Signature valid dan PDF tidak berubah.",
                "details": {
                    "hash": current_pdf_hash_hex,
                    "expired": False,
                    "expires_at_utc": sig_payload.get("expires_at_utc"),
                },
                "signer": sig_payload.get("signer"),
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


@app.route("/api/verify-qr", methods=["POST"])
def verify_qr():
    try:
        payload = request.get_json(silent=True) or {}
        signature_id = (payload.get("signature_id") or "").strip()
        signer = payload.get("signer") or {}

        if not signature_id:
            return error_response("Field wajib: signature_id.", 400)

        sig_path = os.path.join(SIGNATURES_DIR, f"signature_{signature_id}.sig.json")
        if not os.path.exists(sig_path):
            return jsonify(
                {
                    "ok": True,
                    "valid": False,
                    "reason": "Signature ID dari QR tidak ditemukan.",
                }
            )

        with open(sig_path, "r", encoding="utf-8") as f:
            sig_payload = json.load(f)

        stored_signer = sig_payload.get("signer") or {}

        expired, expires_dt = is_signature_expired(sig_payload.get("expires_at_utc"))
        if expired:
            return jsonify(
                {
                    "ok": True,
                    "valid": False,
                    "reason": "Signature expired (masa berlaku habis).",
                    "data": {
                        "signature_id": signature_id,
                        "stored_signer": stored_signer,
                        "scanned_signer": signer,
                        "mismatch_fields": [],
                        "document_name": sig_payload.get("document_name"),
                        "created_at_utc": sig_payload.get("created_at_utc"),
                        "expires_at_utc": expires_dt.isoformat() if expires_dt else sig_payload.get("expires_at_utc"),
                        "expired": True,
                    },
                }
            )

        expected_name = (stored_signer.get("full_name") or "").strip()
        expected_nip = (stored_signer.get("nip") or "").strip()
        expected_username = (stored_signer.get("username") or "").strip()

        given_name = (signer.get("full_name") or "").strip()
        given_nip = (signer.get("nip") or "").strip()
        given_username = (signer.get("username") or "").strip()

        mismatch_fields = []
        if expected_name != given_name:
            mismatch_fields.append("full_name")
        if expected_nip != given_nip:
            mismatch_fields.append("nip")
        if expected_username != given_username:
            mismatch_fields.append("username")

        signer_match = len(mismatch_fields) == 0

        return jsonify(
            {
                "ok": True,
                "valid": signer_match,
                "reason": "Data signer cocok." if signer_match else "Data signer tidak cocok.",
                "data": {
                    "signature_id": signature_id,
                    "stored_signer": stored_signer,
                    "scanned_signer": signer,
                    "mismatch_fields": mismatch_fields,
                    "document_name": sig_payload.get("document_name"),
                    "created_at_utc": sig_payload.get("created_at_utc"),
                    "expires_at_utc": sig_payload.get("expires_at_utc"),
                    "expired": False,
                },
            }
        )
    except Exception:
        return error_response("Verifikasi QR gagal.", 400)


@app.errorhandler(413)
# Menangani request dengan ukuran payload melebihi batas maksimum upload.
def request_entity_too_large(_):
    return error_response("Ukuran file terlalu besar. Maksimal 20 MB.", 413)


if __name__ == "__main__":
    app.run(debug=True)
