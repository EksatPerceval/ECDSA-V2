# ECDSA PDF Digital Signature - Full Stack App

Aplikasi full-stack untuk tanda tangan digital PDF menggunakan **ECDSA** dengan backend Python (Flask) dan frontend HTML/CSS/JS modern minimalis.

## Fitur

- Generate keypair ECDSA (private/public key)
- Sign file PDF
- Verify PDF + signature
- Deteksi modifikasi konten PDF (hash mismatch => INVALID)
- Validasi input aman dan handling error jelas

## Struktur

- `app.py` : Flask backend + API
- `templates/index.html` : UI utama
- `static/style.css` : styling modern minimalis
- `static/app.js` : logic frontend
- `requirements.txt` : dependency Python
- Folder runtime:
  - `storage/keys`
  - `storage/uploads`
  - `storage/signatures`

## Cara Menjalankan

1. Buat virtual env:
   - Windows CMD:
     - `python -m venv .venv`
     - `.venv\Scripts\activate`
2. Install dependency:
   - `pip install -r requirements.txt`
3. Jalankan:
   - `python app.py`
4. Buka browser:
   - `http://127.0.0.1:5000`

## Alur

1. Generate keys
2. Upload PDF + private key untuk sign
3. Upload PDF + signature + public key untuk verify

Jika PDF berubah setelah sign, verifikasi akan gagal.
