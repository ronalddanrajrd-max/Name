import aiosqlite

DB_PATH = "okvehub.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
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
            script_version TEXT DEFAULT 'stable',
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

        CREATE TABLE IF NOT EXISTS script_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            script_name TEXT,
            version_name TEXT DEFAULT 'stable',
            code TEXT,
            active INTEGER DEFAULT 1,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            UNIQUE(script_name, version_name)
        );

        CREATE TABLE IF NOT EXISTS purchases (
            purchase_id TEXT PRIMARY KEY,
            user_id TEXT,
            username TEXT,
            method TEXT,
            script_name TEXT DEFAULT 'OkveHUB',
            script_version TEXT DEFAULT 'stable',
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
            script_version TEXT DEFAULT 'stable',
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

        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id TEXT PRIMARY KEY,
            user_id TEXT,
            channel_id TEXT,
            category TEXT DEFAULT 'support',
            status TEXT DEFAULT 'open',
            claimed_by TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            closed_at INTEGER
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
            "ALTER TABLE keys ADD COLUMN script_version TEXT DEFAULT 'stable'",
            "ALTER TABLE purchases ADD COLUMN script_version TEXT DEFAULT 'stable'",
            "ALTER TABLE execution_logs ADD COLUMN script_version TEXT DEFAULT 'stable'",
        ]:
            try:
                await db.execute(query)
            except Exception:
                pass

        await db.execute("""
        INSERT OR IGNORE INTO scripts
        (name, description, price, category, active, code, executions)
        VALUES
        ('OkveHUB', 'Script principal OkveHUB', 0, 'main', 1, 'print("OkveHUB Loaded")', 0)
        """)

        await db.execute("""
        INSERT OR IGNORE INTO script_versions
        (script_name, version_name, code, active)
        VALUES
        ('OkveHUB', 'stable', 'print("OkveHUB Stable Loaded")', 1)
        """)

        await db.execute("""
        INSERT OR IGNORE INTO script_versions
        (script_name, version_name, code, active)
        VALUES
        ('OkveHUB', 'beta', 'print("OkveHUB Beta Loaded")', 1)
        """)

        await db.execute("""
        INSERT OR IGNORE INTO script_versions
        (script_name, version_name, code, active)
        VALUES
        ('OkveHUB', 'dev', 'print("OkveHUB Dev Loaded")', 1)
        """)

        await db.commit()


async def db_execute(query, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()


async def db_fetchone(query, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            return await cursor.fetchone()


async def db_fetchall(query, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            return await cursor.fetchall()
