import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import time
import json
import os
from utils.helpers import *
from utils.logger import send_log
from utils.database import DB_PATH


class Whitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    wl = app_commands.Group(name="whitelist", description="Gestion de la whitelist OkveHUB")

    # ───── ADD ─────
    @wl.command(name="add", description="Ajouter un membre à la whitelist")
    @app_commands.describe(
        membre="Membre à whitelister",
        script="Nom du script acheté",
        raison="Raison de l'ajout",
        duree="Durée (ex: 30d, 6m) — vide = permanent"
    )
    async def wl_add(self, interaction: discord.Interaction,
                     membre: discord.Member,
                     script: str = "Global",
                     raison: str = "Achat de script",
                     duree: str = None):

        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Tu dois être **Modérateur** pour faire ça."), ephemeral=True)

        expires_at = None
        duree_display = "Permanent"
        if duree:
            secs = parse_duration(duree)
            if secs <= 0:
                return await interaction.response.send_message(embed=embed_error("Durée invalide. Ex: `30d`, `6m`, `1y`"), ephemeral=True)
            expires_at = int(time.time()) + secs
            duree_display = format_duration(secs)

        async with aiosqlite.connect(DB_PATH) as db:
            row = await db.execute("SELECT user_id FROM whitelist WHERE user_id = ?", (str(membre.id),))
            if await row.fetchone():
                return await interaction.response.send_message(embed=embed_warning(f"{membre.mention} est **déjà** dans la whitelist."), ephemeral=True)

            await db.execute(
                "INSERT INTO whitelist VALUES (?,?,?,?,?,?)",
                (str(membre.id), str(interaction.user.id), int(time.time()), raison, script, expires_at)
            )
            await db.commit()

        # Donner les rôles
        for role_env in ["ROLE_WHITELIST", "ROLE_ACHETEUR"]:
            role_id = os.getenv(role_env)
            if role_id:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    await membre.add_roles(role, reason="Whitelist ajout")

        embed = discord.Embed(title="✅ Whitelist — Accès accordé", color=Colors.SUCCESS)
        embed.set_thumbnail(url=membre.display_avatar.url)
        embed.add_field(name="👤 Membre", value=f"{membre.mention} (`{membre.id}`)", inline=True)
        embed.add_field(name="🛒 Script", value=script, inline=True)
        embed.add_field(name="👮 Ajouté par", value=interaction.user.mention, inline=True)
        embed.add_field(name="⏰ Expire", value=dt(expires_at) if expires_at else "**Jamais**", inline=True)
        embed.add_field(name="📝 Raison", value=raison, inline=False)
        embed.timestamp = discord.utils.utcnow()

        await interaction.response.send_message(embed=embed)

        # DM au membre
        try:
            dm_embed = discord.Embed(
                title="🎉 Whitelist OkveHUB — Accès accordé !",
                description=f"Tu as été ajouté à la whitelist de **OkveHUB** !\n\n**Script :** {script}\n**Expire :** {dt(expires_at) if expires_at else 'Jamais'}",
                color=Colors.SUCCESS
            )
            dm_embed.set_footer(text="Merci pour ton achat !")
            await membre.send(embed=dm_embed)
        except Exception:
            pass

        await send_log("WHITELIST_ADD", fields=[
            {"name": "Membre", "value": f"{membre} ({membre.id})", "inline": True},
            {"name": "Script", "value": script, "inline": True},
            {"name": "Staff", "value": str(interaction.user), "inline": True},
            {"name": "Expire", "value": dt(expires_at) if expires_at else "Permanent", "inline": True},
        ])

    # ───── REMOVE ─────
    @wl.command(name="remove", description="Retirer un membre de la whitelist")
    @app_commands.describe(membre="Membre à retirer", raison="Raison")
    async def wl_remove(self, interaction: discord.Interaction,
                        membre: discord.Member,
                        raison: str = "Aucune raison"):

        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            row = await db.execute("SELECT user_id FROM whitelist WHERE user_id = ?", (str(membre.id),))
            if not await row.fetchone():
                return await interaction.response.send_message(embed=embed_error(f"{membre.mention} n'est pas dans la whitelist."), ephemeral=True)
            await db.execute("DELETE FROM whitelist WHERE user_id = ?", (str(membre.id),))
            await db.commit()

        # Retirer les rôles
        for role_env in ["ROLE_WHITELIST", "ROLE_ACHETEUR"]:
            role_id = os.getenv(role_env)
            if role_id:
                role = interaction.guild.get_role(int(role_id))
                if role and role in membre.roles:
                    await membre.remove_roles(role, reason="Whitelist retrait")

        await interaction.response.send_message(embed=embed_success(f"{membre.mention} retiré de la whitelist.\n**Raison :** {raison}"))

        try:
            dm = discord.Embed(title="❌ Whitelist OkveHUB — Accès retiré",
                               description=f"Ton accès whitelist a été retiré.\n**Raison :** {raison}",
                               color=Colors.ERROR)
            await membre.send(embed=dm)
        except Exception:
            pass

        await send_log("WHITELIST_REMOVE", fields=[
            {"name": "Membre", "value": f"{membre} ({membre.id})", "inline": True},
            {"name": "Staff", "value": str(interaction.user), "inline": True},
            {"name": "Raison", "value": raison, "inline": False},
        ])

    # ───── CHECK ─────
    @wl.command(name="check", description="Vérifier si un membre est whitelisté")
    @app_commands.describe(membre="Membre à vérifier")
    async def wl_check(self, interaction: discord.Interaction, membre: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM whitelist WHERE user_id = ?", (str(membre.id),))
            row = await cur.fetchone()

        if not row:
            embed = discord.Embed(title="❌ Non whitelisté",
                                  description=f"{membre.mention} n'est **pas** dans la whitelist OkveHUB.",
                                  color=Colors.ERROR)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        now = int(time.time())
        expired = row["expires_at"] and row["expires_at"] < now
        color = Colors.ERROR if expired else Colors.SUCCESS

        embed = discord.Embed(title="⚠️ Whitelist expirée" if expired else "✅ Whitelisté", color=color)
        embed.set_thumbnail(url=membre.display_avatar.url)
        embed.add_field(name="👤 Membre", value=str(membre), inline=True)
        embed.add_field(name="🛒 Script", value=row["script"], inline=True)
        embed.add_field(name="👮 Ajouté par", value=f"<@{row['added_by']}>", inline=True)
        embed.add_field(name="📅 Ajouté le", value=dt(row["added_at"], "D"), inline=True)
        embed.add_field(name="⏰ Expire", value=dt(row["expires_at"]) if row["expires_at"] else "**Jamais**", inline=True)
        embed.add_field(name="📝 Raison", value=row["reason"], inline=False)
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)

    # ───── LIST ─────
    @wl.command(name="list", description="Voir tous les membres whitelistés")
    @app_commands.describe(page="Numéro de page")
    async def wl_list(self, interaction: discord.Interaction, page: int = 1):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM whitelist ORDER BY added_at DESC")
            all_rows = await cur.fetchall()

        per_page = 10
        pages = max(1, -(-len(all_rows) // per_page))
        page = max(1, min(page, pages))
        items = paginate(all_rows, per_page, page - 1)

        now = int(time.time())
        if not items:
            desc = "*Aucun membre whitelisté.*"
        else:
            desc = "\n".join(
                f"`{(page-1)*per_page + i + 1}.` <@{r['user_id']}> — **{r['script']}** "
                f"{'⚠️ *Expiré*' if r['expires_at'] and r['expires_at'] < now else '✅'}"
                for i, r in enumerate(items)
            )

        embed = discord.Embed(title=f"📋 Whitelist OkveHUB ({len(all_rows)} membres)", description=desc, color=Colors.MAIN)
        embed.set_footer(text=f"Page {page}/{pages}")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)

    # ───── SEARCH ─────
    @wl.command(name="search", description="Chercher un membre dans la whitelist par nom ou ID")
    @app_commands.describe(query="Nom d'utilisateur ou ID")
    async def wl_search(self, interaction: discord.Interaction, query: str):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM whitelist")
            all_rows = await cur.fetchall()

        matches = []
        for r in all_rows:
            member = interaction.guild.get_member(int(r["user_id"]))
            name = str(member) if member else r["user_id"]
            if query.lower() in name.lower() or query == r["user_id"]:
                matches.append((r, member, name))

        if not matches:
            return await interaction.response.send_message(embed=embed_error(f"Aucun résultat pour `{query}`."), ephemeral=True)

        desc = "\n".join(f"<@{r['user_id']}> — **{r['script']}**" for r, _, _ in matches[:10])
        embed = discord.Embed(title=f"🔍 Résultats ({len(matches)})", description=desc, color=Colors.INFO)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Whitelist(bot))
