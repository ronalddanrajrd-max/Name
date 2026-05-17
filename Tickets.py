import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import time
import os
from utils.helpers import *
from utils.logger import send_log
from utils.database import DB_PATH

CATEGORIES = {
    "support":  {"label": "🛠️ Support",     "desc": "Aide et support général"},
    "achat":    {"label": "🛒 Achat",        "desc": "Questions sur les achats"},
    "bug":      {"label": "🐛 Bug Report",   "desc": "Signaler un bug de script"},
    "plainte":  {"label": "⚖️ Plainte",      "desc": "Signalement / plainte"},
    "autre":    {"label": "📌 Autre",        "desc": "Autre demande"},
}


class TicketCategorySelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=v["label"], value=k, description=v["desc"])
            for k, v in CATEGORIES.items()
        ]
        super().__init__(placeholder="🎫 Choisir une catégorie...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.values[0])


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketCategorySelect())


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM tickets WHERE channel_id=?", (str(interaction.channel.id),))
            ticket = await cur.fetchone()

        if not ticket:
            return await interaction.response.send_message(embed=embed_error("Ce salon n'est pas un ticket."), ephemeral=True)

        is_owner = str(interaction.user.id) == ticket["user_id"]
        is_staff = interaction.user.guild_permissions.manage_channels

        if not is_owner and not is_staff:
            return await interaction.response.send_message(embed=embed_error("Tu ne peux pas fermer ce ticket."), ephemeral=True)

        await interaction.response.send_message(embed=embed_warning(f"🔒 Ticket fermé par {interaction.user.mention}.\nSuppression dans 5 secondes..."))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE tickets SET status='closed', closed_at=?, closed_by=? WHERE channel_id=?",
                             (int(time.time()), str(interaction.user.id), str(interaction.channel.id)))
            await db.commit()

        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete(reason="Ticket fermé")
        await send_log("TICKET_CLOSE", fields=[
            {"name": "Ticket", "value": interaction.channel.name, "inline": True},
            {"name": "Fermé par", "value": str(interaction.user), "inline": True},
        ])


async def create_ticket(interaction: discord.Interaction, category: str):
    guild = interaction.guild
    user = interaction.user
    cat_info = CATEGORIES.get(category, CATEGORIES["support"])

    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COUNT(*) FROM tickets WHERE user_id=? AND guild_id=? AND status='open'",
            (str(user.id), str(guild.id))
        )
        count = (await cur.fetchone())[0]

    if count >= 2:
        return await interaction.response.send_message(
            embed=embed_error("Tu as déjà **2 tickets ouverts**. Ferme-en un d'abord."), ephemeral=True
        )

    await interaction.response.defer(ephemeral=True)

    # Trouver ou créer catégorie Discord
    ticket_cat = discord.utils.get(guild.categories, name="🎫・Tickets")
    if not ticket_cat:
        ticket_cat = await guild.create_category("🎫・Tickets")

    safe_name = user.name.lower().replace(" ", "-")[:20]
    channel_name = f"{category}-{safe_name}"

    # Permissions
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True, read_message_history=True),
    }
    for role_env in ["ROLE_MODERATEUR", "ROLE_ADMIN", "ROLE_STAFF"]:
        role_id = os.getenv(role_env)
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True, manage_channels=True)

    channel = await guild.create_text_channel(channel_name, category=ticket_cat, overwrites=overwrites)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO tickets (channel_id,user_id,guild_id,category,created_at) VALUES (?,?,?,?,?)",
            (str(channel.id), str(user.id), str(guild.id), category, int(time.time()))
        )
        await db.commit()

    embed = discord.Embed(
        title=f"{cat_info['label']} — Ticket ouvert",
        description=f"Bienvenue {user.mention} !\n\nCatégorie : **{cat_info['label']}**\n\nNotre équipe va te répondre rapidement.\nDécris ton problème en détail avec des screenshots si nécessaire.",
        color=Colors.MAIN
    )
    embed.set_footer(text="OkveHUB Support")
    embed.timestamp = discord.utils.utcnow()

    staff_ping = ""
    for role_env in ["ROLE_STAFF", "ROLE_MODERATEUR"]:
        role_id = os.getenv(role_env)
        if role_id:
            staff_ping = f"<@&{role_id}>"
            break

    await channel.send(content=f"{staff_ping} {user.mention}", embed=embed, view=CloseTicketView())
    await interaction.followup.send(embed=embed_success(f"🎫 Ticket créé : {channel.mention}"), ephemeral=True)

    await send_log("TICKET_OPEN", fields=[
        {"name": "Utilisateur", "value": f"{user} ({user.id})", "inline": True},
        {"name": "Catégorie", "value": cat_info["label"], "inline": True},
        {"name": "Salon", "value": f"<#{channel.id}>", "inline": True},
    ])


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(TicketPanelView())
        bot.add_view(CloseTicketView())

    ticket = app_commands.Group(name="ticket", description="Système de tickets")

    @ticket.command(name="panel", description="Envoyer le panel de tickets")
    @app_commands.default_permissions(administrator=True)
    async def panel(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 Support OkveHUB",
            description="\n".join([
                "**Bienvenue dans le système de tickets OkveHUB !**",
                "",
                "Clique sur le menu ci-dessous pour ouvrir un ticket.",
                "Notre équipe te répondra dans les meilleurs délais.",
                "",
                "**Catégories :**",
                *[f"{v['label']} — {v['desc']}" for v in CATEGORIES.values()],
            ]),
            color=Colors.MAIN
        )
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text="OkveHUB Support • Un ticket par problème SVP")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed, view=TicketPanelView())

    @ticket.command(name="open", description="Ouvrir un ticket")
    @app_commands.describe(categorie="Catégorie du ticket")
    @app_commands.choices(categorie=[app_commands.Choice(name=v["label"], value=k) for k, v in CATEGORIES.items()])
    async def open_ticket(self, interaction: discord.Interaction, categorie: str = "support"):
        await create_ticket(interaction, categorie)

    @ticket.command(name="close", description="Fermer le ticket actuel")
    async def close_ticket(self, interaction: discord.Interaction, raison: str = "Résolu"):
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT * FROM tickets WHERE channel_id=?", (str(interaction.channel.id),))
            ticket = await cur.fetchone()
        if not ticket:
            return await interaction.response.send_message(embed=embed_error("Ce salon n'est pas un ticket."), ephemeral=True)
        is_owner = str(interaction.user.id) == ticket[2]
        is_staff = interaction.user.guild_permissions.manage_channels
        if not is_owner and not is_staff:
            return await interaction.response.send_message(embed=embed_error("Tu ne peux pas fermer ce ticket."), ephemeral=True)
        await interaction.response.send_message(embed=embed_warning(f"🔒 Fermé par {interaction.user.mention}.\n**Raison :** {raison}\nSuppression dans 5s..."))
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE tickets SET status='closed', closed_at=?, closed_by=? WHERE channel_id=?",
                             (int(time.time()), str(interaction.user.id), str(interaction.channel.id)))
            await db.commit()
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()

    @ticket.command(name="add", description="Ajouter un membre au ticket")
    async def add_member(self, interaction: discord.Interaction, membre: discord.Member):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        await interaction.channel.set_permissions(membre, view_channel=True, send_messages=True)
        await interaction.response.send_message(embed=embed_success(f"{membre.mention} ajouté au ticket."))

    @ticket.command(name="remove", description="Retirer un membre du ticket")
    async def remove_member(self, interaction: discord.Interaction, membre: discord.Member):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        await interaction.channel.set_permissions(membre, view_channel=False)
        await interaction.response.send_message(embed=embed_success(f"{membre.mention} retiré du ticket."))

    @ticket.command(name="list", description="Voir les tickets ouverts")
    @app_commands.default_permissions(moderate_members=True)
    async def list_tickets(self, interaction: discord.Interaction):
        if not is_staff(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM tickets WHERE guild_id=? AND status='open'", (str(interaction.guild.id),))
            rows = await cur.fetchall()
        desc = "\n".join(f"<#{r['channel_id']}> — <@{r['user_id']}> — `{r['category']}`" for r in rows) or "*Aucun ticket ouvert.*"
        embed = discord.Embed(title=f"🎫 Tickets ouverts ({len(rows)})", description=desc, color=Colors.MAIN)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Tickets(bot))
