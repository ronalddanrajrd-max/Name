from flask import Flask, request, redirect, session, render_template_string
import sqlite3
import os
import threading
import asyncio
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

    conn.execute("""
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
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS hwid_resets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        old_hwid TEXT,
        new_hwid TEXT,
        reset_by TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT,
        user_id TEXT,
        message TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )
    """)

    try:
        conn.execute("ALTER TABLE scripts ADD COLUMN executions INTEGER DEFAULT 0")
    except:
        pass

    conn.commit()
    conn.close()


STYLE = """
<style>
*{box-sizing:border-box}
body{margin:0;background:#020617;color:white;font-family:Arial, sans-serif}
.sidebar{position:fixed;left:0;top:0;width:260px;height:100vh;background:#0f172a;padding:25px;border-right:1px solid #1e293b}
.sidebar h2{color:#38bdf8;margin-bottom:28px}
.sidebar a{display:block;color:#cbd5e1;text-decoration:none;padding:12px;border-radius:10px;margin:7px 0}
.sidebar a:hover{background:#1e293b;color:#38bdf8}
.main{margin-left:290px;padding:35px}
.card{background:#111827;padding:20px;border-radius:18px;margin-bottom:20px;border:1px solid #334155}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:18px}
.stat{background:#0f172a;padding:20px;border-radius:18px;border:1px solid #334155}
.stat h2{color:#38bdf8;font-size:34px;margin:0}
.stat p{color:#94a3b8;margin:6px 0 0}
input,textarea,select{width:100%;padding:12px;margin:8px 0;border-radius:10px;border:1px solid #334155;background:#020617;color:white}
button{background:#38bdf8;border:0;padding:12px 18px;border-radius:10px;font-weight:bold;cursor:pointer}
table{width:100%;border-collapse:collapse}
th,td{padding:12px;border-bottom:1px solid #334155;text-align:left}
th{color:#38bdf8}
a{color:#38bdf8}
.danger{color:#fb7185;font-weight:bold}
.ok{color:#22c55e;font-weight:bold}
.pending{color:#facc15;font-weight:bold}
.badge{padding:4px 9px;border-radius:999px;background:#1e293b;border:1px solid #334155}
textarea{font-family:Consolas, monospace}
</style>
"""


def layout(content):
    return STYLE + f"""
    <div class="sidebar">
        <h2>⚡ OkveHUB</h2>
        <a href="/">📊 Dashboard</a>
        <a href="/whitelist">🔐 Users / Whitelist</a>
        <a href="/keys">🔑 Keys</a>
        <a href="/scripts">📜 Scripts</a>
        <a href="/purchases">🛒 Purchases</a>
        <a href="/executions">🧠 Executions</a>
        <a href="/hwid-resets">⚙️ HWID Resets</a>
        <a href="/blacklist">⛔ Blacklist</a>
        <a href="/logs">📁 Logs</a>
        <a href="/logout">🚪 Déconnexion</a>
    </div>
    <div class="main">{content}</div>
    """


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == os.getenv("ADMIN_PASSWORD", "admin123"):
            session["admin"] = True
            return redirect("/")

    return STYLE + """
    <div style="max-width:420px;margin:120px auto" class="card">
        <h1>🔐 OkveHUB Admin</h1>
        <form method="post">
            <input type="password" name="password" placeholder="Mot de passe admin">
            <button>Connexion</button>
        </form>
    </div>
    """


@app.route("/")
def home():
    if not protect():
        return redirect("/login")

    conn = db()
    whitelist_count = conn.execute("SELECT COUNT(*) c FROM whitelist").fetchone()["c"]
    keys_count = conn.execute("SELECT COUNT(*) c FROM keys").fetchone()["c"]
    active_keys = conn.execute("SELECT COUNT(*) c FROM keys WHERE status='active'").fetchone()["c"]
    scripts_count = conn.execute("SELECT COUNT(*) c FROM scripts WHERE active=1").fetchone()["c"]
    purchases_count = conn.execute("SELECT COUNT(*) c FROM purchases").fetchone()["c"]
    completed_purchases = conn.execute("SELECT COUNT(*) c FROM purchases WHERE status='completed'").fetchone()["c"]
    executions = conn.execute("SELECT COUNT(*) c FROM execution_logs").fetchone()["c"]
    blacklist_count = conn.execute("SELECT COUNT(*) c FROM blacklist").fetchone()["c"]
    recent_purchases = conn.execute("SELECT * FROM purchases ORDER BY created_at DESC LIMIT 5").fetchall()
    conn.close()

    html = """
    <h1>Dashboard</h1>
    <div class="grid">
        <div class="stat"><h2>{{whitelist_count}}</h2><p>Users whitelist</p></div>
        <div class="stat"><h2>{{keys_count}}</h2><p>Total keys</p></div>
        <div class="stat"><h2>{{active_keys}}</h2><p>Active keys</p></div>
        <div class="stat"><h2>{{scripts_count}}</h2><p>Scripts actifs</p></div>
        <div class="stat"><h2>{{purchases_count}}</h2><p>Purchases</p></div>
        <div class="stat"><h2>{{completed_purchases}}</h2><p>Completed</p></div>
        <div class="stat"><h2>{{executions}}</h2><p>Executions</p></div>
        <div class="stat"><h2>{{blacklist_count}}</h2><p>Blacklist</p></div>
    </div>

    <div class="card">
        <h2>Derniers achats</h2>
        <table>
            <tr><th>ID</th><th>User</th><th>Method</th><th>Status</th></tr>
            {% for p in recent_purchases %}
            <tr>
                <td>{{p["purchase_id"]}}</td>
                <td>{{p["username"]}}</td>
                <td>{{p["method"]}}</td>
                <td>{% if p["status"] == "completed" %}<span class="ok">Completed</span>{% else %}<span class="pending">Pending</span>{% endif %}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    """
    return layout(render_template_string(html, **locals()))


@app.route("/scripts", methods=["GET", "POST"])
def scripts():
    if not protect():
        return redirect("/login")

    conn = db()

    if request.method == "POST":
        name = request.form.get("name", "main").strip()
        description = request.form.get("description", "").strip()
        code = request.form.get("code", "")

        conn.execute("""
        INSERT INTO scripts(name, description, active, code, executions)
        VALUES(?, ?, 1, ?, 0)
        ON CONFLICT(name) DO UPDATE SET
            description=excluded.description,
            code=excluded.code,
            active=1
        """, (name, description, code))
        conn.commit()

    rows = conn.execute("SELECT * FROM scripts WHERE active=1 ORDER BY id DESC").fetchall()
    conn.close()

    html = """
    <h1>Scripts</h1>
    <div class="card">
        <h2>Ajouter / Modifier un script</h2>
        <form method="post">
            <input name="name" placeholder="Nom du script" value="main">
            <input name="description" placeholder="Description">
            <textarea name="code" rows="16" placeholder="Colle ton script Lua obfusqué ici"></textarea>
            <button>Enregistrer</button>
        </form>
    </div>

    <div class="card">
        <table>
            <tr><th>Nom</th><th>Description</th><th>Executions</th><th>Action</th></tr>
            {% for s in rows %}
            <tr>
                <td>{{s["name"]}}</td>
                <td>{{s["description"]}}</td>
                <td>{{s["executions"] or 0}}</td>
                <td>{% if s["name"] != "main" %}<a class="danger" href="/delete-script/{{s['name']}}">Supprimer</a>{% else %}Protégé{% endif %}</td>
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

    if script_name != "main":
        conn = db()
        conn.execute("UPDATE scripts SET active=0 WHERE name=?", (script_name,))
        conn.commit()
        conn.close()

    return redirect("/scripts")


@app.route("/keys")
def keys():
    if not protect():
        return redirect("/login")

    conn = db()
    rows = conn.execute("SELECT * FROM keys ORDER BY created_at DESC").fetchall()
    conn.close()

    html = """
    <h1>Keys</h1>
    <div class="card">
        <table>
            <tr><th>Key</th><th>Script</th><th>Used by</th><th>Status</th><th>Expires</th></tr>
            {% for k in rows %}
            <tr>
                <td>{{k["key_code"]}}</td>
                <td>{{k["script_name"]}}</td>
                <td>{{k["used_by"] or "Unused"}}</td>
                <td>{{k["status"] or "active"}}</td>
                <td>{{k["expires_at"] or "Never"}}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/whitelist")
def whitelist():
    if not protect():
        return redirect("/login")

    conn = db()
    rows = conn.execute("SELECT * FROM whitelist ORDER BY created_at DESC").fetchall()
    conn.close()

    html = """
    <h1>Users / Whitelist</h1>
    <div class="card">
        <table>
            <tr><th>User ID</th><th>Username</th><th>Script</th><th>HWID</th><th>Expires</th></tr>
            {% for u in rows %}
            <tr>
                <td>{{u["user_id"]}}</td>
                <td>{{u["username"]}}</td>
                <td>{{u["script_access"]}}</td>
                <td>{{u["hwid"] or "Not assigned"}}</td>
                <td>{{u["expires_at"] or "Never"}}</td>
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
    <h1>Purchases</h1>
    <div class="card">
        <table>
            <tr><th>ID</th><th>User</th><th>Method</th><th>Script</th><th>Amount</th><th>Status</th><th>TX</th></tr>
            {% for p in rows %}
            <tr>
                <td>{{p["purchase_id"]}}</td>
                <td>{{p["username"]}}</td>
                <td>{{p["method"]}}</td>
                <td>{{p["script_name"]}}</td>
                <td>{{p["amount_ltc"]}}</td>
                <td>{% if p["status"] == "completed" %}<span class="ok">Completed</span>{% else %}<span class="pending">Pending</span>{% endif %}</td>
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
    <h1>Execution Logs</h1>
    <div class="card">
        <table>
            <tr><th>ID</th><th>User</th><th>Key</th><th>Script</th><th>HWID</th><th>Executor</th><th>Status</th></tr>
            {% for e in rows %}
            <tr>
                <td>{{e["id"]}}</td>
                <td>{{e["user_id"]}}</td>
                <td>{{e["key_code"]}}</td>
                <td>{{e["script_name"]}}</td>
                <td>{{e["hwid"] or "None"}}</td>
                <td>{{e["executor"] or "Unknown"}}</td>
                <td>{{e["status"]}}</td>
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
    <h1>HWID Resets</h1>
    <div class="card">
        <table>
            <tr><th>ID</th><th>User</th><th>Old HWID</th><th>New HWID</th><th>Reset by</th></tr>
            {% for r in rows %}
            <tr>
                <td>{{r["id"]}}</td>
                <td>{{r["user_id"]}}</td>
                <td>{{r["old_hwid"] or "None"}}</td>
                <td>{{r["new_hwid"] or "None"}}</td>
                <td>{{r["reset_by"]}}</td>
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
    <h1>Blacklist</h1>
    <div class="card">
        <table>
            <tr><th>User ID</th><th>Username</th><th>Reason</th><th>Added by</th></tr>
            {% for b in rows %}
            <tr>
                <td>{{b["user_id"]}}</td>
                <td>{{b["username"]}}</td>
                <td>{{b["reason"]}}</td>
                <td>{{b["added_by"]}}</td>
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
    <h1>Logs</h1>
    <div class="card">
        <table>
            <tr><th>ID</th><th>Type</th><th>User</th><th>Message</th></tr>
            {% for l in rows %}
            <tr>
                <td>{{l["id"]}}</td>
                <td>{{l["type"]}}</td>
                <td>{{l["user_id"]}}</td>
                <td>{{l["message"]}}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/load")
def load_script():
    user_agent = request.headers.get("User-Agent", "").lower()
    blocked_agents = ["mozilla", "chrome", "safari", "firefox", "edge", "opera", "brave"]

    if any(agent in user_agent for agent in blocked_agents):
        return "Access denied", 403, {"Content-Type": "text/plain"}

    key = request.args.get("key", "").strip().upper()
    hwid = request.args.get("hwid", "").strip()
    executor = request.args.get("executor", "Unknown").strip()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    conn = db()

    key_row = conn.execute("SELECT * FROM keys WHERE key_code=?", (key,)).fetchone()
    if not key_row:
        conn.close()
        return "print('Key invalide')", 200, {"Content-Type": "text/plain"}

    user_id = key_row["used_by"]
    script_name = key_row["script_name"] or "main"

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
        return "print('Script introuvable')", 200, {"Content-Type": "text/plain"}

    conn.execute("UPDATE scripts SET executions = COALESCE(executions,0) + 1 WHERE name=?", (script_name,))
    conn.execute("""
    INSERT INTO execution_logs (user_id, key_code, script_name, hwid, ip, executor, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, key, script_name, hwid, ip, executor, "success"))

    conn.commit()
    conn.close()

    return script["code"] or "print('Script vide')", 200, {"Content-Type": "text/plain"}


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


def run_bot():
    token = os.getenv("TOKEN")
    if not token:
        print("TOKEN manquant")
        return

    bot = OkveHUBBot()
    asyncio.run(bot.start(token))


if __name__ == "__main__":
    init_db_site()
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
