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

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

*{
    margin:0;
    padding:0;
    box-sizing:border-box;
}

body{
    background:#050816;
    color:white;
    font-family:'Inter',sans-serif;
    overflow-x:hidden;
}

/* SIDEBAR */

.sidebar{
    position:fixed;
    left:0;
    top:0;
    width:270px;
    height:100vh;
    background:linear-gradient(180deg,#0b1220,#090f1c);
    border-right:1px solid rgba(255,255,255,0.05);
    padding:24px;
    z-index:100;
}

.logo{
    display:flex;
    align-items:center;
    gap:12px;
    margin-bottom:35px;
}

.logo-icon{
    width:42px;
    height:42px;
    border-radius:12px;
    background:linear-gradient(135deg,#38bdf8,#6366f1);
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:18px;
    font-weight:bold;
    box-shadow:0 0 25px #38bdf855;
}

.logo h2{
    font-size:22px;
    font-weight:700;
}

.sidebar-links{
    display:flex;
    flex-direction:column;
    gap:8px;
}

.sidebar a{
    text-decoration:none;
    color:#94a3b8;
    padding:14px 16px;
    border-radius:14px;
    transition:0.25s;
    font-size:15px;
    font-weight:500;
    display:flex;
    align-items:center;
    gap:12px;
}

.sidebar a:hover{
    background:#111827;
    color:white;
    transform:translateX(3px);
}

.sidebar .active{
    background:linear-gradient(135deg,#38bdf8,#6366f1);
    color:white;
    box-shadow:0 0 20px #38bdf833;
}

/* MAIN */

.main{
    margin-left:270px;
    padding:35px;
    min-height:100vh;
    background:
    radial-gradient(circle at top right,#2563eb22,transparent 35%),
    radial-gradient(circle at bottom left,#7c3aed22,transparent 35%),
    #050816;
}

/* TOPBAR */

.topbar{
    display:flex;
    justify-content:space-between;
    align-items:center;
    margin-bottom:30px;
}

.topbar h1{
    font-size:34px;
    font-weight:700;
}

.profile{
    display:flex;
    align-items:center;
    gap:14px;
    background:#0f172a;
    padding:10px 16px;
    border-radius:14px;
    border:1px solid rgba(255,255,255,0.05);
}

.profile span{
    color:#cbd5e1;
    font-weight:600;
}

/* GRID */

.grid{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
    gap:22px;
    margin-bottom:25px;
}

/* CARDS */

.card{
    background:linear-gradient(180deg,#0f172a,#0b1220);
    border:1px solid rgba(255,255,255,0.06);
    border-radius:22px;
    padding:24px;
    position:relative;
    overflow:hidden;
    box-shadow:0 12px 40px rgba(0,0,0,0.4);
}

.card::before{
    content:'';
    position:absolute;
    top:-50px;
    right:-50px;
    width:120px;
    height:120px;
    background:#38bdf822;
    border-radius:50%;
}

.stat-title{
    color:#94a3b8;
    font-size:14px;
    margin-bottom:12px;
}

.stat-number{
    font-size:42px;
    font-weight:700;
    color:#38bdf8;
}

/* TABLE */

.table-card{
    background:linear-gradient(180deg,#0f172a,#0b1220);
    border-radius:22px;
    padding:24px;
    border:1px solid rgba(255,255,255,0.06);
    overflow:hidden;
}

table{
    width:100%;
    border-collapse:collapse;
}

th{
    text-align:left;
    color:#38bdf8;
    padding:16px;
    font-size:14px;
    border-bottom:1px solid rgba(255,255,255,0.06);
}

td{
    padding:16px;
    color:#cbd5e1;
    border-bottom:1px solid rgba(255,255,255,0.04);
}

tr:hover td{
    background:#111827;
}

/* BADGES */

.badge{
    padding:6px 12px;
    border-radius:999px;
    font-size:13px;
    font-weight:700;
}

.badge-success{
    background:#22c55e22;
    color:#22c55e;
}

.badge-warning{
    background:#facc1522;
    color:#facc15;
}

.badge-danger{
    background:#ef444422;
    color:#ef4444;
}

button{
    background:linear-gradient(135deg,#38bdf8,#6366f1);
    border:none;
    color:white;
    padding:13px 20px;
    border-radius:14px;
    font-weight:700;
    cursor:pointer;
}

input,
textarea{
    width:100%;
    padding:14px;
    border-radius:14px;
    border:1px solid rgba(255,255,255,0.08);
    background:#020617;
    color:white;
    margin-top:10px;
    margin-bottom:14px;
}

</style>
"""


def layout(content):
    return STYLE + f"""

<div class="sidebar">

    <div class="logo">
        <div class="logo-icon">⚡</div>
        <h2>OkveHUB</h2>
    </div>

    <div class="sidebar-links">
        <a class="active" href="/">📊 Dashboard</a>
        <a href="/whitelist">🔐 Whitelist</a>
        <a href="/keys">🔑 Keys</a>
        <a href="/scripts">📜 Scripts</a>
        <a href="/purchases">🛒 Purchases</a>
        <a href="/executions">🧠 Executions</a>
        <a href="/blacklist">⛔ Blacklist</a>
        <a href="/logout">🚪 Logout</a>
    </div>

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

    executions_count = conn.execute(
        "SELECT COUNT(*) c FROM execution_logs"
    ).fetchone()["c"]

    conn.close()

    html = f"""

<div class="topbar">

    <h1>Dashboard</h1>

    <div class="profile">
        <span>{session.get("username")}</span>
    </div>

</div>

<div class="grid">

    <div class="card">
        <div class="stat-title">Whitelist Users</div>
        <div class="stat-number">{whitelist_count}</div>
    </div>

    <div class="card">
        <div class="stat-title">Keys</div>
        <div class="stat-number">{keys_count}</div>
    </div>

    <div class="card">
        <div class="stat-title">Scripts</div>
        <div class="stat-number">{scripts_count}</div>
    </div>

    <div class="card">
        <div class="stat-title">Purchases</div>
        <div class="stat-number">{purchases_count}</div>
    </div>

    <div class="card">
        <div class="stat-title">Executions</div>
        <div class="stat-number">{executions_count}</div>
    </div>

</div>

"""

    return layout(html)

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

<div class="topbar">
    <h1>Whitelist</h1>
</div>

<div class="table-card">

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

<div class="topbar">
    <h1>Keys</h1>
</div>

<div class="table-card">

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
    <td>
        {% if k["status"] == "active" %}
            <span class="badge badge-success">Active</span>
        {% else %}
            <span class="badge badge-danger">Disabled</span>
        {% endif %}
    </td>
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

<div class="topbar">
    <h1>Scripts</h1>
</div>

<div class="table-card">

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

<div class="topbar">
    <h1>Purchases</h1>
</div>

<div class="table-card">

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
            <span class="badge badge-success">Completed</span>
        {% else %}
            <span class="badge badge-warning">Pending</span>
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

<div class="topbar">
    <h1>Executions</h1>
</div>

<div class="table-card">

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
    <td>
        {% if e["status"] == "success" %}
            <span class="badge badge-success">Success</span>
        {% else %}
            <span class="badge badge-danger">{{e["status"]}}</span>
        {% endif %}
    </td>
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

<div class="topbar">
    <h1>Blacklist</h1>
</div>

<div class="table-card">

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

    blocked_agents = ["mozilla", "chrome", "safari", "firefox", "edge", "opera", "brave"]

    if any(agent in user_agent for agent in blocked_agents):
        return "Access denied", 403

    key = request.args.get("key", "").strip().upper()
    hwid = request.args.get("hwid", "").strip()
    executor = request.args.get("executor", "Unknown").strip()

    conn = db()

    key_row = conn.execute(
        "SELECT * FROM keys WHERE key_code=?",
        (key,)
    ).fetchone()

    if not key_row:
        conn.close()
        return "print('Invalid key')"

    user_id = key_row["used_by"]
    script_name = key_row["script_name"] or "main"

    wl = conn.execute(
        "SELECT * FROM whitelist WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if not wl:
        conn.close()
        return "print('Access denied')"

    if wl["hwid"] and hwid and wl["hwid"] != hwid:
        conn.execute("""
        INSERT INTO execution_logs
        (user_id, key_code, script_name, hwid, executor, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            key,
            script_name,
            hwid,
            executor,
            "hwid_mismatch"
        ))

        conn.commit()
        conn.close()

        return "print('HWID mismatch')"

    if not wl["hwid"] and hwid:
        conn.execute(
            "UPDATE whitelist SET hwid=? WHERE user_id=?",
            (hwid, user_id)
        )

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
    (user_id, key_code, script_name, hwid, executor, status)
    VALUES (?, ?, ?, ?, ?, ?)
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
