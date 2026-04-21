"""
Valora Web Server — OAuth2 Verify + Staff Application Form
Railway deployment
"""

import os
import json
import uuid
import requests
from datetime import datetime, timezone
from flask import Flask, request, render_template_string, redirect
from dotenv import load_dotenv

load_dotenv()

# ── ENV ──────────────────────────────────────────────────────
CLIENT_ID        = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET    = os.getenv("DISCORD_CLIENT_SECRET", "")
WEB_BASE_URL     = os.getenv("WEB_BASE_URL", "https://valora-support-production.up.railway.app")

GUILD_ID         = int(os.getenv("GUILD_ID", 0))
BOT_TOKEN        = os.getenv("DISCORD_TOKEN", "")
VERIFIED_ROLE_ID = int(os.getenv("VERIFIED_ROLE_ID", 0))

REDIRECT_URI      = "https://valora-support-production.up.railway.app/callback"
APPLY_OAUTH_URI   = "https://valora-support-production.up.railway.app/apply/callback"

VERIFIED_FILE     = "verified.json"
APPLICATIONS_FILE = "applications.json"

app = Flask(__name__)

# ── STORAGE ──────────────────────────────────────────────────
def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ── DISCORD HELPERS ──────────────────────────────────────────
def give_role(user_id: str):
    if not BOT_TOKEN or VERIFIED_ROLE_ID == 0:
        print("⚠️ Missing BOT_TOKEN or VERIFIED_ROLE_ID")
        return
    url = f"https://discord.com/api/v10/guilds/{GUILD_ID}/members/{user_id}"
    res = requests.patch(url,
        headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
        json={"roles": [VERIFIED_ROLE_ID]}
    )
    if res.status_code in (200, 204):
        print(f"✅ Role given to {user_id}")
    else:
        print(f"❌ Role error {res.status_code}: {res.text}")


def exchange_code(code: str, redirect_uri: str) -> dict | None:
    """Exchange OAuth2 code for token data. Returns token dict or None."""
    res = requests.post(
        "https://discord.com/api/v10/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    if res.status_code != 200:
        print(f"❌ Token exchange failed: {res.status_code} {res.text}")
        return None
    return res.json()


def get_discord_user(access_token: str) -> dict | None:
    """Fetch the Discord user from an access token."""
    res = requests.get(
        "https://discord.com/api/v10/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if res.status_code != 200:
        return None
    return res.json()


# ── SHARED CSS / DESIGN TOKENS ───────────────────────────────
BASE_STYLE = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&display=swap" rel="stylesheet">
<style>
:root {
  --bg:      #070A12;
  --card:    #0e1220;
  --card2:   #111828;
  --border:  #1c2438;
  --border2: #243050;
  --blue:    #00BFFF;
  --blue2:   #0099cc;
  --green:   #00e5a0;
  --red:     #ff4d4d;
  --gold:    #FFD700;
  --text:    #dde6ff;
  --muted:   #6a779a;
  --input:   #0c1220;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'DM Sans', sans-serif;
  font-size: 15px;
  line-height: 1.6;
  min-height: 100vh;
}
a { color: var(--blue); text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── NOISE OVERLAY ── */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
  pointer-events: none;
  z-index: 0;
}

/* ── GLOW BLOB ── */
body::after {
  content: '';
  position: fixed;
  top: -200px; left: 50%;
  transform: translateX(-50%);
  width: 700px; height: 400px;
  background: radial-gradient(ellipse, rgba(0,191,255,0.07) 0%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}

.page-wrap {
  position: relative;
  z-index: 1;
  max-width: 680px;
  margin: 0 auto;
  padding: 40px 20px 80px;
}

/* ── HEADER ── */
.site-header {
  text-align: center;
  margin-bottom: 40px;
}
.logo-ring {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 72px; height: 72px;
  border-radius: 50%;
  border: 1.5px solid rgba(0,191,255,0.35);
  background: rgba(0,191,255,0.06);
  font-size: 32px;
  margin-bottom: 14px;
}
.site-header h1 {
  font-family: 'Rajdhani', sans-serif;
  font-size: 30px;
  font-weight: 700;
  color: var(--blue);
  letter-spacing: 2px;
  text-transform: uppercase;
}
.site-header p {
  color: var(--muted);
  font-size: 13px;
  margin-top: 4px;
}

/* ── CARD ── */
.card {
  background: linear-gradient(160deg, var(--card) 0%, var(--card2) 100%);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 36px 40px;
  box-shadow: 0 8px 40px rgba(0,0,0,0.4), 0 0 0 1px rgba(0,191,255,0.04);
  animation: slideUp 0.4s ease both;
}
@keyframes slideUp {
  from { transform: translateY(16px); opacity: 0; }
  to   { transform: translateY(0);    opacity: 1; }
}

/* ── FORM ── */
.form-section {
  margin-bottom: 28px;
}
.section-title {
  font-family: 'Rajdhani', sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--blue);
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}
.form-row {
  display: grid;
  gap: 14px;
  margin-bottom: 14px;
}
.form-row.cols-2 { grid-template-columns: 1fr 1fr; }
.form-group { display: flex; flex-direction: column; gap: 6px; }
label {
  font-size: 13px;
  font-weight: 500;
  color: var(--muted);
  letter-spacing: 0.3px;
}
label .req { color: var(--blue); margin-left: 2px; }

input[type="text"],
input[type="number"],
select,
textarea {
  background: var(--input);
  border: 1px solid var(--border2);
  border-radius: 10px;
  padding: 11px 14px;
  color: var(--text);
  font-family: 'DM Sans', sans-serif;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  width: 100%;
}
input:focus, select:focus, textarea:focus {
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(0,191,255,0.1);
}
select option { background: #0e1220; }
textarea { resize: vertical; min-height: 90px; }

/* ── CHARACTER COUNTER ── */
.char-wrap { position: relative; }
.char-counter {
  position: absolute;
  bottom: 10px; right: 12px;
  font-size: 11px;
  color: var(--muted);
  pointer-events: none;
}

/* ── SUBMIT BTN ── */
.btn-submit {
  width: 100%;
  padding: 14px;
  background: linear-gradient(135deg, var(--blue) 0%, var(--blue2) 100%);
  color: #fff;
  border: none;
  border-radius: 12px;
  font-family: 'Rajdhani', sans-serif;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 1px;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.15s;
  margin-top: 8px;
}
.btn-submit:hover { opacity: 0.9; transform: translateY(-1px); }
.btn-submit:active { transform: translateY(0); }
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

/* ── DIVIDER ── */
.divider {
  border: none;
  border-top: 1px solid var(--border);
  margin: 28px 0;
}

/* ── DISCORD TAG ── */
.discord-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(88,101,242,0.12);
  border: 1px solid rgba(88,101,242,0.25);
  border-radius: 10px;
  padding: 8px 14px;
  font-size: 14px;
  font-weight: 600;
  color: #8fa8ff;
  margin-bottom: 20px;
}
.discord-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 6px var(--green);
}

/* ── STATUS CARDS ── */
.status-card {
  text-align: center;
  padding: 20px 0 10px;
}
.status-icon {
  font-size: 52px;
  display: block;
  margin-bottom: 12px;
}
.status-card h2 {
  font-family: 'Rajdhani', sans-serif;
  font-size: 28px;
  font-weight: 700;
}
.status-card h2.success { color: var(--green); }
.status-card h2.error   { color: var(--red); }
.status-card p { color: var(--muted); margin-top: 8px; font-size: 14px; }

.highlight-box {
  background: rgba(0,191,255,0.06);
  border: 1px solid rgba(0,191,255,0.18);
  border-radius: 10px;
  padding: 10px 16px;
  margin: 16px 0 0;
  font-size: 14px;
  color: var(--blue);
  text-align: center;
}

/* ── FOOTER ── */
.footer {
  text-align: center;
  margin-top: 32px;
  color: var(--muted);
  font-size: 12px;
}

/* ── RESPONSIVE ── */
@media (max-width: 520px) {
  .card { padding: 24px 20px; }
  .form-row.cols-2 { grid-template-columns: 1fr; }
}
</style>
"""

# ── VERIFY SUCCESS PAGE ───────────────────────────────────────
SUCCESS_HTML = BASE_STYLE + """
<div class="page-wrap">
  <header class="site-header">
    <div class="logo-ring">💎</div>
    <h1>Valora Store</h1>
    <p>Secure Verification System</p>
  </header>
  <div class="card">
    <div class="status-card">
      <span class="status-icon">✅</span>
      <h2 class="success">Verified!</h2>
      <div class="discord-tag" style="display:inline-flex;margin-top:16px">
        <span class="discord-dot"></span>
        {{ username }}
      </div>
      <p>Your Discord account is now verified.<br>You can close this tab and return to the server.</p>
    </div>
    <div class="highlight-box">🎉 You now have access to all Valora channels</div>
  </div>
  <div class="footer"><a href="https://valora-store.mysellauth.com/">valora-store.mysellauth.com</a></div>
</div>
"""

# ── ERROR PAGE ────────────────────────────────────────────────
ERROR_HTML = BASE_STYLE + """
<div class="page-wrap">
  <header class="site-header">
    <div class="logo-ring">💎</div>
    <h1>Valora Store</h1>
  </header>
  <div class="card">
    <div class="status-card">
      <span class="status-icon">❌</span>
      <h2 class="error">Something went wrong</h2>
      <p>{{ error }}</p>
    </div>
  </div>
  <div class="footer"><a href="https://valora-store.mysellauth.com/">valora-store.mysellauth.com</a></div>
</div>
"""

# ── APPLICATION FORM ──────────────────────────────────────────
# Step 1: Redirect to Discord OAuth to identify applicant
# Step 2: Show the form pre-filled with their Discord tag
# Step 3: POST → save to applications.json

APPLY_OAUTH_HTML = BASE_STYLE + """
<div class="page-wrap">
  <header class="site-header">
    <div class="logo-ring">📋</div>
    <h1>Valora Store</h1>
    <p>Staff Application</p>
  </header>
  <div class="card">
    <div class="status-card">
      <span class="status-icon" style="font-size:40px">🔐</span>
      <h2 style="color:var(--blue);font-size:22px">Identify with Discord</h2>
      <p style="margin-top:10px">We need to verify your Discord account<br>before you can submit an application.</p>
    </div>
    <div style="margin-top:24px;text-align:center">
      <a href="{{ oauth_url }}" style="
        display:inline-block;
        padding:13px 32px;
        background:#5865F2;
        color:white;
        border-radius:12px;
        font-family:'Rajdhani',sans-serif;
        font-size:16px;
        font-weight:700;
        letter-spacing:0.8px;
        text-decoration:none;
        transition:opacity 0.2s
      " onmouseover="this.style.opacity=0.85" onmouseout="this.style.opacity=1">
        🔐 &nbsp; Continue with Discord
      </a>
    </div>
    <p style="text-align:center;color:var(--muted);font-size:12px;margin-top:18px">
      We only read your username and ID — no passwords, no email.
    </p>
  </div>
  <div class="footer"><a href="https://valora-store.mysellauth.com/">valora-store.mysellauth.com</a></div>
</div>
"""

APPLY_FORM_HTML = BASE_STYLE + """
<div class="page-wrap">
  <header class="site-header">
    <div class="logo-ring">📋</div>
    <h1>Valora Store</h1>
    <p>Staff Application Form</p>
  </header>
  <div class="card">
    <div class="discord-tag">
      <span class="discord-dot"></span>
      Applying as: <strong>{{ username }}</strong>
    </div>

    <form method="POST" action="/apply/submit" id="appForm">
      <input type="hidden" name="discord_id"       value="{{ discord_id }}">
      <input type="hidden" name="discord_username"  value="{{ username }}">

      <!-- PERSONAL INFO -->
      <div class="form-section">
        <div class="section-title">Personal Info</div>
        <div class="form-row cols-2">
          <div class="form-group">
            <label>Age <span class="req">*</span></label>
            <input type="number" name="age" min="13" max="99" required placeholder="e.g. 18">
          </div>
          <div class="form-group">
            <label>Timezone <span class="req">*</span></label>
            <input type="text" name="timezone" required placeholder="e.g. CET, EST, PST">
          </div>
        </div>
        <div class="form-row cols-2">
          <div class="form-group">
            <label>Languages spoken <span class="req">*</span></label>
            <input type="text" name="languages" required placeholder="e.g. English, German">
          </div>
          <div class="form-group">
            <label>Weekly availability <span class="req">*</span></label>
            <select name="availability" required>
              <option value="" disabled selected>Select hours/week</option>
              <option value="1–5h">1–5 hours</option>
              <option value="5–10h">5–10 hours</option>
              <option value="10–20h">10–20 hours</option>
              <option value="20h+">20+ hours</option>
            </select>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>How long have you had your Discord account? <span class="req">*</span></label>
            <input type="text" name="discord_since" required placeholder="e.g. 3 years, since 2020">
          </div>
        </div>
      </div>

      <hr class="divider">

      <!-- EXPERIENCE -->
      <div class="form-section">
        <div class="section-title">Experience</div>
        <div class="form-row">
          <div class="form-group">
            <label>Previous staff / moderation experience <span class="req">*</span></label>
            <div class="char-wrap">
              <textarea name="previous_staff" id="prev_staff" required placeholder="Describe any previous staff roles on Discord servers or similar platforms. If none, write 'No experience'." maxlength="600" rows="4"></textarea>
              <span class="char-counter" id="cnt_prev">0 / 600</span>
            </div>
          </div>
        </div>
      </div>

      <hr class="divider">

      <!-- MOTIVATION -->
      <div class="form-section">
        <div class="section-title">Motivation</div>
        <div class="form-row">
          <div class="form-group">
            <label>Why do you want to join the Valora staff team? <span class="req">*</span></label>
            <div class="char-wrap">
              <textarea name="why_valora" id="why_valora" required placeholder="Tell us why you want to be part of Valora and what you can contribute." maxlength="800" rows="5"></textarea>
              <span class="char-counter" id="cnt_why">0 / 800</span>
            </div>
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>Your skills & strengths <span class="req">*</span></label>
            <div class="char-wrap">
              <textarea name="skills" id="skills" required placeholder="e.g. problem solving, fast response, coding, multilingual, customer support..." maxlength="600" rows="4"></textarea>
              <span class="char-counter" id="cnt_skills">0 / 600</span>
            </div>
          </div>
        </div>
      </div>

      <hr class="divider">

      <!-- EXTRA -->
      <div class="form-section">
        <div class="section-title">Anything else?</div>
        <div class="form-row">
          <div class="form-group">
            <label>Additional information (optional)</label>
            <div class="char-wrap">
              <textarea name="extra" id="extra" placeholder="Anything else you'd like us to know?" maxlength="400" rows="3"></textarea>
              <span class="char-counter" id="cnt_extra">0 / 400</span>
            </div>
          </div>
        </div>
      </div>

      <button type="submit" class="btn-submit" id="submitBtn">
        📋 &nbsp; Submit Application
      </button>
    </form>
  </div>

  <div class="footer">
    <a href="https://valora-store.mysellauth.com/">valora-store.mysellauth.com</a>
    &nbsp;•&nbsp; All applications are reviewed manually
  </div>
</div>

<script>
// Character counters
function bindCounter(textareaId, counterId) {
  const ta  = document.getElementById(textareaId);
  const cnt = document.getElementById(counterId);
  if (!ta || !cnt) return;
  const max = ta.getAttribute('maxlength');
  const update = () => {
    cnt.textContent = ta.value.length + ' / ' + max;
    cnt.style.color = ta.value.length > max * 0.9 ? '#ff8844' : '';
  };
  ta.addEventListener('input', update);
  update();
}
bindCounter('prev_staff', 'cnt_prev');
bindCounter('why_valora', 'cnt_why');
bindCounter('skills',     'cnt_skills');
bindCounter('extra',      'cnt_extra');

// Prevent double-submit
document.getElementById('appForm').addEventListener('submit', function() {
  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = '⏳  Submitting…';
});
</script>
"""

APPLY_SUCCESS_HTML = BASE_STYLE + """
<div class="page-wrap">
  <header class="site-header">
    <div class="logo-ring">📋</div>
    <h1>Valora Store</h1>
    <p>Staff Application</p>
  </header>
  <div class="card">
    <div class="status-card">
      <span class="status-icon">🎉</span>
      <h2 class="success">Application Submitted!</h2>
      <p style="margin-top:12px">
        Thank you, <strong>{{ username }}</strong>!<br>
        Your application has been received and will be reviewed by our admin team.
      </p>
    </div>
    <div class="highlight-box" style="margin-top:20px">
      📬 You'll receive a DM on Discord once a decision has been made.
    </div>
    <p style="text-align:center;color:var(--muted);font-size:13px;margin-top:20px">
      Application ID: <code style="color:var(--blue)">{{ app_id }}</code>
    </p>
  </div>
  <div class="footer"><a href="https://valora-store.mysellauth.com/">valora-store.mysellauth.com</a></div>
</div>
"""

APPLY_ALREADY_HTML = BASE_STYLE + """
<div class="page-wrap">
  <header class="site-header">
    <div class="logo-ring">📋</div>
    <h1>Valora Store</h1>
  </header>
  <div class="card">
    <div class="status-card">
      <span class="status-icon">⏳</span>
      <h2 style="color:var(--gold)">Application Pending</h2>
      <p style="margin-top:12px">
        Hey <strong>{{ username }}</strong>, you already have a pending application.<br>
        Please wait for our team to review it before submitting a new one.
      </p>
    </div>
  </div>
  <div class="footer"><a href="https://valora-store.mysellauth.com/">valora-store.mysellauth.com</a></div>
</div>
"""


# ── ROUTES ───────────────────────────────────────────────────

@app.route("/")
def home():
    return """<div style="text-align:center;color:white;font-family:sans-serif;margin-top:100px">
    <h2>Valora OAuth Server ✅</h2>
    <p style="color:#aaa">Running on Railway</p></div>"""


# ── VERIFY FLOW ──────────────────────────────────────────────

@app.route("/callback")
def callback():
    code  = request.args.get("code")
    error = request.args.get("error")

    if error or not code:
        return render_template_string(ERROR_HTML, error="Authorization was cancelled or failed."), 400

    token_data = exchange_code(code, REDIRECT_URI)
    if not token_data:
        return render_template_string(ERROR_HTML, error="Token exchange failed. Please try again."), 500

    access_token = token_data.get("access_token")
    user         = get_discord_user(access_token)
    if not user:
        return render_template_string(ERROR_HTML, error="Could not fetch Discord user."), 500

    uid      = user["id"]
    username = user["username"]

    verified = load_json(VERIFIED_FILE)
    verified[uid] = {
        "username":     username,
        "access_token": access_token,
        "verified_at":  datetime.now(timezone.utc).isoformat(),
    }
    save_json(VERIFIED_FILE, verified)

    give_role(uid)
    print(f"✅ VERIFIED: {username} ({uid})")

    return render_template_string(SUCCESS_HTML, username=username)


# ── APPLY FLOW ───────────────────────────────────────────────

@app.route("/apply")
def apply_start():
    """Step 1 — Redirect to Discord OAuth so we know who's applying."""
    import urllib.parse
    encoded_redirect = urllib.parse.quote(APPLY_OAUTH_URI, safe="")
    oauth_url = (
        "https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={encoded_redirect}"
        "&response_type=code"
        "&scope=identify"
    )
    return render_template_string(APPLY_OAUTH_HTML, oauth_url=oauth_url)


@app.route("/apply/callback")
def apply_callback():
    """Step 2 — Discord sends code here; we identify the user and show the form."""
    code  = request.args.get("code")
    error = request.args.get("error")

    if error or not code:
        return render_template_string(ERROR_HTML, error="Discord login cancelled."), 400

    token_data = exchange_code(code, APPLY_OAUTH_URI)
    if not token_data:
        return render_template_string(ERROR_HTML, error="Could not authenticate with Discord."), 500

    user = get_discord_user(token_data["access_token"])
    if not user:
        return render_template_string(ERROR_HTML, error="Could not fetch Discord user."), 500

    uid      = user["id"]
    username = user["username"]

    # Check for existing pending application
    apps = load_json(APPLICATIONS_FILE)
    for app_data in apps.values():
        if str(app_data.get("discord_id")) == str(uid) and app_data.get("status") == "pending":
            return render_template_string(APPLY_ALREADY_HTML, username=username)

    return render_template_string(APPLY_FORM_HTML, discord_id=uid, username=username)


@app.route("/apply/submit", methods=["POST"])
def apply_submit():
    """Step 3 — Receive the submitted form and save it."""
    discord_id       = request.form.get("discord_id", "").strip()
    discord_username = request.form.get("discord_username", "Unknown").strip()

    if not discord_id:
        return render_template_string(ERROR_HTML, error="Missing Discord ID. Please restart the application."), 400

    # Validate required fields
    required = ["age", "timezone", "languages", "availability",
                "discord_since", "previous_staff", "why_valora", "skills"]
    for field in required:
        if not request.form.get(field, "").strip():
            return render_template_string(ERROR_HTML,
                error=f"Field '{field}' is required. Please go back and fill in all fields."), 400

    app_id = str(uuid.uuid4())[:8].upper()

    apps = load_json(APPLICATIONS_FILE)
    apps[app_id] = {
        "discord_id":       int(discord_id),
        "discord_username": discord_username,
        "submitted_at":     datetime.now(timezone.utc).isoformat(),
        "status":           "pending",
        "message_id":       None,
        "channel_id":       None,
        # Form fields
        "age":              request.form.get("age", "").strip(),
        "timezone":         request.form.get("timezone", "").strip(),
        "languages":        request.form.get("languages", "").strip(),
        "availability":     request.form.get("availability", "").strip(),
        "discord_since":    request.form.get("discord_since", "").strip(),
        "previous_staff":   request.form.get("previous_staff", "").strip()[:600],
        "why_valora":       request.form.get("why_valora", "").strip()[:800],
        "skills":           request.form.get("skills", "").strip()[:600],
        "extra":            request.form.get("extra", "").strip()[:400],
    }
    save_json(APPLICATIONS_FILE, apps)

    print(f"📋 New application: {app_id} from {discord_username} ({discord_id})")
    # The bot's poll_applications task will pick this up within 10 seconds

    return render_template_string(APPLY_SUCCESS_HTML, username=discord_username, app_id=app_id)


# ── RUN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"🌐 Valora web server running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
