import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import secrets

from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *


TICKET_CATEGORIES = {
    "support": {"label": "Support", "emoji": "🆘"},
    "achat": {"label": "Achat / Commande", "emoji": "💳"},
    "whitelist": {"label": "Whitelist / HWID", "emoji": "🔐"},
    "bug": {"label": "Bug Report", "emoji": "🐛"},
    "partenariat": {"label": "Partenariat", "emoji": "🤝"},
    "litige": {"label": "Litige / Remboursement", "emoji": "⚖️"},
}


def create_ticket_id():
    return "TKT-" + secrets.token_hex(4).upper()


class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label=data["label"],
                value=key,
                emoji=data["emoji"]
            )
            for key, data in TICKET_CATEGORIES.items()
        ]

        super().__init__(
            placeholder="📂 Choisir la catégorie...",
            options=options,
            custom_id="okvehub_ticket_select"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            category = self.values[0]
            cat_info = TICKET_CATEGORIES[category]

            open_tickets = await db_fetchall(
                "SELECT * FROM tickets WHERE user_id=? AND status='open'",
                (str(interaction.user.id),)
            )

            if len(open_tickets) >= 2:
                return await interaction.response.send_message(
                    "❌ Tu as déjà 2 tickets ouverts.",
                    ephemeral=True
                )

            ticket_id = create_ticket_id()
            guild = interaction.guild

            if not guild:
                return await interaction.response.send_message(
                    "❌ Erreur : serveur introuvable.",
                    ephemeral=True
                )

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True
                )
            }

            staff_role_id = os.getenv("ROLE_STAFF")
            if staff_role_id:
                staff_role = guild.get_role(int(staff_role_id))
                if staff_role:
                    overwrites[staff_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True
                    )

            parent = None
            category_id = os.getenv("CATEGORY_TICKETS")

            if category_id:
                parent = guild.get_channel(int(category_id))

            channel = await guild.create_text_channel(
                name=f"{cat_info['emoji']}-ticket-{interaction.user.name}".lower(),
                overwrites=overwrites,
                category=parent,
                reason=f"Ticket créé par {interaction.user}"
            )

            await db_execute(
                "INSERT INTO tickets (ticket_id, user_id, channel_id, category) VALUES (?, ?, ?, ?)",
                (
                    ticket_id,
                    str(interaction.user.id),
                    str(channel.id),
                    category
                )
            )

            embed = discord.Embed(
                title=f"{cat_info['emoji']} Ticket — {cat_info['label']}",
                description=(
                    f"Bienvenue {interaction.user.mention} !\n\n"
                    f"Ton ticket `{ticket_id}` a été créé.\n"
                    f"Un membre du staff va te répondre.\n\n"
                    f"Décris ton problème clairement."
                ),
                color=COLOR_TICKET,
                timestamp=discord.utils.utcnow()
            )

            embed.set_footer(text=f"OkveHUB Support • {ticket_id}")

            staff_mention = f"<@&{staff_role_id}>" if staff_role_id else ""

            await channel.send(
                content=f"{interaction.user.mention} {staff_mention}",
                embed=embed,
                view=TicketControls()
            )

            await interaction.response.send_message(
                f"✅ Ton ticket a été créé : {channel.mention}",
                ephemeral=True
            )

        except Exception as e:
            try:
                await interaction.response.send_message(
                    f"❌ Erreur ticket : `{e}`",
                    ephemeral=True
                )
            except:
                pass


class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


class TicketControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔒 Fermer",
        style=discord.ButtonStyle.danger,
        custom_id="okvehub_ticket_close"
    )
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            ticket = await db_fetchone(
                "SELECT * FROM tickets WHERE channel_id=?",
                (str(interaction.channel_id),)
            )

            if not ticket:
                return await interaction.response.send_message(
                    "❌ Ticket introuvable.",
                    ephemeral=True
                )

            if str(interaction.user.id) != ticket["user_id"] and not is_staff(interaction.user):
                return await interaction.response.send_message(
                    "❌ Seul le créateur ou le staff peut fermer ce ticket.",
                    ephemeral=True
                )

            await db_execute(
                "UPDATE tickets SET status='closed', closed_at=strftime('%s','now') WHERE ticket_id=?",
                (ticket["ticket_id"],)
            )

            await interaction.response.send_message(
                embed=success_embed(
                    "Ticket fermé",
                    f"Ticket `{ticket['ticket_id']}` fermé par {interaction.user.mention}.\n"
                    "Ce salon sera supprimé dans 5 secondes."
                )
            )

            await asyncio.sleep(5)
            await interaction.channel.delete()

        except Exception as e:
            try:
                await interaction.response.send_message(
                    f"❌ Erreur fermeture ticket : `{e}`",
                    ephemeral=True
                )
            except:
                pass

    @discord.ui.button(
        label="✋ Prendre en charge",
        style=discord.ButtonStyle.primary,
        custom_id="okvehub_ticket_claim"
    )
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not is_staff(interaction.user):
                return await interaction.response.send_message(
                    "❌ Réservé au staff.",
                    ephemeral=True
                )

            ticket = await db_fetchone(
                "SELECT * FROM tickets WHERE channel_id=?",
                (str(interaction.channel_id),)
            )

            if not ticket:
                return await interaction.response.send_message(
                    "❌ Ticket introuvable.",
                    ephemeral=True
                )

            if ticket["claimed_by"]:
                return await interaction.response.send_message(
                    f"⚠️ Déjà pris par <@{ticket['claimed_by']}>.",
                    ephemeral=True
                )

            await db_execute(
                "UPDATE tickets SET claimed_by=? WHERE ticket_id=?",
                (
                    str(interaction.user.id),
                    ticket["ticket_id"]
                )
            )

            await interaction.response.send_message(
                embed=success_embed(
                    "Ticket pris",
                    f"{interaction.user.mention} prend en charge ce ticket."
                )
            )

        except Exception as e:
            try:
                await interaction.response.send_message(
                    f"❌ Erreur prise en charge : `{e}`",
                    ephemeral=True
                )
            except:
                pass


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticket-setup", description="Créer le panel de tickets")
    async def ticket_setup(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title="🎫 Support OkveHUB",
            description=(
                "**Bienvenue sur le support OkveHUB !**\n\n"
                "Choisis une catégorie dans le menu ci-dessous :\n\n"
                "🆘 Support technique\n"
                "💳 Achat / Commande\n"
                "🔐 Whitelist / HWID\n"
                "🐛 Bug Report\n"
                "🤝 Partenariat\n"
                "⚖️ Litige / Remboursement"
            ),
            color=COLOR_TICKET,
            timestamp=discord.utils.utcnow()
        )

        embed.set_footer(text="OkveHUB Support System")

        await interaction.channel.send(
            embed=embed,
            view=TicketSelectView()
        )

        await interaction.response.send_message(
            "✅ Panel ticket créé.",
            ephemeral=True
        )

    @app_commands.command(name="ticket-close", description="Fermer le ticket actuel")
    async def ticket_close(self, interaction: discord.Interaction, raison: str = "Fermé par le staff"):
        ticket = await db_fetchone(
            "SELECT * FROM tickets WHERE channel_id=?",
            (str(interaction.channel_id),)
        )

        if not ticket:
            return await interaction.response.send_message(
                "❌ Ce salon n'est pas un ticket.",
                ephemeral=True
            )

        if str(interaction.user.id) != ticket["user_id"] and not is_staff(interaction.user):
            return await interaction.response.send_message(
                "❌ Seul le créateur ou le staff peut fermer ce ticket.",
                ephemeral=True
            )

        await db_execute(
            "UPDATE tickets SET status='closed', closed_at=strftime('%s','now') WHERE ticket_id=?",
            (ticket["ticket_id"],)
        )

        await interaction.response.send_message(
            embed=success_embed(
                "Ticket fermé",
                f"Raison : {raison}\nSuppression dans 5 secondes."
            )
        )

        await asyncio.sleep(5)
        await interaction.channel.delete()


async def setup(bot):
    await bot.add_cog(Tickets(bot))
