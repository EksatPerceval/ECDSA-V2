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

function downloadBase64Blob(filename, base64Content, mimeType = "application/octet-stream") {
  const binary = atob(base64Content);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes], { type: mimeType });
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

const registerForm = document.getElementById("register-form");
const registerResult = document.getElementById("register-result");

const loginForm = document.getElementById("login-form");
const loginResult = document.getElementById("login-result");

const sessionState = document.getElementById("session-state");
const sessionResult = document.getElementById("session-result");
const btnDownloadPrivate = document.getElementById("btn-download-private");
const btnDownloadPublic = document.getElementById("btn-download-public");
const btnLogout = document.getElementById("btn-logout");

const signForm = document.getElementById("sign-form");
const signResult = document.getElementById("sign-result");
const qrPreview = document.getElementById("qr-preview");
const qrImage = document.getElementById("qr-image");

const verifyForm = document.getElementById("verify-form");
const verifyResult = document.getElementById("verify-result");

const verifyQrForm = document.getElementById("verify-qr-form");
const verifyQrResult = document.getElementById("verify-qr-result");


function setAuthUI(user) {
  if (!user) {
    sessionState.textContent = "Belum login.";
    btnDownloadPrivate.classList.add("hidden");
    btnDownloadPublic.classList.add("hidden");
    btnLogout.classList.add("hidden");
    return;
  }

  sessionState.textContent = `Login sebagai: ${user.full_name} (${user.username}) · NIP: ${user.nip}`;
  btnDownloadPrivate.classList.remove("hidden");
  btnDownloadPublic.classList.remove("hidden");
  btnLogout.classList.remove("hidden");
}


async function checkSession() {
  clearResult(sessionResult);

  try {
    const res = await fetch("/api/me");
    const data = await res.json();

    if (!res.ok || !data.ok) {
      setAuthUI(null);
      return;
    }

    if (data.authenticated) {
      setAuthUI(data.user);
    } else {
      setAuthUI(null);
    }
  } catch (_e) {
    setAuthUI(null);
  }
}


registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearResult(registerResult);

  const payload = {
    full_name: (document.getElementById("register-full-name").value || "").trim(),
    nip: (document.getElementById("register-nip").value || "").trim(),
    username: (document.getElementById("register-username").value || "").trim(),
    password: document.getElementById("register-password").value || "",
  };

  if (!payload.full_name || !payload.nip || !payload.username || !payload.password) {
    showResult(registerResult, "Semua field registrasi wajib diisi.", "error");
    return;
  }

  try {
    const res = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok || !data.ok) {
      showResult(registerResult, data.error || "Registrasi gagal.", "error");
      return;
    }

    showResult(registerResult, data.message || "Registrasi berhasil.", "success");
    registerForm.reset();
  } catch (_err) {
    showResult(registerResult, "Terjadi kesalahan jaringan saat registrasi.", "error");
  }
});


loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearResult(loginResult);

  const payload = {
    username: (document.getElementById("login-username").value || "").trim(),
    password: document.getElementById("login-password").value || "",
  };

  if (!payload.username || !payload.password) {
    showResult(loginResult, "Username dan password wajib diisi.", "error");
    return;
  }

  try {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok || !data.ok) {
      showResult(loginResult, data.error || "Login gagal.", "error");
      return;
    }

    showResult(loginResult, data.message || "Login berhasil.", "success");
    setAuthUI(data.user);
    loginForm.reset();
  } catch (_err) {
    showResult(loginResult, "Terjadi kesalahan jaringan saat login.", "error");
  }
});


function resetAllUserInputsAndOutputs() {
  registerForm.reset();
  loginForm.reset();
  signForm.reset();
  verifyForm.reset();
  verifyQrForm.reset();

  clearResult(registerResult);
  clearResult(loginResult);
  clearResult(sessionResult);
  clearResult(signResult);
  clearResult(verifyResult);
  clearResult(verifyQrResult);

  qrImage.removeAttribute("src");
  qrPreview.classList.add("hidden");
}

async function downloadMyKeys(which) {
  clearResult(sessionResult);

  try {
    const res = await fetch("/api/my-keys");
    const data = await res.json();

    if (!res.ok || !data.ok) {
      showResult(sessionResult, data.error || "Gagal mengambil key user.", "error");
      return;
    }

    if (which === "private") {
      downloadBlob(data.private_key.filename, data.private_key.content, "application/x-pem-file");
      showResult(sessionResult, "Private key berhasil diunduh.", "success");
      return;
    }

    downloadBlob(data.public_key.filename, data.public_key.content, "application/x-pem-file");
    showResult(sessionResult, "Public key berhasil diunduh.", "success");
  } catch (_e) {
    showResult(sessionResult, "Terjadi kesalahan jaringan saat mengambil key.", "error");
  }
}

btnDownloadPrivate.addEventListener("click", () => downloadMyKeys("private"));
btnDownloadPublic.addEventListener("click", () => downloadMyKeys("public"));

btnLogout.addEventListener("click", async () => {
  clearResult(sessionResult);

  try {
    const res = await fetch("/api/logout", { method: "POST" });
    const data = await res.json();

    if (!res.ok || !data.ok) {
      showResult(sessionResult, data.error || "Logout gagal.", "error");
      return;
    }

    showResult(sessionResult, data.message || "Logout berhasil.", "success");
    setAuthUI(null);
    resetAllUserInputsAndOutputs();
  } catch (_e) {
    showResult(sessionResult, "Terjadi kesalahan jaringan saat logout.", "error");
  }
});


signForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearResult(signResult);

  const pdf = document.getElementById("sign-pdf").files[0];
  const pdfErr = validatePdfFile(pdf);
  if (pdfErr) {
    showResult(signResult, pdfErr, "error");
    return;
  }

  const formData = new FormData();
  formData.append("pdf", pdf);

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
        <a href="#" id="download-signed-pdf" class="link-btn">Download Signed PDF</a>
        <a href="#" id="download-signature" class="link-btn">Download Signature</a>
        <a href="#" id="download-qr-payload" class="link-btn">Download QR Payload</a>
      </div>
      <div class="placement-hint">${data.qr?.placement_hint || ""}</div>
    `;

    document.getElementById("download-signed-pdf").addEventListener("click", (ev) => {
      ev.preventDefault();
      downloadBase64Blob(data.signed_pdf.filename, data.signed_pdf.content_base64, "application/pdf");
    });

    document.getElementById("download-signature").addEventListener("click", (ev) => {
      ev.preventDefault();
      downloadBlob(data.signature.filename, data.signature.content, "application/json");
    });

    document.getElementById("download-qr-payload").addEventListener("click", (ev) => {
      ev.preventDefault();
      downloadBlob("qr_payload.json", JSON.stringify(data.qr?.payload || {}, null, 2), "application/json");
    });

    if (data.qr?.image_data_uri) {
      qrImage.src = data.qr.image_data_uri;
      qrPreview.classList.remove("hidden");
    } else {
      qrPreview.classList.add("hidden");
    }
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

verifyQrForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearResult(verifyQrResult);

  const raw = (document.getElementById("qr-payload").value || "").trim();
  if (!raw) {
    showResult(verifyQrResult, "QR payload wajib diisi.", "error");
    return;
  }

  let payload;
  try {
    payload = JSON.parse(raw);
  } catch (_e) {
    showResult(verifyQrResult, "QR payload harus JSON valid.", "error");
    return;
  }

  try {
    const res = await fetch("/api/verify-qr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok || !data.ok) {
      showResult(verifyQrResult, data.error || "Verifikasi QR gagal.", "error");
      return;
    }

    if (data.valid) {
      showResult(
        verifyQrResult,
        `Status: VALID\n${data.reason}\nSigner: ${data.data?.stored_signer?.full_name || "-"} (${data.data?.stored_signer?.nip || "-"})`,
        "success"
      );
    } else {
      showResult(
        verifyQrResult,
        `Status: INVALID\n${data.reason}`,
        "error"
      );
    }
  } catch (_e) {
    showResult(verifyQrResult, "Terjadi kesalahan jaringan saat verifikasi QR.", "error");
  }
});

checkSession();
