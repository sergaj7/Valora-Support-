"""
web.py — Valora OAuth2 Webserver
Handles Discord OAuth2, saves access tokens for backup/restore.
pip install flask requests python-dotenv
"""

import os
import json
import requests
from datetime import datetime, timezone
from flask import Flask, request, render_template_string
from dotenv import load_dotenv

load_dotenv()

# ── ENV ─────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
WEB_BASE_URL  = os.getenv("WEB_BASE_URL", "http://localhost:5000")

REDIRECT_URI = "https://valora-support-production.up.railway.app/callback"
VERIFIED_FILE = "verified.json"

app = Flask(__name__)

# ── STORAGE ────────────────────────────────────────────────
def load_verified():
    if os.path.exists(VERIFIED_FILE):
        with open(VERIFIED_FILE, "r") as f:
            return json.load(f)
    return {}

def save_verified(data):
    with open(VERIFIED_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── HTML ────────────────────────────────────────────────────
SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Verified — Valora</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--bg:#0b0d14;--card:#12151f;--border:#1c2035;--blue:#00BFFF;--green:#00e5a0;--text:#dde4f0;--muted:#5a6480}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}
.card{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:48px;text-align:center;max-width:460px;width:100%}
.icon{width:80px;height:80px;border-radius:50%;background:rgba(0,229,160,0.1);border:1px solid rgba(0,229,160,0.3);display:flex;align-items:center;justify-content:center;margin:0 auto 24px;font-size:36px}
h1{color:var(--green);font-size:32px}
.username{margin:16px 0;padding:6px 16px;background:rgba(0,191,255,0.1);border:1px solid rgba(0,191,255,0.2);border-radius:8px;color:var(--blue)}
p{color:var(--muted)}
</style>
</head>
<body>
<div class="card">
  <div class="icon">✅</div>
  <h1>Verified!</h1>
  <p>Your Discord account has been verified.</p>
  <div class="username">{{ username }}</div>
  <p>You can close this tab.</p>
</div>
</body>
</html>"""

ERROR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Error</title>
<style>
body{background:#0b0d14;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh}
.card{background:#12151f;padding:40px;border-radius:20px;text-align:center}
h1{color:#ff6b6b}
p{color:#aaa}
</style>
</head>
<body>
<div class="card">
<h1>Verification Failed</h1>
<p>{{ error }}</p>
<p>Please try again in Discord.</p>
</div>
</body>
</html>"""

# ── ROUTES ────────────────────────────────────────────────
@app.route("/")
def index():
    return "<h2 style='text-align:center;margin-top:100px;font-family:sans-serif'>Valora OAuth2 Server ✅</h2>"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    error = request.args.get("error")

    if error or not code:
        return render_template_string(ERROR_HTML, error="Authorization cancelled or missing code"), 400

    # ── TOKEN EXCHANGE ───────────────────────────────
    token_res = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )

    if token_res.status_code != 200:
        return render_template_string(ERROR_HTML, error=f"Token exchange failed ({token_res.status_code})"), 500

    token_data = token_res.json()
    access_token = token_data.get("access_token")

    if not access_token:
        return render_template_string(ERROR_HTML, error="No access token received"), 500

    # ── USER INFO ─────────────────────────────────────
    user_res = requests.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    if user_res.status_code != 200:
        return render_template_string(ERROR_HTML, error="Failed to fetch user"), 500

    user = user_res.json()
    uid = user["id"]
    name = user.get("username", "unknown")

    # ── SAVE DATA ────────────────────────────────────
    verified = load_verified()
    verified[uid] = {
        "username": name,
        "access_token": access_token,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "token_expired": False
    }
    save_verified(verified)

    print(f"[VERIFY] {name} ({uid}) verified")

    return render_template_string(SUCCESS_HTML, username=name)


# ── START ────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"Valora OAuth running on {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
