from flask import Flask, request, redirect, session, render_template_string
import sqlite3
import os
import threading
import asyncio
import requests

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


STYLE = """
<style>
body{
background:#020617;
color:white;
font-family:Arial;
margin:0;
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
margin:7px 0;
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

table{
width:100%;
border-collapse:collapse;
}

th,td{
padding:12px;
border-bottom:1px solid #334155;
text-align:left;
}

th{
color:#38bdf8;
}

.ok{
color:#22c55e;
font-weight:bold;
}

.pending{
color:#facc15;
font-weight:bold;
}
</style>
"""


def layout(content):
    return STYLE + f"""
    <div class="sidebar">
        <h2>⚡ OkveHUB</h2>

        <a href="/">Dashboard</a>
        <a href="/whitelist">Whitelist</a>
        <a href="/keys">Keys</a>
        <a href="/scripts">Scripts</a>
        <a href="/purchases">Purchases</a>
        <a href="/executions">Executions</a>
        <a href="/blacklist">Blacklist</a>
        <a href="/logout">Logout</a>
    </div>

    <div class="main">
        {content}
    </div>
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

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    token_res = requests.post(
        "https://discord.com/api/oauth2/token",
        data=data,
        headers=headers
    )

    token_json = token_res.json()
    access_token = token_json.get("access_token")

    if not access_token:
        return "Discord OAuth Error"

    user_res = requests.get(
        "https://discord.com/api/users/@me",
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    user = user_res.json()

    discord_id = user.get("id")

    if discord_id != os.getenv("OWNER_ID"):
        return "Access denied"

    session["admin"] = True
    session["discord_id"] = discord_id
    session["username"] = user.get("username")

    return redirect("/")


@app.route("/")
def home():
    if not protect():
        return redirect("/login")

    conn = db()

    whitelist_count = conn.execute(
        "SELECT COUNT(*) c FROM whitelist"
    ).fetchone()["c"]

    keys_count = conn.execute(
        "SELECT COUNT(*) c FROM keys"
    ).fetchone()["c"]

    scripts_count = conn.execute(
        "SELECT COUNT(*) c FROM scripts WHERE active=1"
    ).fetchone()["c"]

    purchases_count = conn.execute(
        "SELECT COUNT(*) c FROM purchases"
    ).fetchone()["c"]

    executions = conn.execute(
        "SELECT COUNT(*) c FROM execution_logs"
    ).fetchone()["c"]

    conn.close()

    return layout(f"""
    <h1>Dashboard</h1>

    <div class="grid">

        <div class="stat">
            <h2>{whitelist_count}</h2>
            <p>Whitelist Users</p>
        </div>

        <div class="stat">
            <h2>{keys_count}</h2>
            <p>Keys</p>
        </div>

        <div class="stat">
            <h2>{scripts_count}</h2>
            <p>Scripts</p>
        </div>

        <div class="stat">
            <h2>{purchases_count}</h2>
            <p>Purchases</p>
        </div>

        <div class="stat">
            <h2>{executions}</h2>
            <p>Executions</p>
        </div>

    </div>
    """)


@app.route("/whitelist")
def whitelist():
    if not protect():
        return redirect("/login")

    conn = db()

    rows = conn.execute(
        "SELECT * FROM whitelist ORDER BY created_at DESC"
    ).fetchall()

    conn.close()

    html = """
    <h1>Whitelist</h1>

    <div class="card">
    <table>

    <tr>
        <th>User ID</th>
        <th>Username</th>
        <th>Script</th>
        <th>HWID</th>
    </tr>

    {% for u in rows %}
    <tr>
        <td>{{u["user_id"]}}</td>
        <td>{{u["username"]}}</td>
        <td>{{u["script_access"]}}</td>
        <td>{{u["hwid"] or "None"}}</td>
    </tr>
    {% endfor %}

    </table>
    </div>
    """

    return layout(render_template_string(html, rows=rows))


@app.route("/keys")
def keys():
    if not protect():
        return redirect("/login")

    conn = db()

    rows = conn.execute(
        "SELECT * FROM keys ORDER BY created_at DESC"
    ).fetchall()

    conn.close()

    html = """
    <h1>Keys</h1>

    <div class="card">
    <table>

    <tr>
        <th>Key</th>
        <th>Script</th>
        <th>User</th>
        <th>Status</th>
    </tr>

    {% for k in rows %}
    <tr>
        <td>{{k["key_code"]}}</td>
        <td>{{k["script_name"]}}</td>
        <td>{{k["used_by"] or "Unused"}}</td>
        <td>{{k["status"] or "active"}}</td>
    </tr>
    {% endfor %}

    </table>
    </div>
    """

    return layout(render_template_string(html, rows=rows))


@app.route("/scripts")
def scripts():
    if not protect():
        return redirect("/login")

    conn = db()

    rows = conn.execute(
        "SELECT * FROM scripts WHERE active=1 ORDER BY id DESC"
    ).fetchall()

    conn.close()

    html = """
    <h1>Scripts</h1>

    <div class="card">
    <table>

    <tr>
        <th>Name</th>
        <th>Description</th>
        <th>Executions</th>
    </tr>

    {% for s in rows %}
    <tr>
        <td>{{s["name"]}}</td>
        <td>{{s["description"]}}</td>
        <td>{{s["executions"] or 0}}</td>
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

    rows = conn.execute(
        "SELECT * FROM purchases ORDER BY created_at DESC"
    ).fetchall()

    conn.close()

    html = """
    <h1>Purchases</h1>

    <div class="card">
    <table>

    <tr>
        <th>ID</th>
        <th>User</th>
        <th>Method</th>
        <th>Status</th>
        <th>TX</th>
    </tr>

    {% for p in rows %}
    <tr>
        <td>{{p["purchase_id"]}}</td>
        <td>{{p["username"]}}</td>
        <td>{{p["method"]}}</td>

        <td>
        {% if p["status"] == "completed" %}
        <span class="ok">Completed</span>
        {% else %}
        <span class="pending">Pending</span>
        {% endif %}
        </td>

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

    rows = conn.execute(
        "SELECT * FROM execution_logs ORDER BY created_at DESC LIMIT 100"
    ).fetchall()

    conn.close()

    html = """
    <h1>Executions</h1>

    <div class="card">
    <table>

    <tr>
        <th>User</th>
        <th>Key</th>
        <th>Script</th>
        <th>Executor</th>
        <th>Status</th>
    </tr>

    {% for e in rows %}
    <tr>
        <td>{{e["user_id"]}}</td>
        <td>{{e["key_code"]}}</td>
        <td>{{e["script_name"]}}</td>
        <td>{{e["executor"] or "Unknown"}}</td>
        <td>{{e["status"]}}</td>
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

    rows = conn.execute(
        "SELECT * FROM blacklist ORDER BY created_at DESC"
    ).fetchall()

    conn.close()

    html = """
    <h1>Blacklist</h1>

    <div class="card">
    <table>

    <tr>
        <th>User</th>
        <th>Reason</th>
    </tr>

    {% for b in rows %}
    <tr>
        <td>{{b["username"]}}</td>
        <td>{{b["reason"]}}</td>
    </tr>
    {% endfor %}

    </table>
    </div>
    """

    return layout(render_template_string(html, rows=rows))


@app.route("/load")
def load_script():
    user_agent = request.headers.get("User-Agent", "").lower()

    blocked_agents = [
        "mozilla",
        "chrome",
        "safari",
        "firefox",
        "edge"
    ]

    if any(agent in user_agent for agent in blocked_agents):
        return "Access denied", 403

    key = request.args.get("key", "").strip().upper()
    hwid = request.args.get("hwid", "").strip()
    executor = request.args.get("executor", "Unknown")

    conn = db()

    key_row = conn.execute(
        "SELECT * FROM keys WHERE key_code=?",
        (key,)
    ).fetchone()

    if not key_row:
        conn.close()
        return "print('Invalid key')"

    user_id = key_row["used_by"]

    wl = conn.execute(
        "SELECT * FROM whitelist WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if not wl:
        conn.close()
        return "print('Access denied')"

    if wl["hwid"] and hwid and wl["hwid"] != hwid:
        conn.close()
        return "print('HWID mismatch')"

    if not wl["hwid"] and hwid:
        conn.execute(
            "UPDATE whitelist SET hwid=? WHERE user_id=?",
            (hwid, user_id)
        )

    script_name = key_row["script_name"] or "main"

    script = conn.execute(
        "SELECT * FROM scripts WHERE name=? AND active=1",
        (script_name,)
    ).fetchone()

    if not script:
        conn.close()
        return "print('Script not found')"

    conn.execute(
        "UPDATE scripts SET executions = COALESCE(executions,0)+1 WHERE name=?",
        (script_name,)
    )

    conn.execute("""
    INSERT INTO execution_logs
    (user_id,key_code,script_name,hwid,executor,status)
    VALUES(?,?,?,?,?,?)
    """, (
        user_id,
        key,
        script_name,
        hwid,
        executor,
        "success"
    ))

    conn.commit()
    conn.close()

    return script["code"] or "print('Empty script')"


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
    threading.Thread(target=run_bot, daemon=True).start()

    port = int(os.getenv("PORT", 3000))

    app.run(
        host="0.0.0.0",
        port=port
    )
