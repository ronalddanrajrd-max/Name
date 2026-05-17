import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import time
from utils.helpers import *
from utils.database import DB_PATH


class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ───── HELP ─────
    @app_commands.command(name="help", description="Liste toutes les commandes du bot")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📚 OkveHUB Bot — Commandes",
            description="Bot de gestion complet pour **OkveHUB**",
            color=Colors.MAIN
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)

        embed.add_field(name="🔨 Modération", value="`/ban` `/unban` `/kick` `/mute` `/unmute` `/warn` `/infractions` `/clearwarn` `/purge` `/lock` `/unlock` `/slowmode` `/nickname`", inline=False)
        embed.add_field(name="✅ Whitelist", value="`/whitelist add` `/whitelist remove` `/whitelist check` `/whitelist list` `/whitelist search`", inline=False)
        embed.add_field(name="🎫 Tickets", value="`/ticket panel` `/ticket open` `/ticket close` `/ticket add` `/ticket remove` `/ticket list`", inline=False)
        embed.add_field(name="🎉 Giveaway", value="`/giveaway create` `/giveaway end` `/giveaway reroll` `/giveaway list`", inline=False)
        embed.add_field(name="📊 Niveaux", value="`/niveau rank` `/niveau top` `/niveau setxp` `/niveau reset`", inline=False)
        embed.add_field(name="📢 Annonces", value="`/annonce envoyer` `/annonce update` `/annonce promo` `/annonce dm` `/annonce embed_simple`", inline=False)
        embed.add_field(name="🔧 Automod", value="`/automod config` `/automod status` `/automod motsbanni`", inline=False)
        embed.add_field(name="🛠️ Utilitaire", value="`/help` `/ping` `/avatar` `/banner` `/tag` `/reminder` `/suggestion` `/userinfo` `/serverinfo` `/roleinfo` `/note`", inline=False)
        embed.add_field(name="🎮 Admin", value="`/admin embed` `/admin role` `/admin say` `/admin blacklist` `/admin config`", inline=False)

        embed.set_footer(text=f"OkveHUB Bot • {len(self.bot.tree.get_commands())} commandes")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ───── PING ─────
    @app_commands.command(name="ping", description="Voir la latence du bot")
    async def ping(self, interaction: discord.Interaction):
        ws_lat = round(self.bot.latency * 1000)
        embed = discord.Embed(title="🏓 Pong !", color=Colors.SUCCESS)
        embed.add_field(name="🌐 WebSocket", value=f"**{ws_lat}ms**", inline=True)
        color = Colors.SUCCESS if ws_lat < 100 else Colors.WARNING if ws_lat < 200 else Colors.ERROR
        embed.color = color
        await interaction.response.send_message(embed=embed)

    # ───── AVATAR ─────
    @app_commands.command(name="avatar", description="Voir l'avatar d'un membre")
    async def avatar(self, interaction: discord.Interaction, membre: discord.Member = None):
        user = membre or interaction.user
        embed = discord.Embed(title=f"🖼️ Avatar — {user.name}", color=Colors.MAIN)
        embed.set_image(url=user.display_avatar.url)
        embed.add_field(name="Liens", value=f"[PNG]({user.display_avatar.with_format('png').url}) | [JPG]({user.display_avatar.with_format('jpeg').url}) | [WEBP]({user.display_avatar.url})")
        await interaction.response.send_message(embed=embed)

    # ───── BANNER ─────
    @app_commands.command(name="banner", description="Voir la bannière d'un membre")
    async def banner(self, interaction: discord.Interaction, membre: discord.Member = None):
        user = membre or interaction.user
        fetched = await self.bot.fetch_user(user.id)
        if not fetched.banner:
            return await interaction.response.send_message(embed=embed_info(f"**{user.name}** n'a pas de bannière."), ephemeral=True)
        embed = discord.Embed(title=f"🎨 Bannière — {user.name}", color=Colors.MAIN)
        embed.set_image(url=fetched.banner.url)
        await interaction.response.send_message(embed=embed)

    # ───── TAG ─────
    tag_group = app_commands.Group(name="tag", description="Tags / réponses personnalisées")

    @tag_group.command(name="create", description="Créer un tag")
    @app_commands.default_permissions(manage_messages=True)
    async def tag_create(self, interaction: discord.Interaction, nom: str, contenu: str):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            try:
                await db.execute("INSERT INTO tags (guild_id,name,content,author_id,created_at) VALUES (?,?,?,?,?)",
                                 (str(interaction.guild.id), nom.lower(), contenu, str(interaction.user.id), int(time.time())))
                await db.commit()
                await interaction.response.send_message(embed=embed_success(f"✅ Tag `{nom}` créé."))
            except Exception:
                await interaction.response.send_message(embed=embed_error(f"Un tag `{nom}` existe déjà."), ephemeral=True)

    @tag_group.command(name="get", description="Afficher un tag")
    async def tag_get(self, interaction: discord.Interaction, nom: str):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM tags WHERE guild_id=? AND name=?", (str(interaction.guild.id), nom.lower()))
            tag = await cur.fetchone()
        if not tag:
            return await interaction.response.send_message(embed=embed_error(f"Tag `{nom}` introuvable."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE tags SET uses=uses+1 WHERE guild_id=? AND name=?", (str(interaction.guild.id), nom.lower()))
            await db.commit()
        embed = discord.Embed(description=tag["content"], color=Colors.MAIN)
        embed.set_footer(text=f"Tag: {nom} • {tag['uses']+1} utilisations")
        await interaction.response.send_message(embed=embed)

    @tag_group.command(name="list", description="Voir tous les tags du serveur")
    async def tag_list(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT name, uses FROM tags WHERE guild_id=? ORDER BY uses DESC", (str(interaction.guild.id),))
            rows = await cur.fetchall()
        if not rows:
            return await interaction.response.send_message(embed=embed_info("Aucun tag créé."), ephemeral=True)
        desc = "\n".join(f"`{r['name']}` — {r['uses']} utilisations" for r in rows[:25])
        embed = discord.Embed(title=f"🏷️ Tags ({len(rows)})", description=desc, color=Colors.MAIN)
        await interaction.response.send_message(embed=embed)

    @tag_group.command(name="delete", description="Supprimer un tag")
    @app_commands.default_permissions(manage_messages=True)
    async def tag_delete(self, interaction: discord.Interaction, nom: str):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM tags WHERE guild_id=? AND name=?", (str(interaction.guild.id), nom.lower()))
            await db.commit()
        await interaction.response.send_message(embed=embed_success(f"✅ Tag `{nom}` supprimé."))

    # ───── REMINDER ─────
    remind_group = app_commands.Group(name="reminder", description="Rappels")

    @remind_group.command(name="set", description="Créer un rappel")
    async def remind_set(self, interaction: discord.Interaction, duree: str, message: str):
        secs = parse_duration(duree)
        if secs <= 0:
            return await interaction.response.send_message(embed=embed_error("Durée invalide. Ex: `30m`, `1h`"), ephemeral=True)
        remind_at = int(time.time()) + secs
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO reminders (user_id,channel_id,content,remind_at,created_at) VALUES (?,?,?,?,?)",
                             (str(interaction.user.id), str(interaction.channel.id), message, remind_at, int(time.time())))
            await db.commit()
        embed = embed_success(f"⏰ Rappel créé !\n**Message :** {message}\n**Dans :** {format_duration(secs)} ({dt(remind_at, 'F')})")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @remind_group.command(name="list", description="Voir tes rappels")
    async def remind_list(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM reminders WHERE user_id=? AND sent=0 ORDER BY remind_at ASC", (str(interaction.user.id),))
            rows = await cur.fetchall()
        if not rows:
            return await interaction.response.send_message(embed=embed_info("Aucun rappel actif."), ephemeral=True)
        desc = "\n".join(f"`#{r['id']}` {dt(r['remind_at'], 'R')} — {truncate(r['content'], 80)}" for r in rows)
        embed = discord.Embed(title=f"⏰ Tes rappels ({len(rows)})", description=desc, color=Colors.INFO)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ───── SUGGESTION ─────
    @app_commands.command(name="suggestion", description="Faire une suggestion")
    async def suggestion(self, interaction: discord.Interaction, contenu: str):
        ch_id = os.getenv("CHANNEL_SUGGESTIONS") if hasattr(self, '_env_imported') else None
        import os
        ch_id = os.getenv("CHANNEL_SUGGESTIONS")

        embed = discord.Embed(title="💡 Nouvelle suggestion", description=contenu, color=Colors.PURPLE)
        embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Statut", value="⏳ En attente")
        embed.timestamp = discord.utils.utcnow()

        target_ch = None
        if ch_id:
            target_ch = interaction.guild.get_channel(int(ch_id))

        ch = target_ch or interaction.channel
        msg = await ch.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO suggestions (user_id,guild_id,message_id,content,created_at) VALUES (?,?,?,?,?)",
                             (str(interaction.user.id), str(interaction.guild.id), str(msg.id), contenu, int(time.time())))
            await db.commit()

        await interaction.response.send_message(embed=embed_success("💡 Suggestion envoyée !"), ephemeral=True)


import os

async def setup(bot):
    await bot.add_cog(Utility(bot))
