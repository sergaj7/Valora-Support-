"""
Valora OAuth2 Webserver (FIXED + ROLE SUPPORT + UI UPGRADE)
"""

import os
import json
import requests
from datetime import datetime, timezone
from flask import Flask, request, render_template_string
from dotenv import load_dotenv

load_dotenv()

# ── ENV ─────────────────────────────────────────────
CLIENT_ID     = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
WEB_BASE_URL  = os.getenv("WEB_BASE_URL", "")

GUILD_ID       = int(os.getenv("GUILD_ID", 0))
BOT_TOKEN      = os.getenv("DISCORD_TOKEN", "")
VERIFIED_ROLE_ID = int(os.getenv("VERIFIED_ROLE_ID", 0))

REDIRECT_URI = "https://valora-support-production.up.railway.app/callback"
VERIFIED_FILE = "verified.json"

app = Flask(__name__)

# ── STORAGE ─────────────────────────────────────────
def load_verified():
    if os.path.exists(VERIFIED_FILE):
        with open(VERIFIED_FILE, "r") as f:
            return json.load(f)
    return {}

def save_verified(data):
    with open(VERIFIED_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── DISCORD ROLE GIVER (IMPORTANT FIX) ─────────────
def give_role(user_id: str):
    if not BOT_TOKEN or VERIFIED_ROLE_ID == 0:
        print("⚠️ Missing BOT_TOKEN or VERIFIED_ROLE_ID")
        return

    url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{user_id}"

    res = requests.patch(
        url,
        headers={
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "roles": [VERIFIED_ROLE_ID]
        }
    )

    if res.status_code in (200, 204):
        print(f"✅ Role given to {user_id}")
    else:
        print(f"❌ Role error {res.status_code}: {res.text}")

# ── UI (MODERNIZED) ────────────────────────────────
SUCCESS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Verified — Valora</title>

<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">

<style>
:root{
--bg:#070A12;
--card:#111522;
--border:#1d2336;
--blue:#00BFFF;
--green:#00e5a0;
--text:#e6ecff;
--muted:#7a85a6;
}

*{margin:0;padding:0;box-sizing:border-box}

body{
background:radial-gradient(circle at top,#0b1224,#070A12);
color:var(--text);
font-family:'DM Sans',sans-serif;
height:100vh;
display:flex;
align-items:center;
justify-content:center;
}

.card{
background:linear-gradient(145deg,#121a2b,#0f1422);
border:1px solid var(--border);
border-radius:24px;
padding:50px;
width:420px;
text-align:center;
box-shadow:0 0 40px rgba(0,191,255,0.08);
animation:fade 0.5s ease;
}

@keyframes fade{
from{transform:translateY(10px);opacity:0}
to{transform:translateY(0);opacity:1}
}

.icon{
width:85px;
height:85px;
margin:0 auto 20px;
border-radius:50%;
background:rgba(0,229,160,0.08);
border:1px solid rgba(0,229,160,0.3);
display:flex;
align-items:center;
justify-content:center;
font-size:40px;
}

h1{
color:var(--green);
font-size:34px;
font-family:'Rajdhani',sans-serif;
}

.username{
margin:18px auto;
padding:8px 14px;
display:inline-block;
background:rgba(0,191,255,0.1);
border:1px solid rgba(0,191,255,0.25);
border-radius:10px;
color:var(--blue);
font-weight:600;
}

p{color:var(--muted);font-size:14px;margin-top:10px}
.small{font-size:12px;margin-top:20px;opacity:0.7}
</style>
</head>

<body>
<div class="card">
  <div class="icon">✅</div>
  <h1>Verified</h1>
  <div class="username">{{ username }}</div>
  <p>Your account is now linked to Valora.</p>
  <p class="small">You can close this tab</p>
</div>
</body>
</html>
"""

ERROR_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Error</title>
<style>
body{background:#070A12;color:white;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh}
.box{background:#111522;padding:40px;border-radius:20px;text-align:center;border:1px solid #2a3350}
h1{color:#ff5c5c}
p{color:#aaa}
</style>
</head>
<body>
<div class="box">
<h1>Verification Failed</h1>
<p>{{ error }}</p>
</div>
</body>
</html>
"""

# ── ROUTES ─────────────────────────────────────────

@app.route("/")
def home():
    return "<h2 style='text-align:center;color:white;font-family:sans-serif;margin-top:100px'>Valora OAuth Server ✅</h2>"

@app.route("/callback")
def callback():
    code = request.args.get("code")
    error = request.args.get("error")

    if error or not code:
        return render_template_string(ERROR_HTML, error="No authorization code"), 400

    # ── TOKEN ─────────────────────────────
    token_res = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if token_res.status_code != 200:
        return render_template_string(ERROR_HTML, error="Token exchange failed"), 500

    token_data = token_res.json()
    access_token = token_data.get("access_token")

    # ── USER ─────────────────────────────
    user_res = requests.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    user = user_res.json()
    uid = user["id"]
    username = user["username"]

    # ── SAVE ─────────────────────────────
    verified = load_verified()
    verified[uid] = {
        "username": username,
        "access_token": access_token,
        "verified_at": datetime.now(timezone.utc).isoformat()
    }
    save_verified(verified)

    # ── 🔥 ROLE FIX (IMPORTANT) ───────────
    give_role(uid)

    print(f"✅ VERIFIED: {username} ({uid})")

    return render_template_string(SUCCESS_HTML, username=username)

# ── RUN ───────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"OAuth running on {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
