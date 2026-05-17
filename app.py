from flask import Flask, render_template_string
import sqlite3

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
    <br>
    <a href="/">Retour</a>
    """
    return render_template_string(html, rows=rows)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
