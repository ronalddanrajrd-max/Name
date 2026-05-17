import discord
from discord import app_commands
from discord.ext import commands
import time
import os
from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *

class Whitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ══════════ /wl-add ══════════
    @app_commands.command(name="wl-add", description="➕ Ajouter un utilisateur à la whitelist OkveHUB")
    @app_commands.describe(utilisateur="Utilisateur à whitelister", raison="Raison", scripts="Scripts accessibles (ex: all)", duree="Durée (ex: 30d, permanent)", hwid="HWID de la machine")
    async def wl_add(self, interaction: discord.Interaction, utilisateur: discord.Member, raison: str, scripts: str = "all", duree: str = "permanent", hwid: str = None):
        if not await check_permission(interaction, "staff"): return

        bl = await db_fetchone("SELECT user_id FROM blacklist WHERE user_id=?", (str(utilisateur.id),))
        if bl:
            return await interaction.response.send_message(embed=error_embed("Utilisateur blacklisté", f"**{utilisateur}** est blacklisté. Retirez-le d'abord avec `/bl-remove`."), ephemeral=True)

        expires_at = None
        if duree and duree != "permanent":
            secs = parse_duration(duree)
            if not secs:
                return await interaction.response.send_message(embed=error_embed("Durée invalide", "Format: `30d`, `1w`, `6h`, `permanent`"), ephemeral=True)
            expires_at = now_ts() + secs

        await db_execute("""
            INSERT INTO whitelist (user_id, username, added_by, reason, hwid, script_access, expires_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username, added_by=excluded.added_by,
                reason=excluded.reason, hwid=excluded.hwid,
                script_access=excluded.script_access, expires_at=excluded.expires_at
        """, (str(utilisateur.id), str(utilisateur), str(interaction.user.id), raison, hwid, scripts, expires_at))

        role_id = os.getenv("ROLE_WHITELIST")
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            if role: await utilisateur.add_roles(role)

        embed = discord.Embed(title="🔐 Whitelist Ajoutée", color=COLOR_WL, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=utilisateur.display_avatar.url)
        embed.add_field(name="👤 Utilisateur", value=f"{utilisateur.mention} `{utilisateur}`", inline=True)
        embed.add_field(name="🛡️ Ajouté par", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Raison", value=raison, inline=False)
        embed.add_field(name="📜 Scripts", value=scripts, inline=True)
        embed.add_field(name="⏰ Expiration", value=f"<t:{expires_at}:F>" if expires_at else "∞ Permanent", inline=True)
        embed.add_field(name="🔑 HWID", value=f"`{hwid}`" if hwid else "Non défini", inline=False)

        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, "CHANNEL_LOGS_WHITELIST", embed)

    # ══════════ /wl-remove ══════════
    @app_commands.command(name="wl-remove", description="➖ Retirer de la whitelist")
    @app_commands.describe(utilisateur="Utilisateur", raison="Raison")
    async def wl_remove(self, interaction: discord.Interaction, utilisateur: discord.Member, raison: str = "Aucune raison"):
        if not await check_permission(interaction, "staff"): return

        entry = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(utilisateur.id),))
        if not entry:
            return await interaction.response.send_message(embed=error_embed("Non whitelisté", f"**{utilisateur}** n'est pas dans la whitelist."), ephemeral=True)

        await db_execute("DELETE FROM whitelist WHERE user_id=?", (str(utilisateur.id),))

        role_id = os.getenv("ROLE_WHITELIST")
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            if role: await utilisateur.remove_roles(role)

        embed = success_embed("Whitelist Retirée", f"**{utilisateur}** retiré de la whitelist.\n**Raison:** {raison}")
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, "CHANNEL_LOGS_WHITELIST", embed)

    # ══════════ /wl-check ══════════
    @app_commands.command(name="wl-check", description="🔍 Vérifier la whitelist d'un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur (laisse vide pour toi)")
    async def wl_check(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user
        entry = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(target.id),))

        if not entry:
            return await interaction.response.send_message(embed=error_embed("Non whitelisté", f"**{target}** n'est pas dans la whitelist OkveHUB."), ephemeral=True)

        expired = entry["expires_at"] and entry["expires_at"] < now_ts()
        embed = discord.Embed(
            title="🔐 Whitelist Expirée" if expired else "🔐 Whitelist Active",
            color=COLOR_ERROR if expired else COLOR_WL,
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="👤 Utilisateur", value=f"{target.mention} `{target}`", inline=True)
        embed.add_field(name="📊 Statut", value="❌ Expirée" if expired else "✅ Active", inline=True)
        embed.add_field(name="📜 Scripts", value=entry["script_access"] or "Tous", inline=True)
        embed.add_field(name="🔑 HWID", value=f"`{entry['hwid']}`" if entry["hwid"] else "Non défini", inline=False)
        embed.add_field(name="📅 Ajouté le", value=f"<t:{entry['created_at']}:F>", inline=True)
        embed.add_field(name="⏰ Expire", value=f"<t:{entry['expires_at']}:F>" if entry["expires_at"] else "∞ Permanent", inline=True)
        embed.add_field(name="🛡️ Par", value=f"<@{entry['added_by']}>", inline=True)
        embed.add_field(name="📝 Raison", value=entry["reason"] or "N/A", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ══════════ /wl-list ══════════
    @app_commands.command(name="wl-list", description="📋 Lister tous les whitelistés")
    async def wl_list(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "staff"): return

        rows = await db_fetchall("SELECT * FROM whitelist ORDER BY created_at DESC")
        if not rows:
            return await interaction.response.send_message(embed=info_embed("Whitelist vide", "Aucun utilisateur whitelisté."), ephemeral=True)

        lines = []
        for i, r in enumerate(rows[:20], 1):
            expired = r["expires_at"] and r["expires_at"] < now_ts()
            lines.append(f"`{i}.` <@{r['user_id']}> — {'❌' if expired else '✅'} — {r['script_access']}")

        embed = discord.Embed(title=f"🔐 Whitelist OkveHUB ({len(rows)} membres)", description="\n".join(lines), color=COLOR_WL, timestamp=discord.utils.utcnow())
        if len(rows) > 20: embed.set_footer(text=f"Affichage des 20 premiers sur {len(rows)}")
        await interaction.response.send_message(embed=embed)

    # ══════════ /wl-hwid ══════════
    @app_commands.command(name="wl-hwid", description="🔑 Modifier le HWID d'un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur", hwid="Nouveau HWID")
    async def wl_hwid(self, interaction: discord.Interaction, utilisateur: discord.Member, hwid: str = None):
        if not await check_permission(interaction, "staff"): return

        entry = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(utilisateur.id),))
        if not entry:
            return await interaction.response.send_message(embed=error_embed("Non whitelisté", f"**{utilisateur}** n'est pas dans la whitelist."), ephemeral=True)

        await db_execute("UPDATE whitelist SET hwid=? WHERE user_id=?", (hwid, str(utilisateur.id)))
        embed = success_embed("HWID Mis à jour", f"HWID de **{utilisateur}** {'modifié' if hwid else 'supprimé'}.\n**HWID:** `{hwid or 'Supprimé'}`")
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, "CHANNEL_LOGS_WHITELIST", embed)

    # ══════════ /wl-stats ══════════
    @app_commands.command(name="wl-stats", description="📊 Stats whitelist")
    async def wl_stats(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "staff"): return

        rows = await db_fetchall("SELECT * FROM whitelist")
        n = now_ts()
        active = [r for r in rows if not r["expires_at"] or r["expires_at"] > n]
        expired = [r for r in rows if r["expires_at"] and r["expires_at"] <= n]
        permanent = [r for r in rows if not r["expires_at"]]

        embed = discord.Embed(title="📊 Stats Whitelist OkveHUB", color=COLOR_WL, timestamp=discord.utils.utcnow())
        embed.add_field(name="👥 Total", value=f"`{len(rows)}`", inline=True)
        embed.add_field(name="✅ Actives", value=f"`{len(active)}`", inline=True)
        embed.add_field(name="❌ Expirées", value=f"`{len(expired)}`", inline=True)
        embed.add_field(name="♾️ Permanentes", value=f"`{len(permanent)}`", inline=True)
        await interaction.response.send_message(embed=embed)

    # ══════════ /bl-add ══════════
    @app_commands.command(name="bl-add", description="🚫 Ajouter à la blacklist OkveHUB")
    @app_commands.describe(utilisateur="Utilisateur", raison="Raison")
    async def bl_add(self, interaction: discord.Interaction, utilisateur: discord.Member, raison: str):
        if not await check_permission(interaction, "admin"): return

        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(utilisateur.id),))
        if wl:
            await db_execute("DELETE FROM whitelist WHERE user_id=?", (str(utilisateur.id),))
            role_id = os.getenv("ROLE_WHITELIST")
            if role_id:
                role = interaction.guild.get_role(int(role_id))
                if role: await utilisateur.remove_roles(role)

        await db_execute("INSERT INTO blacklist (user_id, username, reason, added_by) VALUES (?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET reason=excluded.reason",
            (str(utilisateur.id), str(utilisateur), raison, str(interaction.user.id)))

        embed = discord.Embed(title="🚫 Blacklist Ajoutée", color=COLOR_ERROR, timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Utilisateur", value=f"{utilisateur.mention}", inline=True)
        embed.add_field(name="📝 Raison", value=raison, inline=False)
        embed.add_field(name="🛡️ Par", value=interaction.user.mention, inline=True)
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, "CHANNEL_LOGS_WHITELIST", embed)

    # ══════════ /bl-remove ══════════
    @app_commands.command(name="bl-remove", description="✅ Retirer de la blacklist")
    @app_commands.describe(utilisateur="Utilisateur")
    async def bl_remove(self, interaction: discord.Interaction, utilisateur: discord.Member):
        if not await check_permission(interaction, "admin"): return
        bl = await db_fetchone("SELECT * FROM blacklist WHERE user_id=?", (str(utilisateur.id),))
        if not bl:
            return await interaction.response.send_message(embed=error_embed("Pas blacklisté", f"**{utilisateur}** n'est pas blacklisté."), ephemeral=True)
        await db_execute("DELETE FROM blacklist WHERE user_id=?", (str(utilisateur.id),))
        await interaction.response.send_message(embed=success_embed("Retiré de la blacklist", f"**{utilisateur}** n'est plus blacklisté."))

    # ══════════ /bl-check ══════════
    @app_commands.command(name="bl-check", description="🔍 Vérifier si quelqu'un est blacklisté")
    @app_commands.describe(utilisateur="Utilisateur")
    async def bl_check(self, interaction: discord.Interaction, utilisateur: discord.Member):
        entry = await db_fetchone("SELECT * FROM blacklist WHERE user_id=?", (str(utilisateur.id),))
        if not entry:
            return await interaction.response.send_message(embed=success_embed("Non blacklisté", f"**{utilisateur}** n'est pas dans la blacklist."), ephemeral=True)
        embed = discord.Embed(title="🚫 Utilisateur Blacklisté", color=COLOR_ERROR, timestamp=discord.utils.utcnow())
        embed.add_field(name="👤 Utilisateur", value=utilisateur.mention, inline=True)
        embed.add_field(name="📝 Raison", value=entry["reason"], inline=False)
        embed.add_field(name="🛡️ Par", value=f"<@{entry['added_by']}>", inline=True)
        embed.add_field(name="📅 Depuis", value=f"<t:{entry['created_at']}:F>", inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Whitelist(bot))
