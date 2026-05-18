import discord
from discord.ext import commands
import asyncio
import os
import time
from dotenv import load_dotenv

from Database import init_db
import Logger

load_dotenv()

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
        # Base de données
        Logger.info("Initialisation de la base de données...")
        await init_db()
        Logger.success("Base de données prête !")

        # Cogs à charger
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
            "Roles",
            "Site",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                Logger.success(f"Cog chargé: {cog}")
            except Exception as e:
                Logger.error(f"Erreur chargement {cog}: {e}")

        # Recharger les panels persistants après redémarrage Railway
        try:
            from Tickets import TicketSelectView, TicketControls
            self.add_view(TicketSelectView())
            self.add_view(TicketControls())
            Logger.success("Panels Tickets rechargés")
        except Exception as e:
            Logger.error(f"Erreur panels Tickets: {e}")

        try:
            from Whitelist import WhitelistPanel
            self.add_view(WhitelistPanel())
            Logger.success("Panel Whitelist rechargé")
        except Exception as e:
            Logger.error(f"Erreur panel Whitelist: {e}")

        try:
            from Roles import RolePanel
            self.add_view(RolePanel())
            Logger.success("Panel Roles rechargé")
        except Exception as e:
            Logger.error(f"Erreur panel Roles: {e}")

        # Synchronisation des commandes slash
        guild_id = os.getenv("GUILD_ID")

        try:
            if guild_id:
                guild = discord.Object(id=int(guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                Logger.success(f"{len(synced)} commande(s) synchronisée(s) sur le serveur")
            else:
                synced = await self.tree.sync()
                Logger.success(f"{len(synced)} commande(s) synchronisée(s) globalement")
        except Exception as e:
            Logger.error(f"Erreur sync commandes: {e}")

    async def on_ready(self):
        Logger.success("=" * 50)
        Logger.success(f"OkveHUB Bot connecté — {self.user}")
        Logger.success(f"ID: {self.user.id}")
        Logger.success(f"Serveurs: {len(self.guilds)}")
        Logger.success("=" * 50)

        try:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="OkveHUB 🛡️"
                ),
                status=discord.Status.online
            )
        except:
            pass


async def main():
    token = os.getenv("TOKEN")

    if not token:
        Logger.error("TOKEN manquant dans les variables Railway.")
        return

    bot = OkveHUBBot()

    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
