/**
 * Menampilkan hasil ke elemen target dengan tipe status (success/error).
 */
function showResult(el, message, type = "success") {
  el.classList.remove("hidden", "success", "error");
  el.classList.add(type);
  el.textContent = message;
}

/**
 * Membersihkan isi elemen hasil dan menyembunyikannya dari tampilan.
 */
function clearResult(el) {
  el.classList.add("hidden");
  el.classList.remove("success", "error");
  el.textContent = "";
  el.innerHTML = "";
}

/**
 * Membuat file sementara dari konten string lalu memicu download di browser.
 */
function downloadBlob(filename, content, mimeType = "text/plain") {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Memvalidasi file PDF wajib terisi dan berekstensi .pdf.
 */
function validatePdfFile(file) {
  if (!file) return "File PDF wajib diisi.";
  const name = (file.name || "").toLowerCase();
  if (!name.endsWith(".pdf")) return "File harus berekstensi .pdf.";
  return null;
}

/**
 * Memvalidasi file input umum yang wajib diisi.
 */
function validateRequiredFile(file, label) {
  if (!file) return `${label} wajib diisi.`;
  return null;
}

const btnGenerate = document.getElementById("btn-generate");
const generateResult = document.getElementById("generate-result");

const signForm = document.getElementById("sign-form");
const signResult = document.getElementById("sign-result");

const verifyForm = document.getElementById("verify-form");
const verifyResult = document.getElementById("verify-result");

/**
 * Handler tombol generate keypair:
 * - Memanggil endpoint backend
 * - Menampilkan status
 * - Menyediakan link download private/public key
 */
btnGenerate.addEventListener("click", async () => {
  clearResult(generateResult);

  try {
    const res = await fetch("/api/generate-keys", {
      method: "POST",
    });

    const data = await res.json();

    if (!res.ok || !data.ok) {
      showResult(generateResult, data.error || "Gagal generate keys.", "error");
      return;
    }

    generateResult.classList.remove("hidden", "error");
    generateResult.classList.add("success");
    generateResult.innerHTML = `
      <div>Keypair berhasil dibuat.</div>
      <div class="download-group">
        <a href="#" id="download-private" class="link-btn">Download Private Key</a>
        <a href="#" id="download-public" class="link-btn">Download Public Key</a>
      </div>
    `;

    // Handler download private key yang dihasilkan backend.
    document.getElementById("download-private").addEventListener("click", (e) => {
      e.preventDefault();
      downloadBlob(data.private_key.filename, data.private_key.content, "application/x-pem-file");
    });

    // Handler download public key yang dihasilkan backend.
    document.getElementById("download-public").addEventListener("click", (e) => {
      e.preventDefault();
      downloadBlob(data.public_key.filename, data.public_key.content, "application/x-pem-file");
    });
  } catch (err) {
    showResult(generateResult, "Terjadi kesalahan jaringan saat generate keys.", "error");
  }
});

/**
 * Handler submit form sign:
 * - Validasi input PDF + private key
 * - Kirim FormData ke endpoint /api/sign
 * - Tampilkan hasil dan link download signature
 */
signForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearResult(signResult);

  const pdf = document.getElementById("sign-pdf").files[0];
  const privateKey = document.getElementById("sign-private").files[0];

  const pdfErr = validatePdfFile(pdf);
  if (pdfErr) {
    showResult(signResult, pdfErr, "error");
    return;
  }

  const keyErr = validateRequiredFile(privateKey, "Private key");
  if (keyErr) {
    showResult(signResult, keyErr, "error");
    return;
  }

  const formData = new FormData();
  formData.append("pdf", pdf);
  formData.append("private_key", privateKey);

  try {
    const res = await fetch("/api/sign", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok || !data.ok) {
      showResult(signResult, data.error || "Sign gagal.", "error");
      return;
    }

    signResult.classList.remove("hidden", "error");
    signResult.classList.add("success");
    signResult.innerHTML = `
      <div>${data.message}</div>
      <div class="download-group">
        <a href="#" id="download-signature" class="link-btn">Download Signature</a>
      </div>
    `;

    // Handler download file signature JSON hasil proses signing.
    document.getElementById("download-signature").addEventListener("click", (ev) => {
      ev.preventDefault();
      downloadBlob(data.signature.filename, data.signature.content, "application/json");
    });
  } catch (err) {
    showResult(signResult, "Terjadi kesalahan jaringan saat sign PDF.", "error");
  }
});

/**
 * Handler submit form verify:
 * - Validasi input PDF + signature + public key
 * - Kirim FormData ke endpoint /api/verify
 * - Menampilkan status valid/invalid beserta detail hash bila tersedia
 */
verifyForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearResult(verifyResult);

  const pdf = document.getElementById("verify-pdf").files[0];
  const signature = document.getElementById("verify-signature").files[0];
  const publicKey = document.getElementById("verify-public").files[0];

  const pdfErr = validatePdfFile(pdf);
  if (pdfErr) {
    showResult(verifyResult, pdfErr, "error");
    return;
  }

  const sigErr = validateRequiredFile(signature, "Signature file");
  if (sigErr) {
    showResult(verifyResult, sigErr, "error");
    return;
  }

  const pubErr = validateRequiredFile(publicKey, "Public key");
  if (pubErr) {
    showResult(verifyResult, pubErr, "error");
    return;
  }

  const formData = new FormData();
  formData.append("pdf", pdf);
  formData.append("signature", signature);
  formData.append("public_key", publicKey);

  try {
    const res = await fetch("/api/verify", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();

    if (!res.ok || !data.ok) {
      showResult(verifyResult, data.error || "Verifikasi gagal.", "error");
      return;
    }

    if (data.valid) {
      showResult(
        verifyResult,
        `Status: VALID\n${data.reason}\nHash: ${data.details?.hash || "-"}`,
        "success"
      );
    } else {
      const signedHash = data.details?.signed_hash ? `\nSigned Hash: ${data.details.signed_hash}` : "";
      const currentHash = data.details?.current_hash ? `\nCurrent Hash: ${data.details.current_hash}` : "";
      showResult(
        verifyResult,
        `Status: INVALID\n${data.reason}${signedHash}${currentHash}`,
        "error"
      );
    }
  } catch (err) {
    showResult(verifyResult, "Terjadi kesalahan jaringan saat verifikasi PDF.", "error");
  }
});
