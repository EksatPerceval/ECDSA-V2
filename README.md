# ECDSA PDF Digital Signature - Full Stack App

Aplikasi full-stack untuk tanda tangan digital PDF menggunakan **ECDSA** dengan backend Python (Flask) dan frontend HTML/CSS/JS.

## Fitur Utama

- Registrasi & login user (session-based auth)
- Generate keypair ECDSA otomatis saat registrasi user
- Sign PDF menggunakan private key milik user yang sedang login
- Embed QR code ke PDF hasil sign
- Atur posisi QR dengan drag-and-drop pada preview halaman terakhir PDF
- Verify signature PDF dengan public key
- Verify payload QR signer (`/api/verify-qr`)
- Deteksi perubahan konten PDF via hash (mismatch => invalid)
- Dukungan expiry signature (masa berlaku)

## Format Blok Tanda Tangan pada PDF

Saat proses sign, blok pada PDF hasil sign mengikuti format terbaru:

- Lokasi default: **Jimbaran** (jika lokasi tidak diisi)
- Format tanggal: nama bulan Indonesia (contoh: **1 Juli 2026**)
- Label jabatan: **Pembimbing Akademik** (non-bold)
- Teks **QR CODE SIGNED** dihapus
- Nama pembimbing digarisbawahi (underline)
- Konten blok (teks + QR) rata tengah (center align)

## Struktur Proyek

- `app.py` : Flask backend + API + proses sign/verify PDF
- `templates/index.html` : UI utama
- `static/style.css` : styling frontend
- `static/app.js` : logic frontend (auth, sign, verify, preview, drag-drop)
- `requirements.txt` : dependency Python
- `storage/` : folder runtime
  - `storage/keys`
  - `storage/uploads`
  - `storage/signatures`
  - `storage/db`

## Cara Menjalankan

1. Buat virtual environment:
   - `python -m venv .venv`
   - `.venv\Scripts\activate`
2. Install dependency:
   - `pip install -r requirements.txt`
3. Jalankan aplikasi:
   - `python app.py`
4. Buka browser:
   - `http://127.0.0.1:5000`

## Alur Penggunaan Terbaru

1. Register akun (nama, NIP, username, password)
2. Login akun
3. Upload PDF pada menu **Sign PDF**
4. (Opsional) Atur posisi QR via drag-drop pada preview
5. Klik **Sign Dokumen** untuk menghasilkan:
   - Signed PDF
   - Signature JSON
   - QR payload
6. Verifikasi dokumen:
   - **Verify Signature PDF** untuk validasi kriptografi & hash
   - **Verify QR Signer** untuk validasi payload QR terhadap data signature tersimpan

## Endpoint API Ringkas

- `POST /api/register`
- `POST /api/login`
- `POST /api/logout`
- `GET /api/me`
- `GET /api/my-keys`
- `POST /api/sign`
- `POST /api/verify`
- `POST /api/verify-qr`

## Catatan

- Maksimum upload file: 20 MB
- Format PDF wajib `.pdf` pada endpoint sign/verify PDF
- Simpan `FLASK_SECRET_KEY` yang aman untuk production
