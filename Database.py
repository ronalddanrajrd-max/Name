import aiosqlite
import os

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
            script_access TEXT DEFAULT 'all',
            expires_at INTEGER DEFAULT NULL,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS blacklist (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            reason TEXT,
            added_by TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS warns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            guild_id TEXT,
            moderator_id TEXT,
            reason TEXT,
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
        CREATE TABLE IF NOT EXISTS ventes (
            order_id TEXT PRIMARY KEY,
            user_id TEXT,
            username TEXT,
            script_name TEXT,
            price REAL,
            payment_method TEXT,
            status TEXT DEFAULT 'pending',
            notes TEXT,
            staff_id TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now')),
            completed_at INTEGER
        );
        CREATE TABLE IF NOT EXISTS scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            price REAL,
            category TEXT DEFAULT 'general',
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS giveaways (
            message_id TEXT PRIMARY KEY,
            channel_id TEXT,
            prize TEXT,
            winners_count INTEGER DEFAULT 1,
            host_id TEXT,
            participants TEXT DEFAULT '[]',
            ended INTEGER DEFAULT 0,
            ends_at INTEGER,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS levels (
            user_id TEXT,
            guild_id TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0,
            messages INTEGER DEFAULT 0,
            PRIMARY KEY(user_id, guild_id)
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            note TEXT,
            added_by TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS suggestions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            message_id TEXT,
            content TEXT,
            status TEXT DEFAULT 'pending',
            response TEXT,
            staff_id TEXT,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        );
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
