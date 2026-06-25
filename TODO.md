# TODO - ECDSA Signing + QR Verification Upgrade

- [x] 1. Refactor backend data model untuk user account + session auth sederhana
- [x] 2. Implement register/login/logout endpoint
- [x] 3. Generate keypair otomatis saat registrasi user dan simpan terhubung akun
- [x] 4. Update sign endpoint agar memakai private key milik user login
- [x] 5. Simpan metadata signer (nama, NIP, user_id) ke signature payload
- [x] 6. Tambah QR payload generation dari data signature
- [x] 7. Tambah endpoint verifikasi QR payload terhadap data signature tersimpan
- [x] 8. Redesign UI modern elegan (auth + sign + verify + QR verify)
- [x] 9. Update frontend JS untuk alur auth, sign, verify, QR verify
- [x] 10. Jalankan pengujian critical-path
- [x] 11. Perbaiki bug dari hasil pengujian
- [ ] 12. Tambah fitur masa berlaku (expired) pada signature & QR verify
- [ ] 13. Jalankan pengujian ulang untuk skenario expired
- [ ] 14. Finalisasi dokumentasi singkat perubahan
