"""
╔══════════════════════════════════════════════════════════╗
║           OKVEHUB BOT — Bot de Gestion Admin             ║
║          Développé pour OkveHUB Script Store             ║
╚══════════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands
import asyncio
import os
import time
from dotenv import load_dotenv
from Database import init_db
import Logger

load_dotenv()

# ══════════════════════════════════
#     CONFIGURATION DU BOT
# ══════════════════════════════════
intents = discord.Intents.all()

class OkveHUBBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        self.start_time = time.time()

    async def setup_hook(self):
        # Init base de données
        Logger.info("Initialisation de la base de données...")
        await init_db()
        Logger.success("Base de données prête !")

        # Charger tous les cogs
        cogs = [
    "Events",
    "Whitelist",
    "Moderation",
    "Tickets",
    "Admin",
    "Announcements",
    "Giveaway",
    "Levels",
    "Utility",
    "Reglement",
    "ReactionRole",
]


        for cog in cogs:
            try:
                await self.load_extension(cog)
                Logger.success(f"Cog chargé: {cog}")
            except Exception as e:
                Logger.error(f"Erreur chargement {cog}: {e}")

        # Synchroniser les slash commands
        guild_id = os.getenv("GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            Logger.success(f"{len(synced)} commande(s) synchronisée(s) sur le serveur")
        else:
            synced = await self.tree.sync()
            Logger.success(f"{len(synced)} commande(s) synchronisée(s) globalement")

    async def on_ready(self):
        Logger.success("=" * 50)
        Logger.success(f"  OkveHUB Bot — {self.user}")
        Logger.success(f"  ID: {self.user.id}")
        Logger.success(f"  Serveurs: {len(self.guilds)}")
        Logger.success("=" * 50)

# ══════════════════════════════════
#     KEEP ALIVE POUR RAILWAY
# ══════════════════════════════════
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OkveHUB Bot is alive!")
    def log_message(self, format, *args):
        pass  # Silence les logs HTTP

def run_health_server():
    port = int(os.getenv("PORT", 3000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    Logger.info(f"Health server démarré sur le port {port}")
    server.serve_forever()

# ══════════════════════════════════
#     LANCEMENT
# ══════════════════════════════════
async def main():
    token = os.getenv("TOKEN")
    if not token:
        Logger.error("TOKEN manquant dans les variables d'environnement !")
        Logger.error("Ajoute TOKEN=ton_token dans les variables Railway")
        return

    bot = OkveHUBBot()

    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    # Démarrer le serveur de santé dans un thread séparé
    health_thread = Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Lancer le bot
    asyncio.run(main())
