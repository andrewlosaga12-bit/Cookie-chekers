from flask import Flask, request, jsonify, render_template_string, send_file, abort
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests, io
from datetime import datetime

app = Flask(__name__)

LAST_RESULTS = {"valid": [], "invalid": [], "timestamp": None}

# HTML + CSS langsung di-embed
HTML_TEMPLATE = """
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Roblox Cookie Checker</title>
<style>
:root {--bg:#0f1115;--card:#111218;--muted:#9aa0a6;--accent:#00ff95;}
*{box-sizing:border-box;font-family:Inter,system-ui,Segoe UI,Arial;}
body{margin:0;background:linear-gradient(180deg,#07070a,#0f1115);color:#e6eef3;min-height:100vh;}
.container{max-width:900px;margin:24px auto;padding:16px;}
h1{color:var(--accent);margin:8px 0;}
.subtitle{color:var(--muted);margin:0 0 12px;}
.card{background:var(--card);padding:12px;border-radius:10px;border:1px solid rgba(0,255,149,0.06);display:flex;gap:8px;align-items:center;}
input[type=file]{background:transparent;color:inherit;border:1px dashed rgba(255,255,255,0.08);padding:10px;border-radius:6px;}
button{background:var(--accent);color:#041014;border:none;padding:10px 14px;border-radius:8px;cursor:pointer;font-weight:600;}
.results{display:flex;gap:12px;margin-top:18px;flex-wrap:wrap;}
.box{flex:1;min-width:250px;background:#0b0c0f;padding:12px;border-radius:8px;border:1px solid rgba(255,255,255,0.03);}
pre{white-space:pre-wrap;word-break:break-word;max-height:360px;overflow:auto;color:#cfeede;}
.download{display:inline-block;margin-top:8px;padding:8px 10px;background:transparent;color:var(--accent);text-decoration:none;border-radius:6px;border:1px solid rgba(0,255,149,0.12);}
footer{margin-top:18px;color:var(--muted);font-size:12px;}
</style>
</head>
<body>
  <main class="container">
    <h1>Roblox Cookie Checker</h1>
    <p class="subtitle">Upload <code>data.txt</code> lalu klik <b>Check Cookies</b>.</p>
    <div class="card">
      <input id="fileInput" type="file" accept=".txt" />
      <button id="checkBtn">Check Cookies</button>
    </div>
    <div class="results">
      <section class="box">
        <h2>✅ Valid Cookies</h2>
        <pre id="validBox">Menunggu...</pre>
        <a id="dlValid" class="download" style="display:none">Download Valid</a>
      </section>
      <section class="box">
        <h2>❌ Invalid Cookies</h2>
        <pre id="invalidBox">Menunggu...</pre>
        <a id="dlInvalid" class="download" style="display:none">Download Invalid</a>
      </section>
    </div>
    <footer>
      <small>⚠️ Jangan upload cookie milik orang lain.</small>
    </footer>
  </main>
<script>
document.getElementById("checkBtn").addEventListener("click", async () => {
  const fi = document.getElementById("fileInput");
  if (!fi.files.length) { alert("Pilih file data.txt dulu"); return; }

  const fd = new FormData();
  fd.append("file", fi.files[0]);

  const checkBtn = document.getElementById("checkBtn");
  checkBtn.disabled = true;
  checkBtn.textContent = "Memeriksa...";

  try {
    const res = await fetch("/check", { method: "POST", body: fd });
    const data = await res.json();
    if (res.status !== 200) {
      alert(data.error || "Gagal memeriksa");
      document.getElementById("validBox").textContent = "Tidak ada hasil";
      document.getElementById("invalidBox").textContent = "Tidak ada hasil";
      return;
    }
    document.getElementById("validBox").textContent = data.valid.length ? data.valid.join("\\n\\n") : "Tidak ada cookie valid";
    document.getElementById("invalidBox").textContent = data.invalid.length ? data.invalid.join("\\n\\n") : "Tidak ada cookie invalid";

    const dlV = document.getElementById("dlValid");
    const dlI = document.getElementById("dlInvalid");
    dlV.style.display = data.valid.length ? "inline-block" : "none";
    dlI.style.display = data.invalid.length ? "inline-block" : "none";
    dlV.href = "/download/valid";
    dlI.href = "/download/invalid";
  } catch (err) {
    alert("Error: " + err.message);
  } finally {
    checkBtn.disabled = false;
    checkBtn.textContent = "Check Cookies";
  }
});
</script>
</body>
</html>
"""

def check_one_cookie(cookie):
    cookie = cookie.strip()
    if len(cookie) < 80:
        return False, cookie, ""
    headers = {
        "Cookie": f".ROBLOSECURITY={cookie}",
        "User-Agent": "Roblox/WinInet",
        "Accept": "application/json",
        "Referer": "https://www.roblox.com/"
    }
    try:
        r = requests.get("https://users.roblox.com/v1/users/authenticated", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            username = data.get("name") or "Unknown"
            return True, cookie, username
        else:
            return False, cookie, ""
    except:
        return False, cookie, ""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/check", methods=["POST"])
def check():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file uploaded"}), 400
    cookies = file.read().decode("utf-8", errors="ignore").splitlines()
    cookies = list({c.strip() for c in cookies if c.strip()})

    valid, invalid = [], []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = [ex.submit(check_one_cookie, c) for c in cookies]
        for fut in as_completed(futures):
            ok, token, username = fut.result()
            if ok:
                valid.append(f"{token}  -->  [{username}]")
            else:
                invalid.append(token)

    LAST_RESULTS["valid"] = valid
    LAST_RESULTS["invalid"] = invalid
    LAST_RESULTS["timestamp"] = datetime.utcnow().isoformat() + "Z"

    return jsonify(LAST_RESULTS)

@app.route("/download/<which>", methods=["GET"])
def download(which):
    if which not in ("valid", "invalid"):
        abort(404)
    data = LAST_RESULTS.get(which, [])
    b = "\n".join(data).encode("utf-8")
    name = f"{which}_cookies.txt"
    return send_file(io.BytesIO(b), mimetype="text/plain", as_attachment=True, download_name=name)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
