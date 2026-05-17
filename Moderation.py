import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import time
import os
from utils.helpers import *
from utils.logger import send_mod_log
from utils.database import DB_PATH


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ───────────────────────── BAN ─────────────────────────
    @app_commands.command(name="ban", description="Bannir un membre du serveur")
    @app_commands.describe(
        membre="Membre à bannir",
        raison="Raison du ban",
        duree="Durée (ex: 7d, permanent si vide)",
        supprimer_messages="Supprimer les messages des X derniers jours (0-7)"
    )
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction,
                  membre: discord.Member,
                  raison: str = "Aucune raison fournie",
                  duree: str = None,
                  supprimer_messages: app_commands.Range[int, 0, 7] = 0):

        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        if membre.id == interaction.user.id:
            return await interaction.response.send_message(embed=embed_error("Tu ne peux pas te bannir toi-même."), ephemeral=True)
        if not membre.is_bannable():
            return await interaction.response.send_message(embed=embed_error("Je ne peux pas bannir ce membre."), ephemeral=True)

        expires_at = None
        duree_display = "Permanent"
        if duree:
            secs = parse_duration(duree)
            if secs > 0:
                expires_at = int(time.time()) + secs
                duree_display = format_duration(secs)

        # DM avant ban
        try:
            dm = discord.Embed(title=f"🔨 Banni de {interaction.guild.name}",
                               color=Colors.ERROR)
            dm.add_field(name="Raison", value=raison)
            dm.add_field(name="Durée", value=duree_display)
            await membre.send(embed=dm)
        except Exception:
            pass

        await membre.ban(reason=f"{interaction.user}: {raison}",
                         delete_message_days=supprimer_messages)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO infractions (user_id,guild_id,type,reason,moderator_id,created_at,expires_at) VALUES (?,?,?,?,?,?,?)",
                (str(membre.id), str(interaction.guild.id), "BAN", raison,
                 str(interaction.user.id), int(time.time()), expires_at)
            )
            await db.commit()

        embed = embed_success(f"**{membre}** a été banni.\n**Durée :** {duree_display}\n**Raison :** {raison}")
        await interaction.response.send_message(embed=embed)
        await send_mod_log("BAN", fields=[
            {"name": "Membre", "value": f"{membre} ({membre.id})", "inline": True},
            {"name": "Modérateur", "value": str(interaction.user), "inline": True},
            {"name": "Durée", "value": duree_display, "inline": True},
            {"name": "Raison", "value": raison},
        ])

    # ───────────────────────── UNBAN ─────────────────────────
    @app_commands.command(name="unban", description="Débannir un utilisateur")
    @app_commands.describe(user_id="ID de l'utilisateur", raison="Raison")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str, raison: str = "Aucune raison"):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        try:
            user = await self.bot.fetch_user(int(user_id))
            await interaction.guild.unban(user, reason=raison)
            await interaction.response.send_message(embed=embed_success(f"✅ **{user}** débanni."))
            await send_mod_log("UNBAN", fields=[
                {"name": "Utilisateur", "value": f"{user} ({user.id})", "inline": True},
                {"name": "Modérateur", "value": str(interaction.user), "inline": True},
                {"name": "Raison", "value": raison},
            ])
        except Exception:
            await interaction.response.send_message(embed=embed_error("Utilisateur introuvable dans les bans."), ephemeral=True)

    # ───────────────────────── KICK ─────────────────────────
    @app_commands.command(name="kick", description="Expulser un membre")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction,
                   membre: discord.Member,
                   raison: str = "Aucune raison"):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        if not membre.is_bannable():
            return await interaction.response.send_message(embed=embed_error("Je ne peux pas expulser ce membre."), ephemeral=True)
        try:
            dm = discord.Embed(title=f"👢 Expulsé de {interaction.guild.name}", color=Colors.ERROR)
            dm.add_field(name="Raison", value=raison)
            await membre.send(embed=dm)
        except Exception:
            pass
        await membre.kick(reason=f"{interaction.user}: {raison}")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO infractions (user_id,guild_id,type,reason,moderator_id,created_at) VALUES (?,?,?,?,?,?)",
                (str(membre.id), str(interaction.guild.id), "KICK", raison, str(interaction.user.id), int(time.time()))
            )
            await db.commit()
        await interaction.response.send_message(embed=embed_success(f"**{membre}** expulsé.\n**Raison :** {raison}"))
        await send_mod_log("KICK", fields=[
            {"name": "Membre", "value": f"{membre} ({membre.id})", "inline": True},
            {"name": "Modérateur", "value": str(interaction.user), "inline": True},
            {"name": "Raison", "value": raison},
        ])

    # ───────────────────────── MUTE ─────────────────────────
    @app_commands.command(name="mute", description="Mute un membre (timeout Discord)")
    @app_commands.describe(membre="Membre", duree="Durée (ex: 10m, 1h, 7d)", raison="Raison")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction,
                   membre: discord.Member,
                   duree: str = "10m",
                   raison: str = "Aucune raison"):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        secs = parse_duration(duree)
        if secs <= 0 or secs > 2419200:
            return await interaction.response.send_message(embed=embed_error("Durée invalide. Max: 28 jours."), ephemeral=True)

        import datetime
        until = discord.utils.utcnow() + datetime.timedelta(seconds=secs)
        await membre.timeout(until, reason=f"{interaction.user}: {raison}")

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO infractions (user_id,guild_id,type,reason,moderator_id,created_at,expires_at) VALUES (?,?,?,?,?,?,?)",
                (str(membre.id), str(interaction.guild.id), "MUTE", raison,
                 str(interaction.user.id), int(time.time()), int(time.time()) + secs)
            )
            await db.commit()

        dur_str = format_duration(secs)
        try:
            dm = discord.Embed(title=f"🔇 Muté sur {interaction.guild.name}", color=Colors.WARNING)
            dm.add_field(name="Durée", value=dur_str, inline=True)
            dm.add_field(name="Raison", value=raison)
            await membre.send(embed=dm)
        except Exception:
            pass

        await interaction.response.send_message(embed=embed_success(f"🔇 **{membre}** muté **{dur_str}**.\n**Raison :** {raison}"))
        await send_mod_log("MUTE", fields=[
            {"name": "Membre", "value": f"{membre} ({membre.id})", "inline": True},
            {"name": "Modérateur", "value": str(interaction.user), "inline": True},
            {"name": "Durée", "value": dur_str, "inline": True},
            {"name": "Raison", "value": raison},
        ])

    # ───────────────────────── UNMUTE ─────────────────────────
    @app_commands.command(name="unmute", description="Retirer le mute d'un membre")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, membre: discord.Member, raison: str = "Aucune raison"):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        await membre.timeout(None, reason=raison)
        await interaction.response.send_message(embed=embed_success(f"🔊 **{membre}** démuté."))
        await send_mod_log("UNMUTE", fields=[
            {"name": "Membre", "value": f"{membre} ({membre.id})", "inline": True},
            {"name": "Modérateur", "value": str(interaction.user), "inline": True},
        ])

    # ───────────────────────── WARN ─────────────────────────
    @app_commands.command(name="warn", description="Avertir un membre")
    @app_commands.default_permissions(moderate_members=True)
    async def warn(self, interaction: discord.Interaction, membre: discord.Member, raison: str):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO infractions (user_id,guild_id,type,reason,moderator_id,created_at) VALUES (?,?,?,?,?,?)",
                (str(membre.id), str(interaction.guild.id), "WARN", raison, str(interaction.user.id), int(time.time()))
            )
            await db.commit()
            cur = await db.execute(
                "SELECT COUNT(*) FROM infractions WHERE user_id=? AND guild_id=? AND type='WARN'",
                (str(membre.id), str(interaction.guild.id))
            )
            total = (await cur.fetchone())[0]

        # Auto-sanctions
        sanction = ""
        if total >= 5 and membre.is_bannable():
            await membre.ban(reason="Auto-ban: 5 warns")
            sanction = "\n🔨 **Auto-ban** (5 warns atteints)"
        elif total >= 3:
            import datetime
            await membre.timeout(discord.utils.utcnow() + datetime.timedelta(hours=24), reason="Auto-mute: 3 warns")
            sanction = "\n🔇 **Auto-mute 24h** (3 warns atteints)"
        elif total >= 2 and membre.is_bannable():
            await membre.kick(reason="Auto-kick: 2 warns")
            sanction = "\n👢 **Auto-kick** (2 warns atteints)"

        try:
            dm = discord.Embed(title=f"⚠️ Avertissement — {interaction.guild.name}", color=Colors.WARNING)
            dm.add_field(name="Raison", value=raison)
            dm.add_field(name="Total warns", value=f"{total}/5")
            await membre.send(embed=dm)
        except Exception:
            pass

        embed = discord.Embed(title="⚠️ Avertissement enregistré", color=Colors.WARNING)
        embed.add_field(name="👤 Membre", value=f"{membre.mention} (`{membre.id}`)", inline=True)
        embed.add_field(name="⚠️ Warns", value=f"**{total}**/5", inline=True)
        embed.add_field(name="📝 Raison", value=raison, inline=False)
        if sanction:
            embed.add_field(name="🛡️ Sanction automatique", value=sanction)
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)
        await send_mod_log("WARN", fields=[
            {"name": "Membre", "value": f"{membre} ({membre.id})", "inline": True},
            {"name": "Modérateur", "value": str(interaction.user), "inline": True},
            {"name": "Warns", "value": f"{total}/5", "inline": True},
            {"name": "Raison", "value": raison},
        ])

    # ───────────────────────── INFRACTIONS ─────────────────────────
    @app_commands.command(name="infractions", description="Voir l'historique d'un membre")
    @app_commands.default_permissions(moderate_members=True)
    async def infractions(self, interaction: discord.Interaction, membre: discord.Member):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        icons = {"BAN": "🔨", "KICK": "👢", "MUTE": "🔇", "WARN": "⚠️", "UNBAN": "✅", "UNMUTE": "🔊"}
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM infractions WHERE user_id=? AND guild_id=? ORDER BY created_at DESC LIMIT 15",
                (str(membre.id), str(interaction.guild.id))
            )
            rows = await cur.fetchall()

        if not rows:
            return await interaction.response.send_message(embed=embed_info(f"Aucune infraction pour **{membre}**."), ephemeral=True)

        desc = "\n\n".join(
            f"`#{r['id']}` {icons.get(r['type'], '📋')} **{r['type']}** — {dt(r['created_at'], 'D')}\n> {r['reason']} *(par <@{r['moderator_id']}>)*"
            for r in rows
        )
        embed = discord.Embed(title=f"📋 Infractions — {membre}", description=desc, color=Colors.WARNING)
        embed.set_thumbnail(url=membre.display_avatar.url)
        embed.add_field(name="Total", value=f"**{len(rows)}** infraction(s)")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)

    # ───────────────────────── CLEARWARN ─────────────────────────
    @app_commands.command(name="clearwarn", description="Supprimer une infraction par ID")
    @app_commands.default_permissions(moderate_members=True)
    async def clearwarn(self, interaction: discord.Interaction, id: int):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM infractions WHERE id=?", (id,))
            await db.commit()
        await interaction.response.send_message(embed=embed_success(f"Infraction `#{id}` supprimée."))

    # ───────────────────────── PURGE ─────────────────────────
    @app_commands.command(name="purge", description="Supprimer des messages en masse")
    @app_commands.describe(nombre="Nombre de messages (1-100)", membre="Filtrer par membre")
    @app_commands.default_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction,
                    nombre: app_commands.Range[int, 1, 100],
                    membre: discord.Member = None):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        check = (lambda m: m.author.id == membre.id) if membre else None
        deleted = await interaction.channel.purge(limit=nombre, check=check, bulk=True)

        await interaction.followup.send(embed=embed_success(f"🧹 **{len(deleted)}** message(s) supprimé(s)."), ephemeral=True)
        await send_mod_log("PURGE", fields=[
            {"name": "Salon", "value": f"<#{interaction.channel_id}>", "inline": True},
            {"name": "Supprimés", "value": str(len(deleted)), "inline": True},
            {"name": "Par", "value": str(interaction.user), "inline": True},
        ])

    # ───────────────────────── LOCK / UNLOCK ─────────────────────────
    @app_commands.command(name="lock", description="Verrouiller un salon")
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction,
                   salon: discord.TextChannel = None,
                   raison: str = "Maintenance"):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        channel = salon or interaction.channel
        await channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(embed=embed_success(f"🔒 **{channel.name}** verrouillé.\n**Raison :** {raison}"))
        await channel.send(embed=embed_warning(f"🔒 Salon verrouillé.\n**Raison :** {raison}"))

    @app_commands.command(name="unlock", description="Déverrouiller un salon")
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction, salon: discord.TextChannel = None):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        channel = salon or interaction.channel
        await channel.set_permissions(interaction.guild.default_role, send_messages=None)
        await interaction.response.send_message(embed=embed_success(f"🔓 **{channel.name}** déverrouillé."))
        await channel.send(embed=embed_success("🔓 Salon déverrouillé !"))

    # ───────────────────────── SLOWMODE ─────────────────────────
    @app_commands.command(name="slowmode", description="Définir le slowmode d'un salon")
    @app_commands.default_permissions(manage_channels=True)
    async def slowmode(self, interaction: discord.Interaction,
                       secondes: app_commands.Range[int, 0, 21600]):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        await interaction.channel.edit(slowmode_delay=secondes)
        msg = "🐢 Slowmode **désactivé**." if secondes == 0 else f"🐢 Slowmode défini à **{secondes}s**."
        await interaction.response.send_message(embed=embed_success(msg))

    # ───────────────────────── NICKNAME ─────────────────────────
    @app_commands.command(name="nickname", description="Changer le pseudo d'un membre")
    @app_commands.default_permissions(manage_nicknames=True)
    async def nickname(self, interaction: discord.Interaction,
                       membre: discord.Member,
                       pseudo: str = None):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        await membre.edit(nick=pseudo)
        msg = f"✏️ Pseudo de **{membre}** changé en **{pseudo}**." if pseudo else f"✏️ Pseudo de **{membre}** réinitialisé."
        await interaction.response.send_message(embed=embed_success(msg))

    # ───────────────────────── USERINFO ─────────────────────────
    @app_commands.command(name="userinfo", description="Infos détaillées sur un membre")
    async def userinfo(self, interaction: discord.Interaction, membre: discord.Member = None):
        m = membre or interaction.user
        roles = [r.mention for r in reversed(m.roles) if r.id != interaction.guild.id]

        embed = discord.Embed(title=f"👤 {m}", color=m.color or Colors.MAIN)
        embed.set_thumbnail(url=m.display_avatar.url)
        embed.add_field(name="🆔 ID", value=f"`{m.id}`", inline=True)
        embed.add_field(name="📅 Compte créé", value=dt(m.created_at), inline=True)
        embed.add_field(name="📥 A rejoint", value=dt(m.joined_at) if m.joined_at else "?", inline=True)
        embed.add_field(name="🎨 Rôle principal", value=m.top_role.mention, inline=True)
        embed.add_field(name="🤖 Bot", value="Oui" if m.bot else "Non", inline=True)
        embed.add_field(name="💬 Statut", value=str(m.status).capitalize(), inline=True)
        embed.add_field(name=f"🎭 Rôles ({len(roles)})", value=" ".join(roles[:15]) if roles else "Aucun", inline=False)
        embed.set_footer(text=f"OkveHUB • {interaction.guild.name}")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)

    # ───────────────────────── SERVERINFO ─────────────────────────
    @app_commands.command(name="serverinfo", description="Informations sur le serveur")
    async def serverinfo(self, interaction: discord.Interaction):
        g = interaction.guild
        bots = sum(1 for m in g.members if m.bot)
        humans = g.member_count - bots

        embed = discord.Embed(title=f"🏠 {g.name}", color=Colors.MAIN)
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="👑 Propriétaire", value=g.owner.mention if g.owner else "?", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{g.id}`", inline=True)
        embed.add_field(name="📅 Créé le", value=dt(g.created_at, "D"), inline=True)
        embed.add_field(name="👥 Membres", value=f"**{g.member_count}** (👤 {humans} / 🤖 {bots})", inline=True)
        embed.add_field(name="💬 Salons", value=f"💬 {len(g.text_channels)} | 🔊 {len(g.voice_channels)} | 📁 {len(g.categories)}", inline=True)
        embed.add_field(name="🚀 Boosts", value=f"**{g.premium_subscription_count}** (Niveau {g.premium_tier})", inline=True)
        embed.add_field(name="🎭 Rôles", value=str(len(g.roles)), inline=True)
        embed.add_field(name="😀 Emojis", value=str(len(g.emojis)), inline=True)
        embed.add_field(name="🔒 Vérification", value=str(g.verification_level).capitalize(), inline=True)
        embed.set_footer(text="OkveHUB")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)

    # ───────────────────────── ROLEINFO ─────────────────────────
    @app_commands.command(name="roleinfo", description="Infos sur un rôle")
    async def roleinfo(self, interaction: discord.Interaction, role: discord.Role):
        embed = discord.Embed(title=f"🎨 {role.name}", color=role.color)
        embed.add_field(name="🆔 ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="👥 Membres", value=str(len(role.members)), inline=True)
        embed.add_field(name="📅 Créé", value=dt(role.created_at, "D"), inline=True)
        embed.add_field(name="🎨 Couleur", value=str(role.color), inline=True)
        embed.add_field(name="📌 Mentionnable", value="Oui" if role.mentionable else "Non", inline=True)
        embed.add_field(name="🏷️ Affiché séparément", value="Oui" if role.hoist else "Non", inline=True)
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)

    # ───────────────────────── NOTE ─────────────────────────
    @app_commands.command(name="note", description="Ajouter/voir des notes staff sur un membre")
    @app_commands.default_permissions(moderate_members=True)
    async def note(self, interaction: discord.Interaction, membre: discord.Member, contenu: str = None):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            if contenu:
                await db.execute(
                    "INSERT INTO staff_notes (user_id,guild_id,author_id,content,created_at) VALUES (?,?,?,?,?)",
                    (str(membre.id), str(interaction.guild.id), str(interaction.user.id), contenu, int(time.time()))
                )
                await db.commit()
                await interaction.response.send_message(embed=embed_success(f"📝 Note ajoutée pour **{membre}**."), ephemeral=True)
            else:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT * FROM staff_notes WHERE user_id=? AND guild_id=? ORDER BY created_at DESC",
                    (str(membre.id), str(interaction.guild.id))
                )
                rows = await cur.fetchall()
                if not rows:
                    return await interaction.response.send_message(embed=embed_info(f"Aucune note pour **{membre}**."), ephemeral=True)
                desc = "\n\n".join(f"{dt(r['created_at'], 'D')} — <@{r['author_id']}>\n> {r['content']}" for r in rows)
                embed = discord.Embed(title=f"📝 Notes — {membre}", description=desc, color=Colors.INFO)
                await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
