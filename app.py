from flask import Flask, request, redirect, session, render_template_string
import sqlite3
import os
import threading
import asyncio
import requests
import secrets
import time

from Bot import OkveHUBBot

app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_SECRET", "okvehub_secret_123")
DB_PATH = "okvehub.db"


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def protect():
    return session.get("admin") is True


def init_db_site():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS whitelist (
        user_id TEXT PRIMARY KEY,
        username TEXT,
        added_by TEXT,
        reason TEXT,
        hwid TEXT,
        script_access TEXT DEFAULT 'OkveHUB',
        expires_at INTEGER DEFAULT NULL,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    );

    CREATE TABLE IF NOT EXISTS keys (
        key_code TEXT PRIMARY KEY,
        script_name TEXT DEFAULT 'OkveHUB',
        used_by TEXT,
        used_at INTEGER,
        expires_at INTEGER,
        status TEXT DEFAULT 'active',
        created_at INTEGER DEFAULT (strftime('%s','now'))
    );

    CREATE TABLE IF NOT EXISTS scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT,
        price REAL DEFAULT 0,
        category TEXT DEFAULT 'main',
        active INTEGER DEFAULT 1,
        code TEXT,
        executions INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    );

    CREATE TABLE IF NOT EXISTS purchases (
        purchase_id TEXT PRIMARY KEY,
        user_id TEXT,
        username TEXT,
        method TEXT,
        script_name TEXT DEFAULT 'OkveHUB',
        amount_ltc REAL,
        status TEXT DEFAULT 'pending',
        created_at INTEGER DEFAULT (strftime('%s','now')),
        completed_at INTEGER,
        tx_hash TEXT
    );

    CREATE TABLE IF NOT EXISTS execution_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        key_code TEXT,
        script_name TEXT,
        hwid TEXT,
        ip TEXT,
        executor TEXT,
        status TEXT DEFAULT 'success',
        created_at INTEGER DEFAULT (strftime('%s','now'))
    );

    CREATE TABLE IF NOT EXISTS hwid_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        old_hwid TEXT,
        new_hwid TEXT,
        reset_by TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    );

    CREATE TABLE IF NOT EXISTS blacklist (
        user_id TEXT PRIMARY KEY,
        username TEXT,
        reason TEXT,
        added_by TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    );

    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        user_id TEXT,
        message TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    );
    """)

    for query in [
        "ALTER TABLE keys ADD COLUMN expires_at INTEGER",
        "ALTER TABLE keys ADD COLUMN status TEXT DEFAULT 'active'",
        "ALTER TABLE scripts ADD COLUMN executions INTEGER DEFAULT 0",
        "ALTER TABLE whitelist ADD COLUMN expires_at INTEGER DEFAULT NULL",
    ]:
        try:
            conn.execute(query)
        except:
            pass

    conn.execute("""
    INSERT OR IGNORE INTO scripts
    (name, description, price, category, active, code, executions)
    VALUES
    ('OkveHUB', 'Script principal OkveHUB', 0, 'main', 1, 'print("OkveHUB Loaded")', 0)
    """)

    conn.commit()
    conn.close()


STYLE = """
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#050816;color:white;font-family:Arial,sans-serif}
.sidebar{position:fixed;left:0;top:0;width:270px;height:100vh;background:#0b1220;padding:24px;border-right:1px solid #1e293b}
.logo{display:flex;align-items:center;gap:12px;margin-bottom:35px}
.logo-icon{width:42px;height:42px;border-radius:12px;background:linear-gradient(135deg,#38bdf8,#6366f1);display:flex;align-items:center;justify-content:center;font-weight:bold}
.logo h2{font-size:22px}
.sidebar a{display:block;text-decoration:none;color:#94a3b8;padding:14px 16px;border-radius:14px;margin:8px 0}
.sidebar a:hover{background:#111827;color:white}
.main{margin-left:270px;padding:35px;min-height:100vh;background:radial-gradient(circle at top right,#2563eb22,transparent 35%),#050816}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px}
.topbar h1{font-size:34px}
.card,.table-card{background:linear-gradient(180deg,#0f172a,#0b1220);border:1px solid #26344d;border-radius:22px;padding:24px;margin-bottom:24px;box-shadow:0 12px 40px #0008}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:22px;margin-bottom:25px}
.stat-title{color:#94a3b8;font-size:14px;margin-bottom:12px}
.stat-number{font-size:42px;font-weight:700;color:#38bdf8}
table{width:100%;border-collapse:collapse}
th{text-align:left;color:#38bdf8;padding:16px;border-bottom:1px solid #1e293b}
td{padding:16px;color:#cbd5e1;border-bottom:1px solid #1e293b;vertical-align:top}
tr:hover td{background:#111827}
input,textarea,select{width:100%;padding:12px;border-radius:12px;border:1px solid #334155;background:#020617;color:white;margin:6px 0}
textarea{font-family:Consolas,monospace}
button{background:linear-gradient(135deg,#38bdf8,#6366f1);border:none;color:white;padding:12px 18px;border-radius:12px;font-weight:bold;cursor:pointer}
a{color:#38bdf8;text-decoration:none}
.badge{display:inline-block;padding:6px 12px;border-radius:999px;font-size:13px;font-weight:bold;margin:2px}
.badge-success{background:#22c55e22;color:#22c55e}
.badge-warning{background:#facc1522;color:#facc15}
.badge-danger{background:#ef444422;color:#ef4444}
@media(max-width:900px){.sidebar{position:relative;width:100%;height:auto}.main{margin-left:0;padding:20px}}
</style>
"""


def layout(content):
    return STYLE + f"""
    <div class="sidebar">
        <div class="logo"><div class="logo-icon">⚡</div><h2>OkveHUB</h2></div>
        <a href="/">📊 Dashboard</a>
        <a href="/users">👥 Users</a>
        <a href="/whitelist">🔐 Whitelist</a>
        <a href="/keys">🔑 Keys</a>
        <a href="/scripts">📜 Scripts</a>
        <a href="/purchases">🛒 Purchases</a>
        <a href="/executions">🧠 Executions</a>
        <a href="/hwid-resets">⚙️ HWID Resets</a>
        <a href="/blacklist">⛔ Blacklist</a>
        <a href="/logs">📁 Logs</a>
        <a href="/logout">🚪 Logout</a>
    </div>
    <div class="main">{content}</div>
    """


@app.route("/login")
def login():
    client_id = os.getenv("DISCORD_CLIENT_ID")
    redirect_uri = os.getenv("DISCORD_REDIRECT_URI")
    url = (
        "https://discord.com/oauth2/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=identify"
    )
    return redirect(url)


@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return redirect("/login")

    data = {
        "client_id": os.getenv("DISCORD_CLIENT_ID"),
        "client_secret": os.getenv("DISCORD_CLIENT_SECRET"),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.getenv("DISCORD_REDIRECT_URI"),
        "scope": "identify"
    }

    token_res = requests.post(
        "https://discord.com/api/oauth2/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    access_token = token_res.json().get("access_token")
    if not access_token:
        return "Discord OAuth Error"

    user_res = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )

    user = user_res.json()
    if user.get("id") != os.getenv("OWNER_ID"):
        return "Access denied"

    session["admin"] = True
    session["discord_id"] = user.get("id")
    session["username"] = user.get("username")
    return redirect("/")


@app.route("/")
def home():
    if not protect():
        return redirect("/login")

    conn = db()
    whitelist_count = conn.execute("SELECT COUNT(*) c FROM whitelist").fetchone()["c"]
    keys_count = conn.execute("SELECT COUNT(*) c FROM keys").fetchone()["c"]
    scripts_count = conn.execute("SELECT COUNT(*) c FROM scripts WHERE active=1").fetchone()["c"]
    purchases_count = conn.execute("SELECT COUNT(*) c FROM purchases").fetchone()["c"]
    executions_count = conn.execute("SELECT COUNT(*) c FROM execution_logs").fetchone()["c"]
    blacklist_count = conn.execute("SELECT COUNT(*) c FROM blacklist").fetchone()["c"]
    conn.close()

    return layout(f"""
    <div class="topbar"><h1>Dashboard</h1><div>👤 {session.get("username")}</div></div>
    <div class="grid">
        <div class="card"><div class="stat-title">Whitelist Users</div><div class="stat-number">{whitelist_count}</div></div>
        <div class="card"><div class="stat-title">Keys</div><div class="stat-number">{keys_count}</div></div>
        <div class="card"><div class="stat-title">Scripts</div><div class="stat-number">{scripts_count}</div></div>
        <div class="card"><div class="stat-title">Purchases</div><div class="stat-number">{purchases_count}</div></div>
        <div class="card"><div class="stat-title">Executions</div><div class="stat-number">{executions_count}</div></div>
        <div class="card"><div class="stat-title">Blacklist</div><div class="stat-number">{blacklist_count}</div></div>
    </div>
    """)


@app.route("/users")
def users():
    if not protect():
        return redirect("/login")

    conn = db()
    rows = conn.execute("""
    SELECT 
        whitelist.user_id,
        whitelist.username,
        whitelist.hwid,
        whitelist.script_access,
        whitelist.expires_at,
        keys.key_code,
        keys.status,
        COUNT(execution_logs.id) as executions
    FROM whitelist
    LEFT JOIN keys ON keys.used_by = whitelist.user_id
    LEFT JOIN execution_logs ON execution_logs.user_id = whitelist.user_id
    GROUP BY whitelist.user_id
    ORDER BY whitelist.created_at DESC
    """).fetchall()
    conn.close()

    html = """
    <div class="topbar"><h1>Users</h1></div>
    <div class="table-card">
    <table>
        <tr><th>User</th><th>Script</th><th>Key</th><th>HWID</th><th>Executions</th><th>Expires</th><th>Status</th><th>Actions</th></tr>
        {% for u in rows %}
        <tr>
            <td>{{u["username"]}}<br><small>{{u["user_id"]}}</small></td>
            <td>{{u["script_access"]}}</td>
            <td>{{u["key_code"] or "No key"}}</td>
            <td>{{u["hwid"] or "Not assigned"}}</td>
            <td>{{u["executions"]}}</td>
            <td>{{u["expires_at"] or "Lifetime"}}</td>
            <td>{{u["status"] or "Unknown"}}</td>
            <td>
                <a class="badge badge-warning" href="/user-reset-hwid/{{u['user_id']}}">Reset HWID</a>
                <a class="badge badge-danger" href="/user-ban/{{u['user_id']}}">Ban</a>
                <a class="badge badge-danger" href="/user-delete/{{u['user_id']}}">Delete</a>
            </td>
        </tr>
        {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/user-reset-hwid/<user_id>")
def user_reset_hwid(user_id):
    if not protect():
        return redirect("/login")

    conn = db()
    user = conn.execute("SELECT * FROM whitelist WHERE user_id=?", (user_id,)).fetchone()
    old_hwid = user["hwid"] if user else None

    conn.execute("UPDATE whitelist SET hwid=NULL WHERE user_id=?", (user_id,))
    conn.execute("""
    INSERT INTO hwid_resets (user_id, old_hwid, new_hwid, reset_by)
    VALUES (?, ?, ?, ?)
    """, (user_id, old_hwid, None, session.get("discord_id", "site")))

    conn.commit()
    conn.close()
    return redirect("/users")


@app.route("/user-ban/<user_id>")
def user_ban(user_id):
    if not protect():
        return redirect("/login")

    conn = db()
    user = conn.execute("SELECT * FROM whitelist WHERE user_id=?", (user_id,)).fetchone()
    username = user["username"] if user else "Unknown"

    conn.execute("""
    INSERT INTO blacklist (user_id, username, reason, added_by)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        username=excluded.username,
        reason=excluded.reason,
        added_by=excluded.added_by
    """, (user_id, username, "Banned from site", session.get("discord_id", "site")))

    conn.execute("DELETE FROM whitelist WHERE user_id=?", (user_id,))
    conn.execute("UPDATE keys SET status='disabled' WHERE used_by=?", (user_id,))
    conn.commit()
    conn.close()
    return redirect("/users")


@app.route("/user-delete/<user_id>")
def user_delete(user_id):
    if not protect():
        return redirect("/login")

    conn = db()
    conn.execute("DELETE FROM whitelist WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM keys WHERE used_by=?", (user_id,))
    conn.execute("DELETE FROM execution_logs WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM hwid_resets WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return redirect("/users")


@app.route("/scripts", methods=["GET", "POST"])
def scripts():
    if not protect():
        return redirect("/login")

    conn = db()

    if request.method == "POST":
        old_name = request.form.get("old_name", "").strip()
        name = request.form.get("name", "OkveHUB").strip()
        description = request.form.get("description", "").strip()
        code = request.form.get("code", "")

        if old_name:
            conn.execute("UPDATE scripts SET name=?, description=?, code=?, active=1 WHERE name=?", (name, description, code, old_name))
            conn.execute("UPDATE keys SET script_name=? WHERE script_name=?", (name, old_name))
            conn.execute("UPDATE whitelist SET script_access=? WHERE script_access=?", (name, old_name))
            conn.execute("UPDATE purchases SET script_name=? WHERE script_name=?", (name, old_name))
        else:
            conn.execute("""
            INSERT INTO scripts (name, description, active, code, executions)
            VALUES (?, ?, 1, ?, 0)
            ON CONFLICT(name) DO UPDATE SET description=excluded.description, code=excluded.code, active=1
            """, (name, description, code))

        conn.commit()

    rows = conn.execute("SELECT * FROM scripts WHERE active=1 ORDER BY id DESC").fetchall()
    conn.close()

    html = """
    <div class="topbar"><h1>Scripts</h1></div>
    <div class="card">
        <h2>Ajouter un script</h2>
        <form method="post">
            <input name="name" placeholder="Nom du script" value="OkveHUB" required>
            <input name="description" placeholder="Description du script">
            <textarea name="code" rows="12" placeholder="Colle ton script Lua ici"></textarea>
            <button>Ajouter / Enregistrer</button>
        </form>
    </div>

    <div class="table-card">
    <table>
        <tr><th>Nom</th><th>Description</th><th>Executions</th><th>Code / Modifier</th><th>Supprimer</th></tr>
        {% for s in rows %}
        <tr>
            <form method="post">
                <input type="hidden" name="old_name" value="{{s['name']}}">
                <td><input name="name" value="{{s['name']}}"></td>
                <td><input name="description" value="{{s['description'] or ''}}"></td>
                <td>{{s["executions"] or 0}}</td>
                <td><textarea name="code" rows="5">{{s["code"] or ""}}</textarea><button>Modifier</button></td>
                <td>
                    {% if s["name"] != "OkveHUB" %}
                    <a class="badge badge-danger" href="/delete-script/{{s['name']}}">Supprimer</a>
                    {% else %}
                    Protégé
                    {% endif %}
                </td>
            </form>
        </tr>
        {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/delete-script/<script_name>")
def delete_script(script_name):
    if not protect():
        return redirect("/login")

    if script_name != "OkveHUB":
        conn = db()
        conn.execute("UPDATE scripts SET active=0 WHERE name=?", (script_name,))
        conn.commit()
        conn.close()

    return redirect("/scripts")


@app.route("/keys", methods=["GET", "POST"])
def keys():
    if not protect():
        return redirect("/login")

    conn = db()

    if request.method == "POST":
        script_name = request.form.get("script_name", "OkveHUB")
        duration = request.form.get("duration", "lifetime")
        key_code = "OKV-" + secrets.token_hex(8).upper()

        expires_at = None
        if duration == "1d":
            expires_at = int(time.time()) + 86400
        elif duration == "7d":
            expires_at = int(time.time()) + 604800
        elif duration == "30d":
            expires_at = int(time.time()) + 2592000

        conn.execute(
            "INSERT INTO keys (key_code, script_name, expires_at, status) VALUES (?, ?, ?, 'active')",
            (key_code, script_name, expires_at)
        )
        conn.commit()

    rows = conn.execute("SELECT * FROM keys ORDER BY created_at DESC").fetchall()
    scripts_rows = conn.execute("SELECT name FROM scripts WHERE active=1 ORDER BY name").fetchall()
    conn.close()

    html = """
    <div class="topbar"><h1>Keys</h1></div>
    <div class="card">
        <h2>Créer une key</h2>
        <form method="post">
            <select name="script_name">
                {% for s in scripts_rows %}
                <option value="{{s['name']}}">{{s['name']}}</option>
                {% endfor %}
            </select>
            <select name="duration">
                <option value="lifetime">Lifetime</option>
                <option value="1d">1 jour</option>
                <option value="7d">7 jours</option>
                <option value="30d">30 jours</option>
            </select>
            <button>Créer la key</button>
        </form>
    </div>

    <div class="table-card">
    <table>
        <tr><th>Key</th><th>Script</th><th>User</th><th>Status</th><th>Expire</th><th>Action</th></tr>
        {% for k in rows %}
        <tr>
            <td>{{k["key_code"]}}</td>
            <td>{{k["script_name"]}}</td>
            <td>{{k["used_by"] or "Unused"}}</td>
            <td>{{k["status"] or "active"}}</td>
            <td>{{k["expires_at"] or "Lifetime"}}</td>
            <td>
                <a class="badge badge-warning" href="/toggle-key/{{k['key_code']}}">Disable/Enable</a>
                <a class="badge badge-danger" href="/delete-key/{{k['key_code']}}">Delete</a>
            </td>
        </tr>
        {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows, scripts_rows=scripts_rows))


@app.route("/toggle-key/<key_code>")
def toggle_key(key_code):
    if not protect():
        return redirect("/login")

    conn = db()
    key = conn.execute("SELECT * FROM keys WHERE key_code=?", (key_code,)).fetchone()
    if key:
        new_status = "disabled" if key["status"] == "active" else "active"
        conn.execute("UPDATE keys SET status=? WHERE key_code=?", (new_status, key_code))
        conn.commit()

    conn.close()
    return redirect("/keys")


@app.route("/delete-key/<key_code>")
def delete_key(key_code):
    if not protect():
        return redirect("/login")

    conn = db()
    conn.execute("DELETE FROM keys WHERE key_code=?", (key_code,))
    conn.commit()
    conn.close()
    return redirect("/keys")


@app.route("/whitelist")
def whitelist():
    if not protect():
        return redirect("/login")

    conn = db()
    rows = conn.execute("SELECT * FROM whitelist ORDER BY created_at DESC").fetchall()
    conn.close()

    html = """
    <div class="topbar"><h1>Whitelist</h1></div>
    <div class="table-card">
    <table>
        <tr><th>User ID</th><th>Username</th><th>Script</th><th>HWID</th><th>Expires</th></tr>
        {% for u in rows %}
        <tr>
            <td>{{u["user_id"]}}</td><td>{{u["username"]}}</td><td>{{u["script_access"]}}</td><td>{{u["hwid"] or "None"}}</td><td>{{u["expires_at"] or "Never"}}</td>
        </tr>
        {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/purchases")
def purchases():
    if not protect():
        return redirect("/login")

    conn = db()
    rows = conn.execute("SELECT * FROM purchases ORDER BY created_at DESC").fetchall()
    conn.close()

    html = """
    <div class="topbar"><h1>Purchases</h1></div>
    <div class="table-card">
    <table>
        <tr><th>ID</th><th>User</th><th>Method</th><th>Script</th><th>Amount</th><th>Status</th><th>TX</th></tr>
        {% for p in rows %}
        <tr>
            <td>{{p["purchase_id"]}}</td><td>{{p["username"]}}</td><td>{{p["method"]}}</td><td>{{p["script_name"]}}</td><td>{{p["amount_ltc"]}}</td>
            <td>{% if p["status"] == "completed" %}<span class="badge badge-success">Completed</span>{% else %}<span class="badge badge-warning">Pending</span>{% endif %}</td>
            <td>{{p["tx_hash"] or "None"}}</td>
        </tr>
        {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/executions")
def executions():
    if not protect():
        return redirect("/login")

    conn = db()
    rows = conn.execute("SELECT * FROM execution_logs ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()

    html = """
    <div class="topbar"><h1>Executions</h1></div>
    <div class="table-card">
    <table>
        <tr><th>User</th><th>Key</th><th>Script</th><th>HWID</th><th>Executor</th><th>Status</th></tr>
        {% for e in rows %}
        <tr>
            <td>{{e["user_id"]}}</td><td>{{e["key_code"]}}</td><td>{{e["script_name"]}}</td><td>{{e["hwid"] or "None"}}</td><td>{{e["executor"] or "Unknown"}}</td><td>{{e["status"]}}</td>
        </tr>
        {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/hwid-resets")
def hwid_resets():
    if not protect():
        return redirect("/login")

    conn = db()
    rows = conn.execute("SELECT * FROM hwid_resets ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()

    html = """
    <div class="topbar"><h1>HWID Resets</h1></div>
    <div class="table-card">
    <table>
        <tr><th>User</th><th>Old HWID</th><th>New HWID</th><th>Reset by</th></tr>
        {% for r in rows %}
        <tr>
            <td>{{r["user_id"]}}</td><td>{{r["old_hwid"] or "None"}}</td><td>{{r["new_hwid"] or "None"}}</td><td>{{r["reset_by"]}}</td>
        </tr>
        {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/blacklist")
def blacklist():
    if not protect():
        return redirect("/login")

    conn = db()
    rows = conn.execute("SELECT * FROM blacklist ORDER BY created_at DESC").fetchall()
    conn.close()

    html = """
    <div class="topbar"><h1>Blacklist</h1></div>
    <div class="table-card">
    <table>
        <tr><th>User ID</th><th>Username</th><th>Reason</th><th>Added by</th></tr>
        {% for b in rows %}
        <tr>
            <td>{{b["user_id"]}}</td><td>{{b["username"]}}</td><td>{{b["reason"]}}</td><td>{{b["added_by"]}}</td>
        </tr>
        {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/logs")
def logs():
    if not protect():
        return redirect("/login")

    conn = db()
    rows = conn.execute("SELECT * FROM logs ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()

    html = """
    <div class="topbar"><h1>Logs</h1></div>
    <div class="table-card">
    <table>
        <tr><th>ID</th><th>Type</th><th>User</th><th>Message</th></tr>
        {% for l in rows %}
        <tr><td>{{l["id"]}}</td><td>{{l["type"]}}</td><td>{{l["user_id"]}}</td><td>{{l["message"]}}</td></tr>
        {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/load")
def load_script():
    user_agent = request.headers.get("User-Agent", "").lower()
    if any(agent in user_agent for agent in ["mozilla", "chrome", "safari", "firefox", "edge", "opera", "brave"]):
        return "Access denied", 403, {"Content-Type": "text/plain"}

    key = request.args.get("key", "").strip().upper()
    hwid = request.args.get("hwid", "").strip()
    executor = request.args.get("executor", "Unknown").strip()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    conn = db()
    key_row = conn.execute("SELECT * FROM keys WHERE key_code=?", (key,)).fetchone()

    if not key_row:
        conn.close()
        return "print('Invalid key')", 200, {"Content-Type": "text/plain"}

    if key_row["status"] != "active":
        conn.close()
        return "print('Key disabled')", 200, {"Content-Type": "text/plain"}

    user_id = key_row["used_by"]
    script_name = key_row["script_name"] or "OkveHUB"

    wl = conn.execute("SELECT * FROM whitelist WHERE user_id=?", (user_id,)).fetchone()
    if not wl:
        conn.close()
        return "print('Access denied')", 200, {"Content-Type": "text/plain"}

    if wl["hwid"] and hwid and wl["hwid"] != hwid:
        conn.execute("""
        INSERT INTO execution_logs (user_id, key_code, script_name, hwid, ip, executor, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, key, script_name, hwid, ip, executor, "blocked_hwid"))
        conn.commit()
        conn.close()
        return "print('HWID mismatch')", 200, {"Content-Type": "text/plain"}

    if not wl["hwid"] and hwid:
        conn.execute("UPDATE whitelist SET hwid=? WHERE user_id=?", (hwid, user_id))

    script = conn.execute("SELECT * FROM scripts WHERE name=? AND active=1", (script_name,)).fetchone()
    if not script:
        conn.close()
        return "print('Script not found')", 200, {"Content-Type": "text/plain"}

    conn.execute("UPDATE scripts SET executions = COALESCE(executions,0) + 1 WHERE name=?", (script_name,))
    conn.execute("""
    INSERT INTO execution_logs (user_id, key_code, script_name, hwid, ip, executor, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, key, script_name, hwid, ip, executor, "success"))

    conn.commit()
    conn.close()
    return script["code"] or "print('Empty script')", 200, {"Content-Type": "text/plain"}


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


def run_bot():
    token = os.getenv("TOKEN")
    if not token:
        print("TOKEN missing")
        return

    bot = OkveHUBBot()
    asyncio.run(bot.start(token))


if __name__ == "__main__":
    init_db_site()
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
