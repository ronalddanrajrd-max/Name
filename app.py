# Copie tout ce contenu dans ton fichier app.py

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

```
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

conn.execute("""
CREATE TABLE IF NOT EXISTS purchases (
    purchase_id TEXT PRIMARY KEY,
    user_id TEXT,
    username TEXT,
    method TEXT,
    script_name TEXT DEFAULT 'main',
    amount_ltc REAL,
    status TEXT DEFAULT 'pending',
    created_at INTEGER DEFAULT (strftime('%s','now')),
    completed_at INTEGER,
    tx_hash TEXT
)
""")

conn.execute("""
INSERT OR IGNORE INTO scripts
(name, description, price, category, active, code, executions)
VALUES
('main', 'Script principal OkveHUB', 0, 'main', 1, 'print("OkveHUB Loaded")', 0)
""")

conn.commit()
conn.close()
```

STYLE = """

<style>
body{
margin:0;
background:#020617;
color:white;
font-family:Arial;
}
.sidebar{
position:fixed;
left:0;
top:0;
width:250px;
height:100vh;
background:#0f172a;
padding:25px;
border-right:1px solid #1e293b;
}
.sidebar h2{
color:#38bdf8;
}
.sidebar a{
display:block;
color:#cbd5e1;
text-decoration:none;
padding:12px;
border-radius:10px;
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
.card{
background:#111827;
padding:20px;
border-radius:18px;
margin-bottom:20px;
border:1px solid #334155;
}
.grid{
display:grid;
grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
gap:20px;
}
.stat{
background:#0f172a;
padding:20px;
border-radius:18px;
border:1px solid #334155;
}
.stat h2{
color:#38bdf8;
font-size:34px;
margin:0;
}
input,textarea,select{
width:100%;
padding:12px;
margin:8px 0;
border-radius:10px;
border:1px solid #334155;
background:#020617;
color:white;
}
button{
background:#38bdf8;
border:0;
padding:12px 18px;
border-radius:10px;
font-weight:bold;
cursor:pointer;
}
table{
width:100%;
border-collapse:collapse;
}
th,td{
padding:12px;
border-bottom:1px solid #334155;
text-align:left;
}
a{
color:#38bdf8;
}
.danger{
color:#fb7185;
}
.ok{
color:#22c55e;
}
</style>

"""

def layout(content):
return STYLE + f""" <div class="sidebar"> <h2>⚡ OkveHUB</h2> <a href="/">Dashboard</a> <a href="/whitelist">Whitelist</a> <a href="/scripts">Scripts</a> <a href="/keys">Keys</a> <a href="/purchases">Purchases</a> <a href="/logout">Déconnexion</a> </div> <div class="main">{content}</div>
"""

def protect():
return session.get("admin") is True

@app.route("/login", methods=["GET", "POST"])
def login():
if request.method == "POST":
if request.form.get("password") == os.getenv("ADMIN_PASSWORD", "admin123"):
session["admin"] = True
return redirect("/")

```
return STYLE + """
<div style="max-width:420px;margin:120px auto" class="card">
    <h1>Connexion Admin</h1>
    <form method="post">
        <input type="password" name="password" placeholder="Mot de passe admin">
        <button>Connexion</button>
    </form>
</div>
"""
```

@app.route("/")
def home():
if not protect():
return redirect("/login")

```
conn = db()

whitelist_count = conn.execute("SELECT COUNT(*) c FROM whitelist").fetchone()["c"]
keys_count = conn.execute("SELECT COUNT(*) c FROM keys").fetchone()["c"]
scripts_count = conn.execute("SELECT COUNT(*) c FROM scripts WHERE active=1").fetchone()["c"]
purchases_count = conn.execute("SELECT COUNT(*) c FROM purchases").fetchone()["c"]
executions = conn.execute("SELECT COALESCE(SUM(executions),0) c FROM scripts").fetchone()["c"]

conn.close()

return layout(f"""
<h1>Dashboard</h1>

<div class="grid">
    <div class="stat"><h2>{whitelist_count}</h2><p>Whitelist</p></div>
    <div class="stat"><h2>{keys_count}</h2><p>Keys</p></div>
    <div class="stat"><h2>{scripts_count}</h2><p>Scripts</p></div>
    <div class="stat"><h2>{purchases_count}</h2><p>Purchases</p></div>
    <div class="stat"><h2>{executions}</h2><p>Executions</p></div>
</div>
""")
```

@app.route("/scripts", methods=["GET", "POST"])
def scripts():
if not protect():
return redirect("/login")

```
conn = db()

if request.method == "POST":
    name = request.form.get("name")
    description = request.form.get("description")
    code = request.form.get("code")

    conn.execute("""
    INSERT INTO scripts(name,description,active,code)
    VALUES(?,?,1,?)
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
    <form method="post">
        <input name="name" placeholder="Nom du script">
        <input name="description" placeholder="Description">
        <textarea name="code" rows="16" placeholder="Code Lua"></textarea>
        <button>Enregistrer</button>
    </form>
</div>

<div class="card">
<table>
    <tr>
        <th>Nom</th>
        <th>Description</th>
        <th>Executions</th>
        <th>Action</th>
    </tr>

    {% for s in rows %}
    <tr>
        <td>{{s["name"]}}</td>
        <td>{{s["description"]}}</td>
        <td>{{s["executions"]}}</td>
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
```

@app.route("/delete-script/<script_name>")
def delete_script(script_name):
if not protect():
return redirect("/login")

```
conn = db()
conn.execute("UPDATE scripts SET active=0 WHERE name=?", (script_name,))
conn.commit()
conn.close()

return redirect("/scripts")
```

@app.route("/keys")
def keys():
if not protect():
return redirect("/login")

```
conn = db()
rows = conn.execute("SELECT * FROM keys ORDER BY created_at DESC").fetchall()
conn.close()

html = """
<h1>Keys</h1>

<div class="card">
<table>
    <tr>
        <th>Key</th>
        <th>Script</th>
        <th>User</th>
    </tr>

    {% for k in rows %}
    <tr>
        <td>{{k["key_code"]}}</td>
        <td>{{k["script_name"]}}</td>
        <td>{{k["used_by"] or "Unused"}}</td>
    </tr>
    {% endfor %}
</table>
</div>
"""

return layout(render_template_string(html, rows=rows))
```

@app.route("/whitelist")
def whitelist():
if not protect():
return redirect("/login")

```
conn = db()
rows = conn.execute("SELECT * FROM whitelist ORDER BY created_at DESC").fetchall()
conn.close()

html = """
<h1>Whitelist</h1>

<div class="card">
<table>
    <tr>
        <th>User ID</th>
        <th>Username</th>
        <th>Script</th>
    </tr>

    {% for u in rows %}
    <tr>
        <td>{{u["user_id"]}}</td>
        <td>{{u["username"]}}</td>
        <td>{{u["script_access"]}}</td>
    </tr>
    {% endfor %}
</table>
</div>
"""

return layout(render_template_string(html, rows=rows))
```

@app.route("/purchases")
def purchases():
if not protect():
return redirect("/login")

```
conn = db()
rows = conn.execute("SELECT * FROM purchases ORDER BY created_at DESC").fetchall()
conn.close()

html = """
<h1>Purchases</h1>

<div class="card">
<table>
    <tr>
        <th>ID</th>
        <th>User</th>
        <th>Method</th>
        <th>Amount</th>
        <th>Status</th>
        <th>TX Hash</th>
    </tr>

    {% for p in rows %}
    <tr>
        <td>{{p["purchase_id"]}}</td>
        <td>{{p["username"]}}</td>
        <td>{{p["method"]}}</td>
        <td>{{p["amount_ltc"]}}</td>
        <td>
            {% if p["status"] == "completed" %}
            <span class="ok">Completed</span>
            {% else %}
            Pending
            {% endif %}
        </td>
        <td>{{p["tx_hash"] or "None"}}</td>
    </tr>
    {% endfor %}
</table>
</div>
"""

return layout(render_template_string(html, rows=rows))
```

@app.route("/load")
def load_script():
user_agent = request.headers.get("User-Agent", "").lower()

```
blocked_agents = [
    "mozilla",
    "chrome",
    "safari",
    "firefox",
    "edge",
    "opera"
]

if any(agent in user_agent for agent in blocked_agents):
    return "Access denied", 403

key = request.args.get("key", "").strip().upper()

conn = db()

row = conn.execute(
    "SELECT * FROM keys WHERE key_code=?",
    (key,)
).fetchone()

if not row:
    conn.close()
    return "print('Key invalide')"

script_name = row["script_name"] or "main"

script = conn.execute(
    "SELECT * FROM scripts WHERE name=? AND active=1",
    (script_name,)
).fetchone()

if not script:
    conn.close()
    return "print('Script introuvable')"

conn.execute(
    "UPDATE scripts SET executions = executions + 1 WHERE name=?",
    (script_name,)
)

conn.commit()
conn.close()

return script["code"] or "print('Script vide')"
```

@app.route("/logout")
def logout():
session.clear()
return redirect("/login")

def run_bot():
token = os.getenv("TOKEN")

```
if not token:
    print("TOKEN manquant")
    return

bot = OkveHUBBot()
asyncio.run(bot.start(token))
```

if **name** == "**main**":
init_db_site()

```
threading.Thread(target=run_bot, daemon=True).start()

port = int(os.getenv("PORT", 3000))
app.run(host="0.0.0.0", port=port)
```
