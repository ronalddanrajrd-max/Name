import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
from utils.database import init_db
from utils.logger import set_bot

load_dotenv()

# ===== INTENTS =====
intents = discord.Intents.all()

# ===== BOT =====
class OkveHUB(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",      # Prefix de secours (slash commands = principal)
            intents=intents,
            help_command=None,
        )
        self.spam_data: dict = {}   # Anti-spam : {user_id: [timestamps]}

    async def setup_hook(self):
        # Init base de données
        await init_db()

        # Charger tous les cogs
        cogs_dirs = [
            "cogs/admin", "cogs/moderation", "cogs/whitelist",
            "cogs/tickets", "cogs/giveaway", "cogs/levels",
            "cogs/announcements", "cogs/utility", "cogs/automod",
            "cogs/fun",
        ]
        loaded = 0
        for folder in cogs_dirs:
            if not os.path.exists(folder):
                continue
            for filename in os.listdir(folder):
                if filename.endswith(".py") and not filename.startswith("_"):
                    ext = f"{folder.replace('/', '.')}.{filename[:-3]}"
                    try:
                        await self.load_extension(ext)
                        print(f"  ✅ Cog chargé : {ext}")
                        loaded += 1
                    except Exception as e:
                        print(f"  ❌ Erreur cog {ext} : {e}")

        print(f"\n📦 {loaded} cogs chargés.\n")

        # Sync slash commands
        synced = await self.tree.sync()
        print(f"🔄 {len(synced)} commandes slash synchronisées.\n")

    async def on_ready(self):
        set_bot(self)
        print("╔══════════════════════════════╗")
        print("║     OkveHUB Bot v2.0         ║")
        print(f"║  Connecté : {self.user.name[:16]:<16}  ║")
        print(f"║  Serveurs : {len(self.guilds):<16}  ║")
        print("╚══════════════════════════════╝\n")

        # Statuts rotatifs
        self.loop.create_task(self._rotate_status())

    async def _rotate_status(self):
        statuses = [
            discord.Activity(type=discord.ActivityType.watching, name="OkveHUB 🛒"),
            discord.Activity(type=discord.ActivityType.playing,  name="/help | OkveHUB"),
            discord.Activity(type=discord.ActivityType.watching, name="vos scripts 👀"),
            discord.Activity(type=discord.ActivityType.listening, name="discord.gg/okvehub"),
        ]
        i = 0
        while True:
            await self.change_presence(activity=statuses[i % len(statuses)], status=discord.Status.online)
            i += 1
            await asyncio.sleep(15)

bot = OkveHUB()

if __name__ == "__main__":
    token = os.getenv("TOKEN")
    if not token:
        print("❌ TOKEN manquant dans le fichier .env !")
        exit(1)
    bot.run(token)
