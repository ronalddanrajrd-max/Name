import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import time
import json
from utils.helpers import *
from utils.database import DB_PATH


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    admin = app_commands.Group(name="admin", description="Commandes d'administration OkveHUB")

    # ───── SAY ─────
    @admin.command(name="say", description="Faire parler le bot dans un salon")
    @app_commands.default_permissions(administrator=True)
    async def say(self, interaction: discord.Interaction, salon: discord.TextChannel, message: str):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        await salon.send(message)
        await interaction.response.send_message(embed=embed_success(f"✅ Message envoyé dans {salon.mention}."), ephemeral=True)

    # ───── EMBED ─────
    @admin.command(name="embed", description="Envoyer un embed personnalisé")
    @app_commands.default_permissions(administrator=True)
    async def send_embed(self, interaction: discord.Interaction,
                         salon: discord.TextChannel,
                         titre: str,
                         description: str,
                         couleur: str = "#5865F2"):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        try:
            color = int(couleur.lstrip("#"), 16)
        except Exception:
            color = Colors.MAIN
        embed = discord.Embed(title=titre, description=description, color=color)
        embed.timestamp = discord.utils.utcnow()
        await salon.send(embed=embed)
        await interaction.response.send_message(embed=embed_success("✅ Embed envoyé."), ephemeral=True)

    # ───── BLACKLIST ─────
    bl = app_commands.Group(name="blacklist", description="Gestion de la blacklist globale", parent=None)

    @admin.command(name="blacklist_add", description="Blacklister un utilisateur du bot")
    @app_commands.default_permissions(administrator=True)
    async def bl_add(self, interaction: discord.Interaction, utilisateur: discord.User, raison: str):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO blacklist VALUES (?,?,?,?)",
                             (str(utilisateur.id), raison, str(interaction.user.id), int(time.time())))
            await db.commit()
        await interaction.response.send_message(embed=embed_success(f"✅ **{utilisateur}** ajouté à la blacklist.\n**Raison :** {raison}"))

    @admin.command(name="blacklist_remove", description="Retirer de la blacklist")
    @app_commands.default_permissions(administrator=True)
    async def bl_remove(self, interaction: discord.Interaction, utilisateur: discord.User):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM blacklist WHERE user_id=?", (str(utilisateur.id),))
            await db.commit()
        await interaction.response.send_message(embed=embed_success(f"✅ **{utilisateur}** retiré de la blacklist."))

    # ───── CONFIG SERVEUR ─────
    @admin.command(name="config", description="Voir la config du serveur")
    @app_commands.default_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM guild_config WHERE guild_id=?", (str(interaction.guild.id),))
            cfg = await cur.fetchone()
            cur2 = await db.execute("SELECT * FROM automod WHERE guild_id=?", (str(interaction.guild.id),))
            am = await cur2.fetchone()

        embed = discord.Embed(title="⚙️ Configuration — OkveHUB", color=Colors.MAIN)
        if cfg:
            embed.add_field(name="💬 Message bienvenue", value=truncate(cfg["welcome_message"], 100), inline=False)
            embed.add_field(name="📤 Message départ", value=truncate(cfg["leave_message"], 100), inline=False)
            embed.add_field(name="⭐ Taux XP", value=str(cfg["xp_rate"]), inline=True)
            embed.add_field(name="⏱️ Cooldown XP", value=f"{cfg['xp_cooldown']}s", inline=True)
        if am:
            embed.add_field(name="🛡️ Anti-Spam", value="✅" if am["anti_spam"] else "❌", inline=True)
            embed.add_field(name="🔗 Anti-Invite", value="✅" if am["anti_invite"] else "❌", inline=True)
            embed.add_field(name="🔠 Anti-Caps", value="✅" if am["anti_caps"] else "❌", inline=True)
            embed.add_field(name="📣 Anti-Mention", value="✅" if am["anti_mention"] else "❌", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ───── SET WELCOME ─────
    @admin.command(name="setwelcome", description="Changer le message de bienvenue")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(message="Message ({user}, {username}, {server}, {count})")
    async def setwelcome(self, interaction: discord.Interaction, message: str):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO guild_config (guild_id, welcome_message) VALUES (?,?)
                ON CONFLICT(guild_id) DO UPDATE SET welcome_message=?
            """, (str(interaction.guild.id), message, message))
            await db.commit()
        await interaction.response.send_message(embed=embed_success(f"✅ Message de bienvenue mis à jour.\n**Aperçu :** {message.replace('{user}', interaction.user.mention)}"))

    # ───── ROLE TOUS ─────
    @admin.command(name="role", description="Ajouter/Retirer un rôle à tous les membres")
    @app_commands.default_permissions(administrator=True)
    @app_commands.choices(action=[app_commands.Choice(name="Ajouter", value="add"), app_commands.Choice(name="Retirer", value="remove")])
    async def mass_role(self, interaction: discord.Interaction, action: str, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        count = 0
        for member in interaction.guild.members:
            if member.bot:
                continue
            try:
                if action == "add" and role not in member.roles:
                    await member.add_roles(role)
                    count += 1
                elif action == "remove" and role in member.roles:
                    await member.remove_roles(role)
                    count += 1
            except Exception:
                pass
        verb = "ajouté à" if action == "add" else "retiré de"
        await interaction.followup.send(embed=embed_success(f"✅ Rôle {role.mention} **{verb}** **{count}** membres."), ephemeral=True)

    # ───── CLEAR BANS ─────
    @admin.command(name="clearbans", description="Voir la liste des bans")
    @app_commands.default_permissions(administrator=True)
    async def clearbans(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        bans = [b async for b in interaction.guild.bans(limit=50)]
        if not bans:
            return await interaction.response.send_message(embed=embed_info("Aucun ban."), ephemeral=True)
        desc = "\n".join(f"`{b.user.id}` — **{b.user}** — {truncate(b.reason or 'Aucune raison', 60)}" for b in bans[:20])
        embed = discord.Embed(title=f"🔨 Bans ({len(bans)})", description=desc, color=Colors.ERROR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ───── STATS BOT ─────
    @admin.command(name="stats", description="Statistiques du bot")
    @app_commands.default_permissions(administrator=True)
    async def stats(self, interaction: discord.Interaction):
        import platform, sys
        guild = interaction.guild
        embed = discord.Embed(title="📊 Stats — OkveHUB Bot", color=Colors.MAIN)
        embed.add_field(name="🏠 Serveurs", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="👥 Membres (serveur)", value=str(guild.member_count), inline=True)
        embed.add_field(name="🏓 Latence", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="🐍 Python", value=platform.python_version(), inline=True)
        embed.add_field(name="📦 discord.py", value=discord.__version__, inline=True)
        embed.add_field(name="💬 Commandes", value=str(len(self.bot.tree.get_commands())), inline=True)

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT COUNT(*) FROM whitelist")
            wl_count = (await cur.fetchone())[0]
            cur2 = await db.execute("SELECT COUNT(*) FROM infractions")
            inf_count = (await cur2.fetchone())[0]
            cur3 = await db.execute("SELECT COUNT(*) FROM tickets")
            tk_count = (await cur3.fetchone())[0]

        embed.add_field(name="✅ Whitelist", value=str(wl_count), inline=True)
        embed.add_field(name="⚠️ Infractions", value=str(inf_count), inline=True)
        embed.add_field(name="🎫 Tickets total", value=str(tk_count), inline=True)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
