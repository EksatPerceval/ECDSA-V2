# ECDSA PDF Digital Signature - Full Stack App (Dokumentasi Super Lengkap)

Aplikasi full-stack untuk tanda tangan digital PDF menggunakan **ECDSA** dengan backend **Flask** dan frontend **HTML/CSS/JavaScript**.  
Dokumen ini menjelaskan **alur sistem lengkap dari awal sampai akhir**, termasuk **alur data, alur file, lokasi penyimpanan key**, dan fungsi/kode penting yang dipakai aplikasi.

---

## Daftar Isi

1. [Ringkasan Tujuan Sistem](#ringkasan-tujuan-sistem)
2. [Arsitektur Tingkat Tinggi](#arsitektur-tingkat-tinggi)
3. [Struktur Proyek](#struktur-proyek)
4. [Cara Menjalankan Aplikasi](#cara-menjalankan-aplikasi)
5. [Alur Aplikasi End-to-End (Sangat Detail)](#alur-aplikasi-end-to-end-sangat-detail)
6. [Lifecycle Data & Lokasi File Nyata](#lifecycle-data--lokasi-file-nyata)
7. [Key Management Detail (Private/Public Key Disimpan di Mana)](#key-management-detail-privatepublic-key-disimpan-di-mana)
8. [Alur Kriptografi ECDSA yang Dipakai](#alur-kriptografi-ecdsa-yang-dipakai)
9. [Kontrak Endpoint API](#kontrak-endpoint-api)
10. [Fungsi/Kode Penting di Backend (`app.py`)](#fungsikode-penting-di-backend-apppy)
11. [Fungsi/Kode Penting di Frontend (`static/app.js`)](#fungsikode-penting-di-frontend-staticappjs)
12. [Flow Sign PDF (Langkah Internal)](#flow-sign-pdf-langkah-internal)
13. [Flow Verify PDF (Langkah Internal)](#flow-verify-pdf-langkah-internal)
14. [Flow Verify QR (Langkah Internal)](#flow-verify-qr-langkah-internal)
15. [Skenario Validasi (Valid/Invalid)](#skenario-validasi-validinvalid)
16. [Keamanan yang Sudah Diterapkan](#keamanan-yang-sudah-diterapkan)
17. [Troubleshooting](#troubleshooting)
18. [Checklist Uji Cepat](#checklist-uji-cepat)

---

## Ringkasan Tujuan Sistem

Sistem ini memungkinkan user (mis. dosen) untuk:

- Registrasi akun dan otomatis mendapat keypair ECDSA.
- Login dan melakukan sign PDF tanpa upload private key manual.
- Menyisipkan QR code + identitas signer di PDF hasil sign.
- Verifikasi signature PDF dengan public key.
- Verifikasi QR payload untuk mengecek identitas signer.
- Mendeteksi perubahan isi dokumen lewat hash mismatch.
- Menolak signature jika sudah expired.

---

## Arsitektur Tingkat Tinggi

**Frontend (Browser)**  
⬇ kirim request API  
**Flask Backend (`app.py`)**  
⬇ baca/tulis file  
**Storage lokal (`storage/`)**

### Komponen Utama

- `templates/index.html`: halaman UI.
- `static/app.js`: logic interaksi user + call API.
- `app.py`: semua endpoint + logic sign/verify + auth/session.
- `storage/`: persistence lokal (keys, signatures, uploads, users db).

---

## Struktur Proyek

```text
.
├── app.py
├── README.md
├── requirements.txt
├── templates/
│   └── index.html
├── static/
│   ├── app.js
│   └── style.css
└── storage/
    ├── db/
    │   └── users.json
    ├── keys/
    ├── signatures/
    └── uploads/
```

---

## Cara Menjalankan Aplikasi

## 1) Buat virtual environment

Windows (CMD/PowerShell):

```bash
python -m venv .venv
.venv\Scripts\activate
```

## 2) Install dependency

```bash
pip install -r requirements.txt
```

## 3) Jalankan server Flask

```bash
python app.py
```

Default:

- `http://127.0.0.1:5000`

Alternatif port:

```bash
python -c "import app; app.app.run(port=5001, debug=False)"
```

## 4) Akses aplikasi di browser

- `http://127.0.0.1:5000` (atau sesuai port)

---

## Alur Aplikasi End-to-End (Sangat Detail)

Di bawah ini urutan dari user pertama kali pakai sampai verifikasi.

## A. User membuka aplikasi

1. Browser request `GET /`.
2. Backend render `templates/index.html`.
3. Frontend load `static/app.js`.
4. `checkSession()` dipanggil:
   - call `GET /api/me`
   - jika belum login: UI tampil "Belum login."

---

## B. Registrasi akun (`POST /api/register`)

Input JSON:

- `full_name`
- `nip`
- `username`
- `password`

Langkah backend:

1. Validasi field wajib.
2. Cek username sudah ada atau belum.
3. Generate keypair ECDSA:
   - `private_key = ec.generate_private_key(ec.SECP256R1())`
   - `public_key = private_key.public_key()`
4. Serialize ke PEM.
5. Simpan ke disk:
   - private: `storage/keys/user_<uid>_private_<timestamp>.pem`
   - public: `storage/keys/user_<uid>_public_<timestamp>.pem`
6. Tambah user ke `storage/db/users.json`, termasuk path key.
7. Return sukses registrasi.

Output penting:

- User berhasil tersimpan.
- Keypair akun sudah ada di storage server.

---

## C. Login (`POST /api/login`)

Input JSON:

- `username`
- `password`

Langkah backend:

1. Ambil user dari `users.json`.
2. Verifikasi password hash (`check_password_hash`).
3. Jika valid:
   - set `session["user_id"] = user["id"]`.
4. Return data profil ringkas user.

Output penting:

- Session aktif (cookie session di browser/client).

---

## D. Ambil key publik user (`GET /api/my-keys`)

Langkah backend:

1. Pastikan user login (`ensure_logged_in()`).
2. Baca file public key dari path user.
3. Return:
   - `public_key.filename`
   - `public_key.content`

> **Catatan keamanan:** private key tidak dikirim.

---

## E. Sign PDF (`POST /api/sign`)

Input multipart/form-data:

- `pdf` (wajib)
- `qr_x_ratio`, `qr_y_ratio` (opsional posisi QR)
- `signer_name`, `signer_nip` (opsional override)

Langkah backend detail:

1. Pastikan user login.
2. Simpan file PDF upload ke `storage/uploads/<uuid>.pdf`.
3. Tentukan `signature_id` berbasis user: `user_<user_id>`.
4. Hitung `created_at_utc`, `expires_at_utc`.
5. Buat payload QR berisi:
   - type,
   - signature_id,
   - expiry,
   - identitas signer.
6. Generate QR PNG dari payload.
7. Tempel blok tanda tangan ke halaman terakhir PDF:
   - lokasi + tanggal
   - jabatan "Pembimbing Akademik"
   - QR
   - nama (underline)
   - NIP
8. Simpan signed PDF ke `storage/signatures/signed_<uuid>.pdf`.
9. Hitung hash SHA-256 signed PDF.
10. Baca private key user dari storage.
11. Sign hash menggunakan ECDSA SHA256.
12. Simpan signature JSON ke:

- `storage/signatures/signature_user_<user_id>.sig.json`

13. Return response:

- signed PDF (base64)
- signature JSON (string)
- QR payload + data URI image.

---

## F. Verify Signature PDF (`POST /api/verify`)

Input multipart/form-data:

- `pdf`
- `signature`
- `public_key`

Langkah backend:

1. Simpan 3 file ke `storage/uploads/`.
2. Hitung hash PDF yang diupload saat verify.
3. Parse signature JSON.
4. Validasi field signature wajib.
5. Decode `signature_b64`.
6. Load public key PEM.
7. Verifikasi kriptografi:
   - `public_key.verify(signature, signed_hash, ec.ECDSA(hashes.SHA256()))`
8. Cek expiry signature.
9. Cek hash match:
   - `current_pdf_hash == signed_hash`
10. Return hasil:

- valid true jika semua lolos,
- valid false + reason jika ada yang gagal.

---

## G. Verify QR (`POST /api/verify-qr`)

Input JSON:

- `signature_id`
- `signer` (full_name, nip, username)

Langkah backend:

1. Cari file signature berdasarkan `signature_id`.
2. Load signer tersimpan dari signature JSON.
3. Cek expiry.
4. Bandingkan field signer hasil scan vs signer tersimpan.
5. Return valid/invalid + field yang mismatch.

---

## Lifecycle Data & Lokasi File Nyata

Bagian ini menjawab pertanyaan: **data apa disimpan di mana**.

## 1) Database user

Lokasi:

- `storage/db/users.json`

Isi penting per user:

- `id`
- `username`
- `password_hash`
- `full_name`
- `nip`
- `private_key_path`
- `public_key_path`
- `created_at_utc`

Artinya, path file key per user direferensikan langsung di DB JSON.

## 2) File key

Lokasi folder:

- `storage/keys/`

Pattern nama:

- Private key user: `user_<uid>_private_<timestamp>.pem`
- Public key user: `user_<uid>_public_<timestamp>.pem`
- Key generated umum: `ecdsa_private_<timestamp>.pem`, `ecdsa_public_<timestamp>.pem`

## 3) File upload sementara

Lokasi:

- `storage/uploads/`

Contoh:

- PDF verify/sign sementara
- signature/public key yang diupload saat verify

## 4) File signature & signed PDF

Lokasi:

- `storage/signatures/`

Contoh:

- `signed_<uuid>.pdf`
- `signature_user_<user_id>.sig.json`

---

## Key Management Detail (Private/Public Key Disimpan di Mana)

Ini penjelasan spesifik dan lengkap:

## Private key disimpan di mana?

- Disimpan sebagai file PEM di:
  - `storage/keys/user_<uid>_private_<timestamp>.pem`
- Path private key disimpan di `users.json` pada field:
  - `private_key_path`

## Public key disimpan di mana?

- Disimpan sebagai file PEM di:
  - `storage/keys/user_<uid>_public_<timestamp>.pem`
- Path public key disimpan di `users.json` pada field:
  - `public_key_path`

## Kapan key dibuat?

1. Saat registrasi (`/api/register`) → otomatis keypair per user.
2. Saat endpoint `/api/generate-keys` dipanggil → generate pasangan key baru.

## Siapa yang bisa mengakses private key?

- Private key **hanya dipakai internal backend** saat sign.
- Endpoint API **tidak lagi mengekspos private key**.
- Tombol download private key di UI sudah dihapus.

## Kenapa private key tidak didownload?

- Mengurangi risiko kebocoran.
- Menjaga model server-side signing.
- Verifikasi tetap bisa karena hanya butuh public key.

---

## Alur Kriptografi ECDSA yang Dipakai

## 1) Key generation

Kurva:

- `SECP256R1`

## 2) Hashing dokumen

- SHA-256 dari **signed PDF bytes**

## 3) Signing

- Input yang ditandatangani: hash hex (encoded bytes)
- Algoritma: ECDSA + SHA256

## 4) Verifying

- Signature diverifikasi dengan public key.
- Setelah itu hash PDF saat ini dibandingkan dengan hash signed.
- Jadi terjamin:
  - keaslian signer (key cocok),
  - integritas file (hash cocok).

---

## Kontrak Endpoint API

## Auth

- `POST /api/register` (JSON)
- `POST /api/login` (JSON)
- `POST /api/logout`
- `GET /api/me`

## Key

- `GET /api/my-keys` → return **public_key saja**
- `POST /api/generate-keys` → return **public_key saja**

## Signature

- `POST /api/sign` (multipart)
- `POST /api/verify` (multipart)
- `POST /api/verify-qr` (JSON)

---

## Fungsi/Kode Penting di Backend (`app.py`)

## Helper penting

### `error_response(...)`

Standarisasi error JSON.

### `save_uploaded_file(...)`

Simpan file upload dengan nama aman + validasi PDF.

### `sha256_hex(...)`

Hash SHA-256 untuk integrity check.

### `ensure_logged_in()`

Validasi session login.

### `build_signed_pdf_with_qr_and_name(...)`

Membangun tampilan blok tanda tangan di halaman terakhir PDF.

## Endpoint penting

### `register()`

Generate keypair user + simpan path key ke DB.

### `login()`

Verifikasi credential + set session.

### `my_keys()`

Mengirim public key user login.

### `sign_pdf()`

Proses inti sign + generate signature JSON.

### `verify_pdf()`

Validasi signature, expiry, dan hash.

### `verify_qr()`

Validasi signer dari QR payload.

---

## Fungsi/Kode Penting di Frontend (`static/app.js`)

### `checkSession()`

Sinkronisasi UI berdasarkan status auth.

### `setAuthUI(user)`

Menampilkan tombol aksi sesuai user login (sekarang hanya public key + logout).

### `renderPdfPreview(file)`

Render halaman terakhir PDF memakai pdf.js.

### `initQrDragDrop()`

Drag-drop box QR di canvas preview.

### `getQrPlacementPayload()`

Mengirim posisi QR ratio ke backend saat sign.

### Handler submit:

- register form
- login form
- sign form
- verify form
- verify-qr form

---

## Flow Sign PDF (Langkah Internal)

1. Frontend kirim file + ratio QR.
2. Backend simpan upload.
3. Backend generate QR payload + QR image.
4. Backend overlay QR + nama ke PDF.
5. Backend hash PDF hasil overlay.
6. Backend sign hash pakai private key user.
7. Backend simpan signature JSON.
8. Frontend dapat file hasil untuk diunduh.

---

## Flow Verify PDF (Langkah Internal)

1. Frontend kirim PDF + signature + public key.
2. Backend parse signature.
3. Backend verifikasi ECDSA.
4. Backend cek expiry.
5. Backend bandingkan hash.
6. Backend kirim status valid/invalid + alasan.

---

## Flow Verify QR (Langkah Internal)

1. Frontend kirim payload hasil scan QR.
2. Backend ambil signature file berdasar `signature_id`.
3. Cocokkan signer payload vs signer tersimpan.
4. Return valid/invalid + mismatch field.

---

## Skenario Validasi (Valid/Invalid)

## Verify valid jika:

- signature cocok dengan public key,
- belum expired,
- hash PDF sama.

## Verify invalid jika:

- key mismatch,
- signature expired,
- hash mismatch (file berubah),
- signature file rusak/invalid JSON.

## QR valid jika:

- signature_id ditemukan,
- signer cocok,
- belum expired.

---

## Keamanan yang Sudah Diterapkan

- Password disimpan hashed.
- Session-based auth untuk aksi sign.
- Private key tidak diekspos API/UI.
- Validasi ukuran upload (max 20MB).
- Validasi ekstensi PDF pada endpoint terkait.
- Signature expiry check.
- Integritas dokumen berbasis hash.

---

## Troubleshooting

1. **Field wajib kosong**
   - Pastikan payload register/login dikirim JSON.

2. **Sign gagal karena belum login**
   - Lakukan login dulu agar session aktif.

3. **Verify invalid (key mismatch)**
   - Gunakan public key pasangan signer yang benar.

4. **Verify invalid (hash mismatch)**
   - File PDF kemungkinan berubah setelah sign.

5. **413 file terlalu besar**
   - Ukuran file melampaui 20MB.

---

## Checklist Uji Cepat

1. Register user baru.
2. Login user.
3. Cek `/api/my-keys` hanya return public key.
4. Sign satu PDF.
5. Download signed PDF + signature JSON.
6. Verify dengan public key yang benar → valid.
7. Verify dengan key lain / file diubah → invalid.
8. Verify QR payload → cek validasi signer.

---

## Ringkasan Utama (Poin Penting)

- Aplikasi memakai ECDSA untuk tanda tangan digital.
- Keypair terikat akun sejak registrasi.
- **Private key disimpan di server (`storage/keys/...private...pem`)** dan direferensikan dari `storage/db/users.json`.
- **Public key disimpan di server (`storage/keys/...public...pem`)** dan dapat didownload untuk verifikasi.
- Proses sign dilakukan server-side dengan private key internal.
- Verifikasi dilakukan dengan public key + validasi hash + cek expiry.
- Fitur download private key sudah dihapus untuk keamanan.
