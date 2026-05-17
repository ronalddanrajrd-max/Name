import discord
from discord import app_commands
from discord.ext import commands
import json, os, random
from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ══════════ /annonce ══════════
    @app_commands.command(name="annonce", description="📢 Faire une annonce officielle")
    @app_commands.describe(titre="Titre", message="Contenu", mention="Qui mentionner", couleur="Couleur hex (ex: ff0000)")
    @app_commands.choices(mention=[
        app_commands.Choice(name="@everyone", value="@everyone"),
        app_commands.Choice(name="@here", value="@here"),
        app_commands.Choice(name="Aucun", value="none"),
    ])
    async def annonce(self, interaction: discord.Interaction, titre: str, message: str, mention: str = "none", couleur: str = None):
        if not await check_permission(interaction, "admin"): return
        color = int(couleur.replace("#",""), 16) if couleur else COLOR_MAIN
        embed = discord.Embed(title=f"📢 {titre}", description=message, color=color, timestamp=discord.utils.utcnow())
        embed.set_author(name="OkveHUB — Annonce Officielle", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text=f"Annonce par {interaction.user}")
        ch_id = os.getenv("CHANNEL_ANNONCES")
        channel = self.bot.get_channel(int(ch_id)) if ch_id else interaction.channel
        content = mention if mention != "none" else None
        await channel.send(content=content, embed=embed)
        await interaction.response.send_message(embed=success_embed("Annonce Envoyée", f"Publiée dans {channel.mention}."), ephemeral=True)

    # ══════════ /update ══════════
    @app_commands.command(name="update", description="🔄 Annoncer une mise à jour de script")
    @app_commands.describe(script="Nom du script", version="Version (ex: v2.1.0)", nouveautes="Nouveautés (séparées par |)", corrections="Bug fixes (séparés par |)")
    async def update(self, interaction: discord.Interaction, script: str, version: str, nouveautes: str, corrections: str = None):
        if not await check_permission(interaction, "admin"): return
        embed = discord.Embed(title=f"🔄 Update — {script} {version}", color=0x00b0f4, timestamp=discord.utils.utcnow())
        embed.set_author(name="OkveHUB — Mise à jour", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.add_field(name="✨ Nouveautés", value="\n".join(f"> ✨ {n.strip()}" for n in nouveautes.split("|")), inline=False)
        if corrections:
            embed.add_field(name="🐛 Corrections", value="\n".join(f"> 🐛 {c.strip()}" for c in corrections.split("|")), inline=False)
        embed.set_footer(text=f"OkveHUB Scripts")
        ch_id = os.getenv("CHANNEL_UPDATES")
        channel = self.bot.get_channel(int(ch_id)) if ch_id else interaction.channel
        await channel.send(content="@everyone", embed=embed)
        await interaction.response.send_message(embed=success_embed("Update Annoncée", f"Mise à jour de **{script}** publiée !"), ephemeral=True)

    # ══════════ /promo ══════════
    @app_commands.command(name="promo", description="🏷️ Annoncer une promotion")
    @app_commands.describe(script="Script en promo", reduction="Réduction en %", prix_original="Prix original", duree="Durée (ex: 24h)")
    async def promo(self, interaction: discord.Interaction, script: str, reduction: int, prix_original: float, duree: str = "Durée limitée"):
        if not await check_permission(interaction, "admin"): return
        prix_promo = prix_original * (1 - reduction / 100)
        embed = discord.Embed(
            title=f"🏷️ PROMO — {script}",
            description=f"**Profite de {reduction}% de réduction sur {script} !**\n\n~~{prix_original}€~~ → **{prix_promo:.2f}€**\n\n⏰ Valable : **{duree}**\n\n💬 Ouvre un ticket pour en profiter !",
            color=COLOR_GOLD, timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text="OkveHUB — Offre limitée !")
        ch_id = os.getenv("CHANNEL_ANNONCES")
        channel = self.bot.get_channel(int(ch_id)) if ch_id else interaction.channel
        await channel.send(content="@everyone 🎉 PROMOTION !", embed=embed)
        await interaction.response.send_message(embed=success_embed("Promo Annoncée", f"Promo **{script}** publiée !"), ephemeral=True)

    # ══════════ /embed ══════════
    @app_commands.command(name="embed", description="📋 Créer un embed personnalisé")
    @app_commands.describe(titre="Titre", description="Description", couleur="Couleur hex", footer="Footer text")
    async def embed_cmd(self, interaction: discord.Interaction, titre: str, description: str, couleur: str = None, footer: str = None):
        if not await check_permission(interaction, "admin"): return
        color = int(couleur.replace("#",""), 16) if couleur else COLOR_MAIN
        embed = discord.Embed(title=titre, description=description.replace("\\n", "\n"), color=color, timestamp=discord.utils.utcnow())
        if footer: embed.set_footer(text=footer)
        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Embed envoyé !", ephemeral=True)

    # ══════════ /dm ══════════
    @app_commands.command(name="dm", description="📨 Envoyer un DM à un utilisateur")
    @app_commands.describe(utilisateur="Destinataire", message="Message")
    async def dm(self, interaction: discord.Interaction, utilisateur: discord.Member, message: str):
        if not await check_permission(interaction, "admin"): return
        embed = discord.Embed(title="📨 Message de OkveHUB", description=message, color=COLOR_MAIN, timestamp=discord.utils.utcnow())
        embed.set_footer(text="OkveHUB — Message Officiel")
        try:
            await utilisateur.send(embed=embed)
            await interaction.response.send_message(embed=success_embed("DM Envoyé", f"Message envoyé à **{utilisateur}**."), ephemeral=True)
        except:
            await interaction.response.send_message(embed=error_embed("Erreur", f"Impossible d'envoyer un DM à **{utilisateur}** (DMs fermés)."), ephemeral=True)

    # ══════════ /giveaway-start ══════════
    @app_commands.command(name="giveaway-start", description="🎉 Lancer un giveaway")
    @app_commands.describe(prix="Lot à gagner", duree="Durée (ex: 1h, 24h, 7d)", gagnants="Nombre de gagnants")
    async def giveaway_start(self, interaction: discord.Interaction, prix: str, duree: str, gagnants: int = 1):
        if not await check_permission(interaction, "admin"): return
        seconds = parse_duration(duree)
        if not seconds:
            return await interaction.response.send_message(embed=error_embed("Durée invalide", "Format: `1h`, `24h`, `7d`"), ephemeral=True)
        ends_at = now_ts() + seconds
        embed = discord.Embed(title=f"🎉 GIVEAWAY — {prix}", color=COLOR_GOLD, timestamp=discord.utils.utcnow())
        embed.description = f"**Clique sur 🎉 pour participer !**\n\n🏆 **Lot:** {prix}\n👥 **Gagnants:** {gagnants}\n⏰ **Fin:** <t:{ends_at}:F> (<t:{ends_at}:R>)\n🎫 **Organisé par:** {interaction.user.mention}"
        embed.set_footer(text="0 participant(s)")

        view = GiveawayView()
        msg = await interaction.channel.send(embed=embed, view=view)
        await db_execute("INSERT INTO giveaways (message_id, channel_id, prize, winners_count, host_id, ends_at) VALUES (?,?,?,?,?,?)",
            (str(msg.id), str(interaction.channel_id), prix, gagnants, str(interaction.user.id), ends_at))
        await interaction.response.send_message(embed=success_embed("Giveaway Lancé !", f"**{prix}** — Fin: <t:{ends_at}:F>"), ephemeral=True)

    # ══════════ /giveaway-end ══════════
    @app_commands.command(name="giveaway-end", description="🏆 Terminer un giveaway")
    @app_commands.describe(message_id="ID du message du giveaway")
    async def giveaway_end(self, interaction: discord.Interaction, message_id: str):
        if not await check_permission(interaction, "admin"): return
        gw = await db_fetchone("SELECT * FROM giveaways WHERE message_id=?", (message_id,))
        if not gw:
            return await interaction.response.send_message(embed=error_embed("Introuvable", "Giveaway non trouvé."), ephemeral=True)
        if gw["ended"]:
            return await interaction.response.send_message(embed=error_embed("Terminé", "Ce giveaway est déjà terminé."), ephemeral=True)
        participants = json.loads(gw["participants"] or "[]")
        if not participants:
            await interaction.response.send_message(embed=warn_embed("Aucun participant", "Personne n'a participé."))
        else:
            winners = random.sample(participants, min(gw["winners_count"], len(participants)))
            winners_text = " ".join(f"<@{w}>" for w in winners)
            win_embed = discord.Embed(title="🏆 Fin du Giveaway !", description=f"**Lot:** {gw['prize']}\n\n🎊 Félicitations {winners_text} !\n\n👥 **{len(participants)}** participant(s).", color=COLOR_GOLD, timestamp=discord.utils.utcnow())
            channel = self.bot.get_channel(int(gw["channel_id"]))
            if channel: await channel.send(content=f"🎉 Félicitations {winners_text} !", embed=win_embed)
            await interaction.response.send_message(embed=success_embed("Giveaway Terminé", f"Gagnant(s): {winners_text}"))
        await db_execute("UPDATE giveaways SET ended=1 WHERE message_id=?", (message_id,))

    # ══════════ /role-add ══════════
    @app_commands.command(name="role-add", description="🎭 Donner un rôle à un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur", role="Rôle", raison="Raison")
    async def role_add(self, interaction: discord.Interaction, utilisateur: discord.Member, role: discord.Role, raison: str = "Aucune raison"):
        if not await check_permission(interaction, "moderator"): return
        await utilisateur.add_roles(role, reason=raison)
        await interaction.response.send_message(embed=success_embed("Rôle Ajouté", f"{role.mention} donné à {utilisateur.mention}."))

    # ══════════ /role-remove ══════════
    @app_commands.command(name="role-remove", description="🎭 Retirer un rôle à un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur", role="Rôle", raison="Raison")
    async def role_remove(self, interaction: discord.Interaction, utilisateur: discord.Member, role: discord.Role, raison: str = "Aucune raison"):
        if not await check_permission(interaction, "moderator"): return
        await utilisateur.remove_roles(role, reason=raison)
        await interaction.response.send_message(embed=success_embed("Rôle Retiré", f"{role.mention} retiré de {utilisateur.mention}."))

    # ══════════ /serverinfo ══════════
    @app_commands.command(name="serverinfo", description="📊 Informations sur le serveur")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        wl_count = len(await db_fetchall("SELECT * FROM whitelist"))
        tk_count = len(await db_fetchall("SELECT * FROM tickets WHERE status='open'"))
        ventes_count = len(await db_fetchall("SELECT * FROM ventes WHERE status='completed'"))
        embed = discord.Embed(title=f"📊 {guild.name}", color=COLOR_MAIN, timestamp=discord.utils.utcnow())
        if guild.icon: embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="👑 Propriétaire", value=f"<@{guild.owner_id}>", inline=True)
        embed.add_field(name="📅 Créé le", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=True)
        embed.add_field(name="🆔 ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="👥 Membres", value=f"Total: `{guild.member_count}`", inline=True)
        embed.add_field(name="💬 Salons", value=f"`{len(guild.channels)}`", inline=True)
        embed.add_field(name="🎭 Rôles", value=f"`{len(guild.roles)}`", inline=True)
        embed.add_field(name="🔐 Whitelistés", value=f"`{wl_count}`", inline=True)
        embed.add_field(name="🎫 Tickets ouverts", value=f"`{tk_count}`", inline=True)
        embed.add_field(name="💳 Ventes", value=f"`{ventes_count}`", inline=True)
        await interaction.response.send_message(embed=embed)

    # ══════════ /stats ══════════
    @app_commands.command(name="stats", description="📈 Statistiques globales du bot")
    async def stats(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "staff"): return
        import psutil, time
        wl = await db_fetchall("SELECT * FROM whitelist")
        bl = await db_fetchall("SELECT * FROM blacklist")
        tk = await db_fetchall("SELECT * FROM tickets WHERE status='open'")
        ventes_rows = await db_fetchall("SELECT * FROM ventes WHERE status='completed'")
        revenue = sum(r["price"] for r in ventes_rows)
        uptime_s = int(time.time() - self.bot.start_time)
        embed = discord.Embed(title="📈 Statistiques OkveHUB Bot", color=COLOR_MAIN, timestamp=discord.utils.utcnow())
        embed.add_field(name="🔐 Whitelist", value=f"`{len(wl)}` actifs", inline=True)
        embed.add_field(name="🚫 Blacklist", value=f"`{len(bl)}`", inline=True)
        embed.add_field(name="🎫 Tickets ouverts", value=f"`{len(tk)}`", inline=True)
        embed.add_field(name="💳 Ventes", value=f"`{len(ventes_rows)}` — `{revenue:.2f}€`", inline=True)
        embed.add_field(name="⏱️ Uptime", value=format_duration(uptime_s), inline=True)
        embed.add_field(name="📡 Ping", value=f"`{round(self.bot.latency * 1000)}ms`", inline=True)
        await interaction.response.send_message(embed=embed)

    # ══════════ /ping ══════════
    @app_commands.command(name="ping", description="🏓 Latence du bot")
    async def ping(self, interaction: discord.Interaction):
        lat = round(self.bot.latency * 1000)
        color = COLOR_SUCCESS if lat < 100 else COLOR_WARNING if lat < 300 else COLOR_ERROR
        embed = discord.Embed(title="🏓 Pong !", color=color, timestamp=discord.utils.utcnow())
        embed.add_field(name="💓 Heartbeat", value=f"`{lat}ms`", inline=True)
        await interaction.response.send_message(embed=embed)

    # ══════════ /avatar ══════════
    @app_commands.command(name="avatar", description="🖼️ Voir l'avatar d'un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur")
    async def avatar(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user
        embed = discord.Embed(title=f"🖼️ Avatar — {target}", color=COLOR_MAIN, timestamp=discord.utils.utcnow())
        embed.set_image(url=target.display_avatar.url)
        embed.add_field(name="🔗 Lien", value=f"[Clique ici]({target.display_avatar.url})", inline=True)
        await interaction.response.send_message(embed=embed)

class GiveawayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎉 Participer", style=discord.ButtonStyle.success, custom_id="giveaway_join")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        gw = await db_fetchone("SELECT * FROM giveaways WHERE message_id=?", (str(interaction.message.id),))
        if not gw or gw["ended"]:
            return await interaction.response.send_message("❌ Ce giveaway est terminé.", ephemeral=True)
        participants = json.loads(gw["participants"] or "[]")
        if str(interaction.user.id) in participants:
            return await interaction.response.send_message("⚠️ Tu participes déjà à ce giveaway.", ephemeral=True)
        participants.append(str(interaction.user.id))
        await db_execute("UPDATE giveaways SET participants=? WHERE message_id=?", (json.dumps(participants), str(interaction.message.id)))
        # Update embed footer
        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"{len(participants)} participant(s)")
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(f"✅ Tu participes au giveaway **{gw['prize']}** !", ephemeral=True)

    @discord.ui.button(label="❌ Quitter", style=discord.ButtonStyle.danger, custom_id="giveaway_leave")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        gw = await db_fetchone("SELECT * FROM giveaways WHERE message_id=?", (str(interaction.message.id),))
        if not gw: return
        participants = json.loads(gw["participants"] or "[]")
        if str(interaction.user.id) not in participants:
            return await interaction.response.send_message("❌ Tu ne participes pas à ce giveaway.", ephemeral=True)
        participants.remove(str(interaction.user.id))
        await db_execute("UPDATE giveaways SET participants=? WHERE message_id=?", (json.dumps(participants), str(interaction.message.id)))
        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"{len(participants)} participant(s)")
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message("✅ Tu as quitté le giveaway.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))
