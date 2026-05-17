from flask import Flask, render_template_string
import sqlite3
import threading
import asyncio
import os
from Bot import OkveHUBBot

app = Flask(__name__)
DB_PATH = "okvehub.db"

@app.route("/")
def home():
    return """
    <h1>Panel Admin OkveHUB</h1>
    <p>Site connecté au bot ✅</p>
    <a href="/whitelist">Voir les whitelist</a>
    """

@app.route("/whitelist")
def whitelist():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM whitelist ORDER BY created_at DESC").fetchall()
    conn.close()

    html = """
    <h1>Liste Whitelist</h1>
    <table border="1" cellpadding="8">
        <tr>
            <th>User ID</th>
            <th>Username</th>
            <th>Script</th>
            <th>HWID</th>
        </tr>
        {% for user in rows %}
        <tr>
            <td>{{ user["user_id"] }}</td>
            <td>{{ user["username"] }}</td>
            <td>{{ user["script_access"] }}</td>
            <td>{{ user["hwid"] }}</td>
        </tr>
        {% endfor %}
    </table>
    """
    return render_template_string(html, rows=rows)

def run_bot():
    token = os.getenv("TOKEN")
    if not token:
        print("TOKEN manquant")
        return

    bot = OkveHUBBot()
    asyncio.run(bot.start(token))

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()

    port = int(os.getenv("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
