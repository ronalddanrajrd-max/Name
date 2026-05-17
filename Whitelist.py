import discord
from discord import app_commands
from discord.ext import commands
import os
from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *


class RedeemModal(discord.ui.Modal, title="🔑 Redeem Key"):
    key = discord.ui.TextInput(
        label="Entre ta clé",
        placeholder="Exemple : OKV-XXXX-XXXX",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        # Ici on considère que la clé entrée donne accès
        await db_execute("""
            INSERT INTO whitelist (user_id, username, added_by, reason, script_access)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                reason=excluded.reason,
                script_access=excluded.script_access
        """, (
            user_id,
            str(interaction.user),
            "redeem_key",
            f"Key redeem: {self.key.value}",
            "all"
        ))

        role_id = os.getenv("ROLE_WHITELIST")
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            if role:
                await interaction.user.add_roles(role)

        await interaction.response.send_message(
            embed=success_embed("Whitelist activée", "Tu es maintenant whitelist ✅"),
            ephemeral=True
        )


class WhitelistPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔑 Redeem Key", style=discord.ButtonStyle.success, custom_id="wl_redeem")
    async def redeem_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RedeemModal())

    @discord.ui.button(label="📜 Get Script", style=discord.ButtonStyle.primary, custom_id="wl_get_script")
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(interaction.user.id),))

        if not row:
            return await interaction.response.send_message(
                embed=error_embed("Accès refusé", "Tu n'es pas whitelist."),
                ephemeral=True
            )

        script_url = os.getenv("SCRIPT_URL")

        if not script_url:
            return await interaction.response.send_message(
                embed=error_embed("Script non configuré", "Ajoute SCRIPT_URL dans les variables Railway."),
                ephemeral=True
            )

        embed = discord.Embed(
            title="📜 Ton script",
            description=f"Voici ton script :\n```lua\nloadstring(game:HttpGet('{script_url}'))()\n```",
            color=COLOR_SUCCESS
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="👥 Get Role", style=discord.ButtonStyle.primary, custom_id="wl_get_role")
    async def get_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(interaction.user.id),))

        if not row:
            return await interaction.response.send_message(
                embed=error_embed("Accès refusé", "Tu n'es pas whitelist."),
                ephemeral=True
            )

        role_id = os.getenv("ROLE_WHITELIST")

        if not role_id:
            return await interaction.response.send_message(
                embed=error_embed("Rôle non configuré", "Ajoute ROLE_WHITELIST dans Railway."),
                ephemeral=True
            )

        role = interaction.guild.get_role(int(role_id))

        if not role:
            return await interaction.response.send_message(
                embed=error_embed("Rôle introuvable", "L'ID ROLE_WHITELIST est incorrect."),
                ephemeral=True
            )

        await interaction.user.add_roles(role)

        await interaction.response.send_message(
            embed=success_embed("Rôle donné", f"Tu as reçu le rôle {role.mention}."),
            ephemeral=True
        )

    @discord.ui.button(label="⚙️ Reset HWID", style=discord.ButtonStyle.secondary, custom_id="wl_reset_hwid")
    async def reset_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(interaction.user.id),))

        if not row:
            return await interaction.response.send_message(
                embed=error_embed("Accès refusé", "Tu n'es pas whitelist."),
                ephemeral=True
            )

        await db_execute("UPDATE whitelist SET hwid=NULL WHERE user_id=?", (str(interaction.user.id),))

        await interaction.response.send_message(
            embed=success_embed("HWID reset", "Ton HWID a été réinitialisé ✅"),
            ephemeral=True
        )

    @discord.ui.button(label="📊 Get Stats", style=discord.ButtonStyle.secondary, custom_id="wl_stats")
    async def get_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        total = await db_fetchall("SELECT * FROM whitelist")
        user = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(interaction.user.id),))

        embed = discord.Embed(
            title="📊 Stats Whitelist",
            color=COLOR_INFO
        )

        embed.add_field(name="👥 Total whitelist", value=str(len(total)), inline=True)
        embed.add_field(name="🔐 Ton statut", value="✅ Whitelist" if user else "❌ Non whitelist", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class Whitelist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="whitelist-panel", description="Créer le panel whitelist")
    async def whitelist_panel(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title="FunHub",
            description=(
                "This control panel is for the project: **FunHub**\n"
                "If you're a buyer, click on the buttons below to redeem your key, "
                "get the script or get your role."
            ),
            color=COLOR_GOLD
        )

        embed.set_footer(text=f"Sent by {interaction.user}")

        await interaction.channel.send(embed=embed, view=WhitelistPanel())

        await interaction.response.send_message(
            embed=success_embed("Panel créé", "Le panel whitelist a été envoyé."),
            ephemeral=True
        )

    @app_commands.command(name="wl-add", description="Ajouter un utilisateur à la whitelist")
    async def wl_add(self, interaction: discord.Interaction, utilisateur: discord.Member, raison: str = "Ajout manuel"):
        if not await check_permission(interaction, "staff"):
            return

        await db_execute("""
            INSERT INTO whitelist (user_id, username, added_by, reason, script_access)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                added_by=excluded.added_by,
                reason=excluded.reason,
                script_access=excluded.script_access
        """, (
            str(utilisateur.id),
            str(utilisateur),
            str(interaction.user.id),
            raison,
            "all"
        ))

        role_id = os.getenv("ROLE_WHITELIST")
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            if role:
                await utilisateur.add_roles(role)

        await interaction.response.send_message(
            embed=success_embed("Whitelist ajoutée", f"{utilisateur.mention} est maintenant whitelist."),
            ephemeral=True
        )

    @app_commands.command(name="wl-remove", description="Retirer un utilisateur de la whitelist")
    async def wl_remove(self, interaction: discord.Interaction, utilisateur: discord.Member):
        if not await check_permission(interaction, "staff"):
            return

        await db_execute("DELETE FROM whitelist WHERE user_id=?", (str(utilisateur.id),))

        role_id = os.getenv("ROLE_WHITELIST")
        if role_id:
            role = interaction.guild.get_role(int(role_id))
            if role:
                await utilisateur.remove_roles(role)

        await interaction.response.send_message(
            embed=success_embed("Whitelist retirée", f"{utilisateur.mention} n'est plus whitelist."),
            ephemeral=True
        )

    @app_commands.command(name="wl-check", description="Vérifier si un utilisateur est whitelist")
    async def wl_check(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user

        row = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(target.id),))

        if not row:
            return await interaction.response.send_message(
                embed=error_embed("Non whitelist", f"{target.mention} n'est pas whitelist."),
                ephemeral=True
            )

        embed = discord.Embed(
            title="🔐 Whitelist active",
            color=COLOR_SUCCESS
        )

        embed.add_field(name="Utilisateur", value=target.mention, inline=True)
        embed.add_field(name="Script", value=row["script_access"] or "all", inline=True)
        embed.add_field(name="HWID", value=row["hwid"] or "Non défini", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Whitelist(bot))
