from flask import Flask, request, redirect, session, render_template_string
import sqlite3, os, threading, asyncio, secrets
from Bot import OkveHUBBot

app = Flask(__name__)
app.secret_key = os.getenv("ADMIN_SECRET", "change-moi")
DB_PATH = "okvehub.db"

def init_extra_db():
    conn = db()

    # TABLE SCRIPTS
    conn.execute("""
    CREATE TABLE IF NOT EXISTS scripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT,
        price REAL DEFAULT 0,
        category TEXT DEFAULT 'general',
        active INTEGER DEFAULT 1,
        code TEXT
    )
    """)

    # TABLE KEYS
    conn.execute("""
    CREATE TABLE IF NOT EXISTS keys (
        key_code TEXT PRIMARY KEY,
        script_name TEXT DEFAULT 'main',
        used_by TEXT,
        used_at INTEGER,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )
    """)

    # SCRIPT PAR DÉFAUT
    conn.execute("""
    INSERT OR IGNORE INTO scripts
    (name, description, price, category, active, code)
    VALUES
    (
        'main',
        'Script principal',
        0,
        'main',
        1,
        '-- colle ton script ici'
    )
    """)

    conn.commit()
    conn.close()

STYLE = """
<style>
body{margin:0;background:#0f172a;color:white;font-family:Arial}
.sidebar{position:fixed;width:220px;height:100vh;background:#020617;padding:25px}
.sidebar h2{color:#38bdf8}
.sidebar a{display:block;color:#cbd5e1;text-decoration:none;margin:18px 0}
.main{margin-left:260px;padding:30px}
.card{background:#1e293b;padding:22px;border-radius:16px;margin-bottom:20px;box-shadow:0 10px 25px #0005}
input,textarea,select{width:100%;padding:12px;border-radius:10px;border:0;margin:8px 0;background:#334155;color:white}
button{background:#38bdf8;border:0;padding:12px 18px;border-radius:10px;font-weight:bold;cursor:pointer}
table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:12px;overflow:hidden}
th,td{padding:12px;border-bottom:1px solid #334155;text-align:left}
.badge{padding:5px 10px;border-radius:999px;background:#22c55e;color:#052e16}
.danger{background:#ef4444;color:white}
</style>
"""

def layout(content):
    return STYLE + f"""
    <div class="sidebar">
        <h2>OkveHUB</h2>
        <a href="/">Dashboard</a>
        <a href="/whitelist">Whitelist</a>
        <a href="/scripts">Scripts</a>
        <a href="/keys">Keys</a>
        <a href="/logout">Déconnexion</a>
    </div>
    <div class="main">{content}</div>
    """

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form["password"] == os.getenv("ADMIN_PASSWORD", "admin123"):
            session["admin"] = True
            return redirect("/")
    return STYLE + """
    <div style="max-width:400px;margin:120px auto" class="card">
        <h1>Connexion Admin</h1>
        <form method="post">
            <input type="password" name="password" placeholder="Mot de passe admin">
            <button>Se connecter</button>
        </form>
    </div>
    """

def protect():
    return session.get("admin") == True

@app.route("/")
def home():
    if not protect(): return redirect("/login")
    conn = db()
    wl = conn.execute("SELECT COUNT(*) c FROM whitelist").fetchone()["c"]
    keys = conn.execute("SELECT COUNT(*) c FROM keys").fetchone()["c"]
    scripts = conn.execute("SELECT COUNT(*) c FROM scripts WHERE active=1").fetchone()["c"]
    conn.close()
    return layout(f"""
    <h1>Dashboard</h1>
    <div class="card"><h2>Whitelist</h2><p>{wl} utilisateurs</p></div>
    <div class="card"><h2>Keys</h2><p>{keys} clés créées</p></div>
    <div class="card"><h2>Scripts</h2><p>{scripts} scripts actifs</p></div>
    """)

@app.route("/whitelist")
def whitelist():
    if not protect(): return redirect("/login")
    conn = db()
    rows = conn.execute("SELECT * FROM whitelist ORDER BY created_at DESC").fetchall()
    conn.close()
    html = """
    <h1>Whitelist</h1>
    <div class="card">
    <table>
    <tr><th>User ID</th><th>Username</th><th>Script</th><th>HWID</th><th>Action</th></tr>
    {% for u in rows %}
    <tr>
        <td>{{u["user_id"]}}</td>
        <td>{{u["username"]}}</td>
        <td>{{u["script_access"]}}</td>
        <td>{{u["hwid"] or "Aucun"}}</td>
        <td><a href="/remove/{{u['user_id']}}">Supprimer</a></td>
    </tr>
    {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))

@app.route("/remove/<user_id>")
def remove(user_id):
    if not protect(): return redirect("/login")
    conn = db()
    conn.execute("DELETE FROM whitelist WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return redirect("/whitelist")

@app.route("/scripts", methods=["GET","POST"])
def scripts():
    if not protect(): return redirect("/login")
    conn = db()
    if request.method == "POST":
        conn.execute("""
        INSERT INTO scripts (name, description, price, category, active, code)
        VALUES (?, ?, 0, 'main', 1, ?)
        ON CONFLICT(name) DO UPDATE SET code=excluded.code, description=excluded.description
        """, (request.form["name"], request.form["description"], request.form["code"]))
        conn.commit()
    rows = conn.execute("SELECT * FROM scripts WHERE active=1").fetchall()
    conn.close()
    html = """
    <h1>Scripts</h1>
    <div class="card">
        <h2>Modifier / Ajouter un script</h2>
        <form method="post">
            <input name="name" value="main" placeholder="Nom du script">
            <input name="description" placeholder="Description">
            <textarea name="code" rows="12" placeholder="Colle ton script ici"></textarea>
            <button>Enregistrer</button>
        </form>
    </div>
    <div class="card">
    <table>
    <tr><th>Nom</th><th>Description</th></tr>
    {% for s in rows %}
    <tr><td>{{s["name"]}}</td><td>{{s["description"]}}</td></tr>
    {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows))

@app.route("/keys", methods=["GET","POST"])
def keys():
    if not protect(): return redirect("/login")
    conn = db()
    if request.method == "POST":
        key = "OKV-" + secrets.token_hex(4).upper()
        conn.execute("INSERT INTO keys (key_code, script_name) VALUES (?,?)", (key, request.form["script_name"]))
        conn.commit()
    scripts = conn.execute("SELECT name FROM scripts WHERE active=1").fetchall()
    rows = conn.execute("SELECT * FROM keys ORDER BY created_at DESC").fetchall()
    conn.close()
    html = """
    <h1>Keys</h1>
    <div class="card">
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
    <table>
    <tr><th>Key</th><th>Script</th><th>Utilisée par</th></tr>
    {% for k in rows %}
    <tr>
        <td>{{k["key_code"]}}</td>
        <td>{{k["script_name"]}}</td>
        <td>{{k["used_by"] or "Non utilisée"}}</td>
    </tr>
    {% endfor %}
    </table>
    </div>
    """
    return layout(render_template_string(html, rows=rows, scripts=scripts))

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

def run_bot():
    token = os.getenv("TOKEN")
    if token:
        bot = OkveHUBBot()
        asyncio.run(bot.start(token))

if __name__ == "__main__":
    init_extra_db()
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
