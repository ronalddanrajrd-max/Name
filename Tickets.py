import discord
from discord import app_commands
from discord.ext import commands
import os
from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *

TICKET_CATEGORIES = {
    "support":      {"label": "Support",             "emoji": "🆘"},
    "achat":        {"label": "Achat / Commande",    "emoji": "💳"},
    "whitelist":    {"label": "Whitelist / HWID",    "emoji": "🔐"},
    "bug":          {"label": "Bug Report",          "emoji": "🐛"},
    "partenariat":  {"label": "Partenariat",         "emoji": "🤝"},
    "litige":       {"label": "Litige / Remboursement","emoji": "⚖️"},
}

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=v["label"], value=k, emoji=v["emoji"])
            for k, v in TICKET_CATEGORIES.items()
        ]
        super().__init__(placeholder="📂 Choisir la catégorie...", options=options, custom_id="ticket_create")

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        cat_info = TICKET_CATEGORIES[category]

        open_tickets = await db_fetchall("SELECT * FROM tickets WHERE user_id=? AND status='open'", (str(interaction.user.id),))
        if len(open_tickets) >= 2:
            return await interaction.response.send_message("❌ Tu as déjà 2 tickets ouverts. Ferme-en un avant d'en créer un nouveau.", ephemeral=True)

        ticket_id = generate_id("TKT")
        guild = interaction.guild
        category_id = os.getenv("CATEGORY_TICKETS")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }
        staff_role_id = os.getenv("ROLE_STAFF")
        if staff_role_id:
            staff_role = guild.get_role(int(staff_role_id))
            if staff_role:
                overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        parent = guild.get_channel(int(category_id)) if category_id else None
        channel = await guild.create_text_channel(
            name=f"{cat_info['emoji']}-{interaction.user.name}".lower().replace(" ", "-"),
            overwrites=overwrites,
            category=parent
        )

        await db_execute("INSERT INTO tickets (ticket_id, user_id, channel_id, category) VALUES (?,?,?,?)",
            (ticket_id, str(interaction.user.id), str(channel.id), category))

        embed = discord.Embed(
            title=f"{cat_info['emoji']} Ticket — {cat_info['label']}",
            description=f"Bienvenue **{interaction.user.name}** !\n\nTon ticket `{ticket_id}` a été créé.\nUn staff va te répondre sous peu.\n\n**Décris ton problème en détail.**",
            color=COLOR_TICKET, timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="📂 Catégorie", value=cat_info["label"], inline=True)
        embed.set_footer(text=f"OkveHUB Support • {ticket_id}")

        view = TicketControls()
        staff_mention = f"<@&{staff_role_id}>" if staff_role_id else ""
        await channel.send(content=f"{interaction.user.mention} {staff_mention}", embed=embed, view=view)
        await interaction.response.send_message(f"✅ Ton ticket a été créé : {channel.mention}", ephemeral=True)

class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer", style=discord.ButtonStyle.danger, custom_id="ticket_close_btn")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = await db_fetchone("SELECT * FROM tickets WHERE channel_id=?", (str(interaction.channel_id),))
        if not ticket: return
        if str(interaction.user.id) != ticket["user_id"] and not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Seul le créateur ou un staff peut fermer ce ticket.", ephemeral=True)
        await db_execute("UPDATE tickets SET status='closed', closed_at=strftime('%s','now') WHERE ticket_id=?", (ticket["ticket_id"],))
        await interaction.response.send_message(embed=success_embed("Ticket Fermé", f"Ticket `{ticket['ticket_id']}` fermé par {interaction.user.mention}.\n*Ce salon sera supprimé dans 5 secondes.*"))
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @discord.ui.button(label="✋ Prendre en charge", style=discord.ButtonStyle.primary, custom_id="ticket_claim_btn")
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_staff(interaction.user):
            return await interaction.response.send_message("❌ Réservé au staff.", ephemeral=True)
        ticket = await db_fetchone("SELECT * FROM tickets WHERE channel_id=?", (str(interaction.channel_id),))
        if not ticket: return
        if ticket["claimed_by"]:
            return await interaction.response.send_message(f"⚠️ Déjà pris par <@{ticket['claimed_by']}>.", ephemeral=True)
        await db_execute("UPDATE tickets SET claimed_by=? WHERE ticket_id=?", (str(interaction.user.id), ticket["ticket_id"]))
        await interaction.response.send_message(embed=success_embed("Ticket Pris", f"{interaction.user.mention} prend en charge ce ticket."))

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticket-setup", description="🎫 Créer le panel de tickets")
    async def ticket_setup(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"): return
        embed = discord.Embed(
            title="🎫 Support OkveHUB",
            description="**Bienvenue sur le support OkveHUB !**\n\nNotre équipe est là pour t'aider avec :\n> 🆘 Support technique\n> 💳 Achats & Commandes\n> 🔐 Whitelist / HWID\n> 🐛 Bug Reports\n> 🤝 Partenariats\n> ⚖️ Litiges\n\n**Clique sur le menu pour ouvrir un ticket.**",
            color=COLOR_TICKET, timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text="OkveHUB — Support 24/7")
        await interaction.channel.send(embed=embed, view=TicketSelectView())
        await interaction.response.send_message("✅ Panel de tickets créé !", ephemeral=True)

    @app_commands.command(name="ticket-close", description="🔒 Fermer le ticket actuel")
    @app_commands.describe(raison="Raison de fermeture")
    async def ticket_close(self, interaction: discord.Interaction, raison: str = "Fermé par l'utilisateur"):
        ticket = await db_fetchone("SELECT * FROM tickets WHERE channel_id=?", (str(interaction.channel_id),))
        if not ticket:
            return await interaction.response.send_message(embed=error_embed("Pas un ticket", "Commande à utiliser dans un ticket."), ephemeral=True)
        if str(interaction.user.id) != ticket["user_id"] and not is_staff(interaction.user):
            return await interaction.response.send_message(embed=error_embed("Permissions", "Seul le créateur ou un staff peut fermer ce ticket."), ephemeral=True)
        await db_execute("UPDATE tickets SET status='closed', closed_at=strftime('%s','now') WHERE ticket_id=?", (ticket["ticket_id"],))
        await interaction.response.send_message(embed=success_embed("Ticket Fermé", f"Fermé par {interaction.user.mention}\n**Raison:** {raison}\n*Suppression dans 5s...*"))
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @app_commands.command(name="ticket-add", description="➕ Ajouter un utilisateur au ticket")
    @app_commands.describe(utilisateur="Utilisateur")
    async def ticket_add(self, interaction: discord.Interaction, utilisateur: discord.Member):
        if not await check_permission(interaction, "staff"): return
        await interaction.channel.set_permissions(utilisateur, view_channel=True, send_messages=True)
        await interaction.response.send_message(embed=success_embed("Ajouté", f"{utilisateur.mention} a été ajouté au ticket."))

    @app_commands.command(name="ticket-remove", description="➖ Retirer un utilisateur du ticket")
    @app_commands.describe(utilisateur="Utilisateur")
    async def ticket_remove(self, interaction: discord.Interaction, utilisateur: discord.Member):
        if not await check_permission(interaction, "staff"): return
        await interaction.channel.set_permissions(utilisateur, view_channel=False)
        await interaction.response.send_message(embed=success_embed("Retiré", f"{utilisateur.mention} a été retiré du ticket."))

    @app_commands.command(name="ticket-claim", description="✋ Prendre en charge ce ticket")
    async def ticket_claim(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "staff"): return
        ticket = await db_fetchone("SELECT * FROM tickets WHERE channel_id=?", (str(interaction.channel_id),))
        if not ticket:
            return await interaction.response.send_message(embed=error_embed("Pas un ticket", "Commande à utiliser dans un ticket."), ephemeral=True)
        if ticket["claimed_by"]:
            return await interaction.response.send_message(embed=warn_embed("Déjà pris", f"Ticket pris par <@{ticket['claimed_by']}>."), ephemeral=True)
        await db_execute("UPDATE tickets SET claimed_by=? WHERE ticket_id=?", (str(interaction.user.id), ticket["ticket_id"]))
        await interaction.response.send_message(embed=success_embed("Pris en charge", f"{interaction.user.mention} prend ce ticket."))

    @app_commands.command(name="ticket-list", description="📋 Voir tous les tickets ouverts")
    async def ticket_list(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "staff"): return
        rows = await db_fetchall("SELECT * FROM tickets WHERE status='open' ORDER BY created_at DESC")
        if not rows:
            return await interaction.response.send_message(embed=info_embed("Aucun ticket", "Aucun ticket ouvert."), ephemeral=True)
        lines = [f"`{r['ticket_id']}` — <@{r['user_id']}> — `{r['category']}` — {'<@' + r['claimed_by'] + '>' if r['claimed_by'] else '⚠️ Non pris'}" for r in rows]
        embed = discord.Embed(title=f"🎫 Tickets Ouverts ({len(rows)})", description="\n".join(lines), color=COLOR_TICKET, timestamp=discord.utils.utcnow())
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Tickets(bot))
