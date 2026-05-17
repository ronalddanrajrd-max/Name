import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "../data/okvehub.db")

async def get_db():
    return await aiosqlite.connect(DB_PATH)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS whitelist (
            user_id     TEXT PRIMARY KEY,
            added_by    TEXT NOT NULL,
            added_at    INTEGER NOT NULL,
            reason      TEXT DEFAULT 'Aucune raison',
            script      TEXT DEFAULT 'Global',
            expires_at  INTEGER DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS infractions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT NOT NULL,
            guild_id     TEXT NOT NULL,
            type         TEXT NOT NULL,
            reason       TEXT NOT NULL,
            moderator_id TEXT NOT NULL,
            created_at   INTEGER NOT NULL,
            expires_at   INTEGER DEFAULT NULL,
            active       INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS levels (
            user_id        TEXT NOT NULL,
            guild_id       TEXT NOT NULL,
            xp             INTEGER DEFAULT 0,
            level          INTEGER DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            last_message   INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id  TEXT UNIQUE NOT NULL,
            user_id     TEXT NOT NULL,
            guild_id    TEXT NOT NULL,
            category    TEXT DEFAULT 'support',
            status      TEXT DEFAULT 'open',
            created_at  INTEGER NOT NULL,
            closed_at   INTEGER DEFAULT NULL,
            closed_by   TEXT DEFAULT NULL
        );

        CREATE TABLE IF NOT EXISTS giveaways (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id    TEXT UNIQUE,
            channel_id    TEXT NOT NULL,
            guild_id      TEXT NOT NULL,
            host_id       TEXT NOT NULL,
            prize         TEXT NOT NULL,
            winners_count INTEGER DEFAULT 1,
            entries       TEXT DEFAULT '[]',
            ends_at       INTEGER NOT NULL,
            ended         INTEGER DEFAULT 0,
            created_at    INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS automod (
            guild_id       TEXT PRIMARY KEY,
            anti_spam      INTEGER DEFAULT 1,
            anti_invite    INTEGER DEFAULT 1,
            anti_caps      INTEGER DEFAULT 1,
            anti_mention   INTEGER DEFAULT 1,
            anti_link      INTEGER DEFAULT 0,
            max_mentions   INTEGER DEFAULT 5,
            caps_threshold INTEGER DEFAULT 70,
            spam_threshold INTEGER DEFAULT 5,
            spam_interval  INTEGER DEFAULT 5,
            log_channel    TEXT DEFAULT NULL,
            bypass_roles   TEXT DEFAULT '[]',
            banned_words   TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id        TEXT PRIMARY KEY,
            welcome_message TEXT DEFAULT 'Bienvenue {user} sur OkveHUB !',
            leave_message   TEXT DEFAULT '{username} a quitté le serveur.',
            xp_rate         INTEGER DEFAULT 15,
            xp_cooldown     INTEGER DEFAULT 60,
            level_roles     TEXT DEFAULT '[]',
            boost_message   TEXT DEFAULT '{user} vient de booster le serveur !'
        );

        CREATE TABLE IF NOT EXISTS staff_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT NOT NULL,
            guild_id   TEXT NOT NULL,
            author_id  TEXT NOT NULL,
            content    TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tags (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   TEXT NOT NULL,
            name       TEXT NOT NULL,
            content    TEXT NOT NULL,
            author_id  TEXT NOT NULL,
            uses       INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,
            UNIQUE(guild_id, name)
        );

        CREATE TABLE IF NOT EXISTS blacklist (
            user_id  TEXT PRIMARY KEY,
            reason   TEXT NOT NULL,
            added_by TEXT NOT NULL,
            added_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reminders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            content    TEXT NOT NULL,
            remind_at  INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            sent       INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS suggestions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    TEXT NOT NULL,
            guild_id   TEXT NOT NULL,
            message_id TEXT,
            content    TEXT NOT NULL,
            status     TEXT DEFAULT 'pending',
            upvotes    INTEGER DEFAULT 0,
            downvotes  INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        """)
        await db.commit()
    print("✅ Base de données initialisée.")
