from flask import Flask, request, redirect, session, render_template_string
import sqlite3
import os
import threading
import asyncio
import secrets
from Bot import OkveHUBBot

app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_SECRET", "okvehub_secret_123")

DB_PATH = "okvehub.db"


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db_site():
    conn = db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS whitelist (
        user_id TEXT PRIMARY KEY,
        username TEXT,
        added_by TEXT,
        reason TEXT,
        hwid TEXT,
        script_access TEXT DEFAULT 'main',
        expires_at INTEGER DEFAULT NULL,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT,
        price REAL DEFAULT 0,
        category TEXT DEFAULT 'general',
        active INTEGER DEFAULT 1,
        code TEXT,
        executions INTEGER DEFAULT 0
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS keys (
        key_code TEXT PRIMARY KEY,
        script_name TEXT DEFAULT 'main',
        used_by TEXT,
        used_at INTEGER,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )
    """)

    try:
        conn.execute("ALTER TABLE scripts ADD COLUMN executions INTEGER DEFAULT 0")
    except:
        pass

    conn.execute("""
    INSERT OR IGNORE INTO scripts
    (name, description, price, category, active, code, executions)
    VALUES
    ('main', 'Script principal OkveHUB', 0, 'main', 1, 'print("OkveHUB Loaded")', 0)
    """)

    conn.commit()
    conn.close()


STYLE = """
<style>
*{box-sizing:border-box}
body{
    margin:0;
    background:radial-gradient(circle at top,#1e1b4b,#020617 55%);
    color:white;
    font-family:Inter,Arial,sans-serif;
}
.sidebar{
    position:fixed;
    left:0;
    top:0;
    width:260px;
    height:100vh;
    background:rgba(2,6,23,.92);
    border-right:1px solid #1e293b;
    padding:28px;
}
.logo{
    font-size:26px;
    font-weight:900;
    color:#38bdf8;
    margin-bottom:35px;
}
.sidebar a{
    display:block;
    color:#cbd5e1;
    text-decoration:none;
    padding:13px 14px;
    border-radius:12px;
    margin:8px 0;
}
.sidebar a:hover{
    background:#1e293b;
    color:#38bdf8;
}
.main{
    margin-left:290px;
    padding:35px;
}
.header{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:25px;
}
.card{
    background:rgba(30,41,59,.88);
    border:1px solid #334155;
    padding:22px;
    border-radius:20px;
    margin-bottom:22px;
    box-shadow:0 15px 40px #0006;
}
.grid{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
    gap:18px;
}
.stat{
    background:linear-gradient(135deg,#1e293b,#0f172a);
    border:1px solid #334155;
    padding:22px;
    border-radius:20px;
}
.stat h2{
    margin:0;
    font-size:34px;
    color:#38bdf8;
}
.stat p{
    color:#cbd5e1;
}
input,textarea,select{
    width:100%;
    padding:13px;
    border-radius:12px;
    border:1px solid #475569;
    margin:8px 0;
    background:#0f172a;
    color:white;
}
button{
    background:linear-gradient(135deg,#38bdf8,#6366f1);
    color:white;
    border:0;
    padding:13px 18px;
    border-radius:12px;
    font-weight:bold;
    cursor:pointer;
}
button:hover{opacity:.9}
table{
    width:100%;
    border-collapse:collapse;
    overflow:hidden;
    border-radius:14px;
}
th{
    background:#0f172a;
    color:#38bdf8;
}
th,td{
    padding:13px;
    border-bottom:1px solid #334155;
    text-align:left;
}
a{color:#38bdf8}
.danger{color:#fb7185;font-weight:bold}
.ok{color:#22c55e;font-weight:bold}
.badge{
    padding:5px 10px;
    border-radius:999px;
    background:#0f172a;
    border:1px solid #334155;
}
textarea{font-family:Consolas,monospace}
</style>
"""


def layout(content):
    return STYLE + f"""
    <div class="sidebar">
        <div class="logo">⚡ OkveHUB</div>
        <a href="/">📊 Dashboard</a>
        <a href="/whitelist">🔐 Whitelist</a>
        <a href="/scripts">📜 Scripts</a>
        <a href="/keys">🔑 Keys</a>
        <a href="/logout">🚪 Déconnexion</a>
    </div>
    <div class="main">
        {content}
    </div>
    """


def protect():
    return session.get("admin") is True


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == os.getenv("ADMIN_PASSWORD", "admin123"):
            session["admin"] = True
            return redirect("/")

    return STYLE + """
    <div style="max-width:430px;margin:130px auto" class="card">
        <h1>🔐 OkveHUB Admin</h1>
        <p>Connexion au panel sécurisé.</p>
        <form method="post">
            <input type="password" name="password" placeholder="Mot de passe admin">
            <button>Se connecter</button>
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
    used_keys = conn.execute("SELECT COUNT(*) c FROM keys WHERE used_by IS NOT NULL").fetchone()["c"]
    scripts_count = conn.execute("SELECT COUNT(*) c FROM scripts WHERE active=1").fetchone()["c"]
    executions = conn.execute("SELECT COALESCE(SUM(executions),0) c FROM scripts").fetchone()["c"]
    recent_keys = conn.execute("SELECT * FROM keys ORDER BY created_at DESC LIMIT 5").fetchall()
    conn.close()

    html = """
    <div class="header">
        <div>
            <h1>Dashboard Admin</h1>
            <p>Gestion complète OkveHUB.</p>
        </div>
        <span class="badge">Online</span>
    </div>

    <div class="grid">
        <div class="stat"><h2>{{whitelist_count}}</h2><p>Whitelist</p></div>
        <div class="stat"><h2>{{keys_count}}</h2><p>Keys créées</p></div>
        <div class="stat"><h2>{{used_keys}}</h2><p>Keys utilisées</p></div>
        <div class="stat"><h2>{{scripts_count}}</h2><p>Scripts actifs</p></div>
        <div class="stat"><h2>{{executions}}</h2><p>Exécutions totales</p></div>
    </div>

    <div class="card">
        <h2>Dernières keys</h2>
        <table>
            <tr><th>Key</th><th>Script</th><th>Statut</th></tr>
            {% for k in recent_keys %}
            <tr>
                <td>{{k["key_code"]}}</td>
                <td>{{k["script_name"]}}</td>
                <td>{% if k["used_by"] %}<span class="ok">Utilisée</span>{% else %}Non utilisée{% endif %}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    """

    return layout(render_template_string(
        html,
        whitelist_count=whitelist_count,
        keys_count=keys_count,
        used_keys=used_keys,
        scripts_count=scripts_count,
        executions=executions,
        recent_keys=recent_keys
    ))


@app.route("/whitelist")
def whitelist():
    if not protect():
        return redirect("/login")

    conn = db()
    rows = conn.execute("SELECT * FROM whitelist ORDER BY created_at DESC").fetchall()
    conn.close()

    html = """
    <h1>🔐 Whitelist</h1>

    <div class="card">
        <table>
            <tr>
                <th>User ID</th>
                <th>Username</th>
                <th>Script</th>
                <th>HWID</th>
                <th>Action</th>
            </tr>
            {% for u in rows %}
            <tr>
                <td>{{u["user_id"]}}</td>
                <td>{{u["username"]}}</td>
                <td>{{u["script_access"]}}</td>
                <td>{{u["hwid"] or "Aucun"}}</td>
                <td><a class="danger" href="/remove/{{u['user_id']}}">Supprimer</a></td>
            </tr>
            {% endfor %}
        </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))


@app.route("/remove/<user_id>")
def remove(user_id):
    if not protect():
        return redirect("/login")

    conn = db()
    conn.execute("DELETE FROM whitelist WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

    return redirect("/whitelist")


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
        INSERT INTO scripts (name, description, price, category, active, code, executions)
        VALUES (?, ?, 0, 'main', 1, ?, 0)
        ON CONFLICT(name) DO UPDATE SET
            description=excluded.description,
            code=excluded.code,
            active=1
        """, (name, description, code))

        conn.commit()

    rows = conn.execute("SELECT * FROM scripts WHERE active=1 ORDER BY id DESC").fetchall()
    conn.close()

    html = """
    <h1>📜 Scripts</h1>

    <div class="card">
        <h2>Ajouter / Modifier un script</h2>
        <form method="post">
            <input name="name" value="main" placeholder="Nom du script">
            <input name="description" placeholder="Description">
            <textarea name="code" rows="18" placeholder="Colle ton script Lua obfusqué ici"></textarea>
            <button>Enregistrer</button>
        </form>
    </div>

    <div class="card">
        <h2>Scripts enregistrés</h2>
        <table>
            <tr>
                <th>Nom</th>
                <th>Description</th>
                <th>Exécutions</th>
                <th>Action</th>
            </tr>
            {% for s in rows %}
            <tr>
                <td>{{s["name"]}}</td>
                <td>{{s["description"]}}</td>
                <td>{{s["executions"] or 0}}</td>
                <td>
                    {% if s["name"] != "main" %}
                    <a class="danger" href="/delete-script/{{s['name']}}">Supprimer</a>
                    {% else %}
                    Protégé
                    {% endif %}
                </td>
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

    if script_name == "main":
        return redirect("/scripts")

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
        key = "OKV-" + secrets.token_hex(8).upper()
        script_name = request.form.get("script_name", "main")

        conn.execute(
            "INSERT INTO keys (key_code, script_name) VALUES (?, ?)",
            (key, script_name)
        )
        conn.commit()

    scripts = conn.execute("SELECT name FROM scripts WHERE active=1").fetchall()
    rows = conn.execute("SELECT * FROM keys ORDER BY created_at DESC").fetchall()
    conn.close()

    html = """
    <h1>🔑 Keys</h1>

    <div class="card">
        <h2>Créer une key</h2>
        <form method="post">
            <select name="script_name">
                {% for s in scripts %}
                <option value="{{s['name']}}">{{s['name']}}</option>
                {% endfor %}
            </select>
            <button>Créer une key</button>
        </form>
    </div>

    <div class="card">
        <h2>Liste des keys</h2>
        <table>
            <tr>
                <th>Key</th>
                <th>Script</th>
                <th>Statut</th>
            </tr>
            {% for k in rows %}
            <tr>
                <td>{{k["key_code"]}}</td>
                <td>{{k["script_name"]}}</td>
                <td>
                    {% if k["used_by"] %}
                    <span class="ok">Utilisée par {{k["used_by"]}}</span>
                    {% else %}
                    Non utilisée
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows, scripts=scripts))


@app.route("/load")
def load_script():
    user_agent = request.headers.get("User-Agent", "").lower()

    blocked_agents = [
        "mozilla", "chrome", "safari", "firefox", "edge", "opera", "brave"
    ]

    if any(agent in user_agent for agent in blocked_agents):
        return "Access denied", 403, {
            "Content-Type": "text/plain",
            "Cache-Control": "no-store"
        }

    key = request.args.get("key", "").strip().upper()

    if not key:
        return "print('Key manquante')", 200, {"Content-Type": "text/plain"}

    conn = db()

    row = conn.execute(
        "SELECT * FROM keys WHERE key_code=?",
        (key,)
    ).fetchone()

    if not row:
        conn.close()
        return "print('Key invalide')", 200, {"Content-Type": "text/plain"}

    script_name = row["script_name"] or "main"

    script = conn.execute(
        "SELECT * FROM scripts WHERE name=? AND active=1",
        (script_name,)
    ).fetchone()

    if not script:
        conn.close()
        return "print('Script introuvable')", 200, {"Content-Type": "text/plain"}

    conn.execute(
        "UPDATE scripts SET executions = COALESCE(executions,0) + 1 WHERE name=?",
        (script_name,)
    )
    conn.commit()
    conn.close()

    code = script["code"] or "print('Script vide')"

    return code, 200, {
        "Content-Type": "text/plain",
        "Cache-Control": "no-store"
    }


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


def run_bot():
    token = os.getenv("TOKEN")

    if not token:
        print("TOKEN manquant dans Railway Variables")
        return

    bot = OkveHUBBot()
    asyncio.run(bot.start(token))


if __name__ == "__main__":
    init_db_site()

    threading.Thread(target=run_bot, daemon=True).start()

    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
