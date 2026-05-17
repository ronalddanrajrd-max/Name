import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
import os
from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ══════════ /ban ══════════
    @app_commands.command(name="ban", description="🔨 Bannir un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur", raison="Raison", messages="Jours de messages à supprimer (0-7)")
    async def ban(self, interaction: discord.Interaction, utilisateur: discord.Member, raison: str, messages: int = 0):
        if not await check_permission(interaction, "moderator"): return
        if not utilisateur.banneable:
            return await interaction.response.send_message(embed=error_embed("Impossible", "Je ne peux pas bannir cet utilisateur."), ephemeral=True)
        try:
            await utilisateur.send(embed=discord.Embed(title=f"🔨 Tu as été banni de {interaction.guild.name}", description=f"**Raison:** {raison}", color=COLOR_ERROR))
        except: pass
        await utilisateur.ban(reason=f"{raison} | Par: {interaction.user}", delete_message_days=messages)
        embed = discord.Embed(title="🔨 BAN", color=COLOR_ERROR, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=utilisateur.display_avatar.url)
        embed.add_field(name="👤 Utilisateur", value=f"{utilisateur.mention} `{utilisateur}`", inline=True)
        embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Raison", value=raison, inline=False)
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, "CHANNEL_LOGS_MOD", embed)

    # ══════════ /unban ══════════
    @app_commands.command(name="unban", description="✅ Débannir un utilisateur")
    @app_commands.describe(userid="ID de l'utilisateur", raison="Raison")
    async def unban(self, interaction: discord.Interaction, userid: str, raison: str = "Aucune raison"):
        if not await check_permission(interaction, "moderator"): return
        try:
            user = await self.bot.fetch_user(int(userid))
            await interaction.guild.unban(user, reason=raison)
            await interaction.response.send_message(embed=success_embed("Débanni", f"**{user}** a été débanni.\n**Raison:** {raison}"))
        except discord.NotFound:
            await interaction.response.send_message(embed=error_embed("Introuvable", f"Utilisateur `{userid}` non trouvé ou non banni."), ephemeral=True)

    # ══════════ /kick ══════════
    @app_commands.command(name="kick", description="👟 Expulser un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur", raison="Raison")
    async def kick(self, interaction: discord.Interaction, utilisateur: discord.Member, raison: str):
        if not await check_permission(interaction, "moderator"): return
        try:
            await utilisateur.send(embed=discord.Embed(title=f"👟 Tu as été expulsé de {interaction.guild.name}", description=f"**Raison:** {raison}", color=COLOR_WARNING))
        except: pass
        await utilisateur.kick(reason=f"{raison} | Par: {interaction.user}")
        embed = discord.Embed(title="👟 KICK", color=COLOR_WARNING, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=utilisateur.display_avatar.url)
        embed.add_field(name="👤 Utilisateur", value=f"{utilisateur.mention}", inline=True)
        embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Raison", value=raison, inline=False)
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, "CHANNEL_LOGS_MOD", embed)

    # ══════════ /mute ══════════
    @app_commands.command(name="mute", description="🔇 Mettre en timeout un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur", duree="Durée (ex: 10m, 1h, 7d)", raison="Raison")
    async def mute(self, interaction: discord.Interaction, utilisateur: discord.Member, duree: str, raison: str = "Aucune raison"):
        if not await check_permission(interaction, "moderator"): return
        seconds = parse_duration(duree)
        if not seconds:
            return await interaction.response.send_message(embed=error_embed("Durée invalide", "Format: `10m`, `1h`, `7d`"), ephemeral=True)
        if seconds > 2419200:
            return await interaction.response.send_message(embed=error_embed("Trop long", "Maximum 28 jours."), ephemeral=True)
        await utilisateur.timeout(timedelta(seconds=seconds), reason=raison)
        embed = discord.Embed(title="🔇 MUTE (Timeout)", color=COLOR_WARNING, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=utilisateur.display_avatar.url)
        embed.add_field(name="👤 Utilisateur", value=utilisateur.mention, inline=True)
        embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="⏱️ Durée", value=format_duration(seconds), inline=True)
        embed.add_field(name="📝 Raison", value=raison, inline=False)
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, "CHANNEL_LOGS_MOD", embed)

    # ══════════ /unmute ══════════
    @app_commands.command(name="unmute", description="🔊 Retirer le timeout d'un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur", raison="Raison")
    async def unmute(self, interaction: discord.Interaction, utilisateur: discord.Member, raison: str = "Aucune raison"):
        if not await check_permission(interaction, "moderator"): return
        if not utilisateur.is_timed_out():
            return await interaction.response.send_message(embed=error_embed("Pas mute", "Cet utilisateur n'est pas en timeout."), ephemeral=True)
        await utilisateur.timeout(None, reason=raison)
        await interaction.response.send_message(embed=success_embed("Unmute", f"**{utilisateur}** n'est plus en timeout."))

    # ══════════ /warn ══════════
    @app_commands.command(name="warn", description="⚠️ Avertir un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur", raison="Raison")
    async def warn(self, interaction: discord.Interaction, utilisateur: discord.Member, raison: str):
        if not await check_permission(interaction, "moderator"): return
        await db_execute("INSERT INTO warns (user_id, guild_id, moderator_id, reason) VALUES (?,?,?,?)",
            (str(utilisateur.id), str(interaction.guild_id), str(interaction.user.id), raison))
        rows = await db_fetchall("SELECT * FROM warns WHERE user_id=? AND guild_id=?", (str(utilisateur.id), str(interaction.guild_id)))
        count = len(rows)
        embed = discord.Embed(title="⚠️ Avertissement", color=COLOR_GOLD, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=utilisateur.display_avatar.url)
        embed.add_field(name="👤 Utilisateur", value=utilisateur.mention, inline=True)
        embed.add_field(name="🛡️ Modérateur", value=interaction.user.mention, inline=True)
        embed.add_field(name="📝 Raison", value=raison, inline=False)
        embed.add_field(name="📊 Total warns", value=f"`{count}`", inline=True)
        if count == 3: embed.add_field(name="🤖 Suggestion", value="⚠️ 3 warns — Envisager un mute", inline=False)
        if count >= 5: embed.add_field(name="🤖 Suggestion", value="🔨 5+ warns — Envisager un ban", inline=False)
        try:
            await utilisateur.send(embed=discord.Embed(title=f"⚠️ Avertissement sur {interaction.guild.name}", description=f"**Raison:** {raison}\n**Total warns:** {count}", color=COLOR_GOLD))
        except: pass
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, "CHANNEL_LOGS_MOD", embed)

    # ══════════ /warns ══════════
    @app_commands.command(name="warns", description="📋 Voir les avertissements d'un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur")
    async def warns_cmd(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user
        if target.id != interaction.user.id and not is_staff(interaction.user): return
        rows = await db_fetchall("SELECT * FROM warns WHERE user_id=? AND guild_id=? ORDER BY created_at DESC", (str(target.id), str(interaction.guild_id)))
        if not rows:
            return await interaction.response.send_message(embed=success_embed("Aucun warn", f"**{target}** n'a aucun avertissement."), ephemeral=True)
        lines = [f"**#{r['id']}** <t:{r['created_at']}:d> — {r['reason']} — par <@{r['moderator_id']}>" for r in rows]
        embed = discord.Embed(title=f"⚠️ Warns de {target}", description="\n".join(lines), color=COLOR_GOLD, timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"{len(rows)} avertissement(s)")
        await interaction.response.send_message(embed=embed, ephemeral=(target.id == interaction.user.id))

    # ══════════ /unwarn ══════════
    @app_commands.command(name="unwarn", description="🗑️ Supprimer un avertissement")
    @app_commands.describe(id="ID du warn")
    async def unwarn(self, interaction: discord.Interaction, id: int):
        if not await check_permission(interaction, "moderator"): return
        await db_execute("DELETE FROM warns WHERE id=?", (id,))
        await interaction.response.send_message(embed=success_embed("Warn supprimé", f"Le warn `#{id}` a été supprimé."))

    # ══════════ /clearwarns ══════════
    @app_commands.command(name="clearwarns", description="🧹 Effacer tous les warns d'un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur")
    async def clearwarns(self, interaction: discord.Interaction, utilisateur: discord.Member):
        if not await check_permission(interaction, "admin"): return
        await db_execute("DELETE FROM warns WHERE user_id=? AND guild_id=?", (str(utilisateur.id), str(interaction.guild_id)))
        await interaction.response.send_message(embed=success_embed("Warns effacés", f"Tous les warns de **{utilisateur}** supprimés."))

    # ══════════ /purge ══════════
    @app_commands.command(name="purge", description="🧹 Supprimer des messages en masse")
    @app_commands.describe(nombre="Nombre de messages (1-100)", utilisateur="Seulement cet utilisateur")
    async def purge(self, interaction: discord.Interaction, nombre: int, utilisateur: discord.Member = None):
        if not await check_permission(interaction, "moderator"): return
        if nombre < 1 or nombre > 100:
            return await interaction.response.send_message(embed=error_embed("Nombre invalide", "Entre 1 et 100."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        check = (lambda m: m.author.id == utilisateur.id) if utilisateur else None
        deleted = await interaction.channel.purge(limit=nombre, check=check, bulk=True)
        await interaction.followup.send(content=f"✅ **{len(deleted)}** message(s) supprimé(s).", ephemeral=True)
        await send_log(self.bot, "CHANNEL_LOGS_MOD", info_embed("🧹 Purge", f"**{len(deleted)}** messages supprimés dans {interaction.channel.mention} par {interaction.user.mention}"))

    # ══════════ /slowmode ══════════
    @app_commands.command(name="slowmode", description="🐌 Configurer le slowmode")
    @app_commands.describe(secondes="Délai (0 = désactivé)", raison="Raison")
    async def slowmode(self, interaction: discord.Interaction, secondes: int, raison: str = "Aucune raison"):
        if not await check_permission(interaction, "moderator"): return
        await interaction.channel.edit(slowmode_delay=secondes, reason=raison)
        msg = f"Slowmode {'désactivé' if secondes == 0 else f'défini à **{secondes}s**'} dans ce salon."
        await interaction.response.send_message(embed=success_embed("Slowmode", msg))

    # ══════════ /lock ══════════
    @app_commands.command(name="lock", description="🔒 Verrouiller un salon")
    @app_commands.describe(raison="Raison")
    async def lock(self, interaction: discord.Interaction, raison: str = "Aucune raison"):
        if not await check_permission(interaction, "moderator"): return
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(embed=success_embed("🔒 Salon Verrouillé", f"**Raison:** {raison}"))

    # ══════════ /unlock ══════════
    @app_commands.command(name="unlock", description="🔓 Déverrouiller un salon")
    async def unlock(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "moderator"): return
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=None)
        await interaction.response.send_message(embed=success_embed("🔓 Salon Déverrouillé", "Les membres peuvent à nouveau écrire."))

    # ══════════ /userinfo ══════════
    @app_commands.command(name="userinfo", description="👤 Informations sur un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur")
    async def userinfo(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user
        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(target.id),))
        bl = await db_fetchone("SELECT * FROM blacklist WHERE user_id=?", (str(target.id),))
        w_rows = await db_fetchall("SELECT * FROM warns WHERE user_id=? AND guild_id=?", (str(target.id), str(interaction.guild_id)))

        embed = discord.Embed(title=f"👤 {target}", color=target.color, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🆔 ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="📅 Créé le", value=f"<t:{int(target.created_at.timestamp())}:F>", inline=True)
        embed.add_field(name="📥 Rejoint le", value=f"<t:{int(target.joined_at.timestamp())}:F>", inline=True)
        embed.add_field(name="⚠️ Warns", value=f"`{len(w_rows)}`", inline=True)
        wl_status = ("✅ Active" if wl and (not wl["expires_at"] or wl["expires_at"] > now_ts()) else "⏰ Expirée") if wl else "❌ Non"
        embed.add_field(name="🔐 Whitelist", value=wl_status, inline=True)
        embed.add_field(name="🚫 Blacklist", value="⛔ Oui" if bl else "✅ Non", inline=True)
        roles = [r.mention for r in target.roles if r != interaction.guild.default_role][-10:]
        if roles: embed.add_field(name=f"🎭 Rôles", value=" ".join(roles), inline=False)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
