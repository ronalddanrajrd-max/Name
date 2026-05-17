import discord
from discord import app_commands
from discord.ext import commands
import os
from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *


class RedeemModal(discord.ui.Modal, title="Redeem Key"):
    key_code = discord.ui.TextInput(
        label="Entre ta key",
        placeholder="OKV-XXXXXXXX",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key_code.value.strip().upper()

        row = await db_fetchone(
            "SELECT * FROM keys WHERE key_code=?",
            (key,)
        )

        if not row:
            return await interaction.response.send_message(
                embed=error_embed("Key invalide", "Cette key n'existe pas."),
                ephemeral=True
            )

        if row["used_by"]:
            return await interaction.response.send_message(
                embed=error_embed("Key déjà utilisée", "Cette key a déjà été utilisée."),
                ephemeral=True
            )

        script_name = row["script_name"] or "main"

        await db_execute("""
        INSERT INTO whitelist (
            user_id,
            username,
            added_by,
            reason,
            script_access
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            reason=excluded.reason,
            script_access=excluded.script_access
        """, (
            str(interaction.user.id),
            str(interaction.user),
            "redeem_key",
            f"Redeemed {key}",
            script_name
        ))

        await db_execute(
            "UPDATE keys SET used_by=?, used_at=strftime('%s','now') WHERE key_code=?",
            (str(interaction.user.id), key)
        )

        role_id = os.getenv("ROLE_WHITELIST")

        if role_id:
            role = interaction.guild.get_role(int(role_id))

            if role:
                await interaction.user.add_roles(role)

        await interaction.response.send_message(
            embed=success_embed(
                "Whitelist activée",
                f"Tu as maintenant accès au script **{script_name}**"
            ),
            ephemeral=True
        )


class WhitelistPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔑 Redeem Key",
        style=discord.ButtonStyle.success,
        custom_id="redeem_key"
    )
    async def redeem_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RedeemModal())

    @discord.ui.button(
        label="📜 Get Script",
        style=discord.ButtonStyle.primary,
        custom_id="get_script"
    )
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):

        wl = await db_fetchone(
            "SELECT * FROM whitelist WHERE user_id=?",
            (str(interaction.user.id),)
        )

        if not wl:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Accès refusé",
                    "Tu n'es pas whitelist."
                ),
                ephemeral=True
            )

        key = await db_fetchone(
            "SELECT * FROM keys WHERE used_by=? ORDER BY used_at DESC LIMIT 1",
            (str(interaction.user.id),)
        )

        if not key:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Aucune key",
                    "Aucune key liée à ton compte."
                ),
                ephemeral=True
            )

        base_url = os.getenv("BASE_URL")

        if not base_url:
            return await interaction.response.send_message(
                embed=error_embed(
                    "BASE_URL manquant",
                    "Ajoute BASE_URL dans Railway."
                ),
                ephemeral=True
            )

        loader = f'''script_key = "{key["key_code"]}"

loadstring(game:HttpGet(
    "{base_url}/load?key=" .. script_key
))()'''

        embed = discord.Embed(
            title="📜 Ton Loader",
            description=f"```lua\n{loader}\n```",
            color=COLOR_SUCCESS
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @discord.ui.button(
        label="👥 Get Role",
        style=discord.ButtonStyle.primary,
        custom_id="get_role"
    )
    async def get_role(self, interaction: discord.Interaction, button: discord.ui.Button):

        wl = await db_fetchone(
            "SELECT * FROM whitelist WHERE user_id=?",
            (str(interaction.user.id),)
        )

        if not wl:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Accès refusé",
                    "Tu n'es pas whitelist."
                ),
                ephemeral=True
            )

        role_id = os.getenv("ROLE_WHITELIST")

        if not role_id:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Erreur config",
                    "ROLE_WHITELIST manquant."
                ),
                ephemeral=True
            )

        role = interaction.guild.get_role(int(role_id))

        if not role:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Rôle introuvable",
                    "L'ID du rôle est incorrect."
                ),
                ephemeral=True
            )

        await interaction.user.add_roles(role)

        await interaction.response.send_message(
            embed=success_embed(
                "Rôle donné",
                f"Tu as reçu le rôle {role.mention}"
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="⚙️ Reset HWID",
        style=discord.ButtonStyle.secondary,
        custom_id="reset_hwid"
    )
    async def reset_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):

        wl = await db_fetchone(
            "SELECT * FROM whitelist WHERE user_id=?",
            (str(interaction.user.id),)
        )

        if not wl:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Accès refusé",
                    "Tu n'es pas whitelist."
                ),
                ephemeral=True
            )

        await db_execute(
            "UPDATE whitelist SET hwid=NULL WHERE user_id=?",
            (str(interaction.user.id),)
        )

        await interaction.response.send_message(
            embed=success_embed(
                "HWID reset",
                "Ton HWID a été réinitialisé."
            ),
            ephemeral=True
        )

    @discord.ui.button(
        label="📊 Get Stats",
        style=discord.ButtonStyle.secondary,
        custom_id="get_stats"
    )
    async def get_stats(self, interaction: discord.Interaction, button: discord.ui.Button):

        total_wl = await db_fetchall("SELECT * FROM whitelist")
        total_keys = await db_fetchall("SELECT * FROM keys")

        embed = discord.Embed(
            title="📊 Statistiques",
            color=COLOR_INFO
        )

        embed.add_field(
            name="Whitelist",
            value=str(len(total_wl)),
            inline=True
        )

        embed.add_field(
            name="Keys",
            value=str(len(total_keys)),
            inline=True
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


class Whitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="whitelist-panel",
        description="Créer le panel whitelist"
    )
    async def whitelist_panel(self, interaction: discord.Interaction):

        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title="OkveHUB — Whitelist Panel",
            description=(
                "Bienvenue sur le panel whitelist.\n\n"
                "🔑 Redeem Key : utiliser une clé\n"
                "📜 Get Script : récupérer ton loader\n"
                "👥 Get Role : récupérer ton rôle\n"
                "⚙️ Reset HWID : reset ton HWID\n"
                "📊 Get Stats : voir les statistiques"
            ),
            color=COLOR_GOLD
        )

        await interaction.channel.send(
            embed=embed,
            view=WhitelistPanel()
        )

        await interaction.response.send_message(
            "✅ Panel envoyé.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Whitelist(bot))
