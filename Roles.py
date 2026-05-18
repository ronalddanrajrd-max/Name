import discord
from discord import app_commands
from discord.ext import commands

from Helpers import *


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # =========================
    # ADD ROLE
    # =========================

    @app_commands.command(name="add-role", description="Ajouter un rôle à un utilisateur")
    async def add_role(
        self,
        interaction: discord.Interaction,
        utilisateur: discord.Member,
        role: discord.Role
    ):
        if not await check_permission(interaction, "staff"):
            return

        try:
            await utilisateur.add_roles(role)

            embed = success_embed(
                "Rôle ajouté",
                f"{utilisateur.mention} a reçu le rôle {role.mention}"
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=error_embed("Erreur", str(e)),
                ephemeral=True
            )

    # =========================
    # REMOVE ROLE
    # =========================

    @app_commands.command(name="remove-role", description="Retirer un rôle")
    async def remove_role(
        self,
        interaction: discord.Interaction,
        utilisateur: discord.Member,
        role: discord.Role
    ):
        if not await check_permission(interaction, "staff"):
            return

        try:
            await utilisateur.remove_roles(role)

            embed = success_embed(
                "Rôle retiré",
                f"{role.mention} retiré à {utilisateur.mention}"
            )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(
                embed=error_embed("Erreur", str(e)),
                ephemeral=True
            )

    # =========================
    # ROLE PANEL
    # =========================

    @app_commands.command(name="role-panel", description="Créer un panel de rôles")
    async def role_panel(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title="🎭・Role Panel",
            description=(
                "Clique sur les boutons pour récupérer tes rôles."
            ),
            color=0x000000
        )

        await interaction.channel.send(
            embed=embed,
            view=RolePanel()
        )

        await interaction.response.send_message(
            "✅ Panel envoyé.",
            ephemeral=True
        )

    # =========================
    # USER ROLES
    # =========================

    @app_commands.command(name="user-roles", description="Voir les rôles d'un utilisateur")
    async def user_roles(
        self,
        interaction: discord.Interaction,
        utilisateur: discord.Member = None
    ):
        target = utilisateur or interaction.user

        roles = [
            role.mention
            for role in target.roles
            if role.name != "@everyone"
        ]

        embed = discord.Embed(
            title=f"🎭 Roles de {target}",
            description="\n".join(roles) if roles else "Aucun rôle.",
            color=0x3498DB
        )

        await interaction.response.send_message(embed=embed)

    # =========================
    # LOCK CHANNEL
    # =========================

    @app_commands.command(name="lock", description="Verrouiller le salon")
    async def lock(
        self,
        interaction: discord.Interaction
    ):
        if not await check_permission(interaction, "staff"):
            return

        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = False

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite
        )

        embed = success_embed(
            "Salon verrouillé",
            "Le salon a été verrouillé."
        )

        await interaction.response.send_message(embed=embed)

    # =========================
    # UNLOCK CHANNEL
    # =========================

    @app_commands.command(name="unlock", description="Déverrouiller le salon")
    async def unlock(
        self,
        interaction: discord.Interaction
    ):
        if not await check_permission(interaction, "staff"):
            return

        overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True

        await interaction.channel.set_permissions(
            interaction.guild.default_role,
            overwrite=overwrite
        )

        embed = success_embed(
            "Salon déverrouillé",
            "Le salon a été déverrouillé."
        )

        await interaction.response.send_message(embed=embed)


# ==================================
# ROLE BUTTON PANEL
# ==================================

class RolePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🛒 Acheteur",
        style=discord.ButtonStyle.success,
        custom_id="role_acheteur"
    )
    async def acheteur(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        role_id = os.getenv("ROLE_ACHETEUR")

        if not role_id:
            return await interaction.response.send_message(
                "ROLE_ACHETEUR manquant.",
                ephemeral=True
            )

        role = interaction.guild.get_role(int(role_id))

        if not role:
            return await interaction.response.send_message(
                "Role introuvable.",
                ephemeral=True
            )

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)

            return await interaction.response.send_message(
                f"❌ Rôle {role.mention} retiré.",
                ephemeral=True
            )

        await interaction.user.add_roles(role)

        await interaction.response.send_message(
            f"✅ Rôle {role.mention} ajouté.",
            ephemeral=True
        )

    @discord.ui.button(
        label="🔐 Whitelist",
        style=discord.ButtonStyle.primary,
        custom_id="role_whitelist"
    )
    async def whitelist(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        role_id = os.getenv("ROLE_WHITELIST")

        if not role_id:
            return await interaction.response.send_message(
                "ROLE_WHITELIST manquant.",
                ephemeral=True
            )

        role = interaction.guild.get_role(int(role_id))

        if not role:
            return await interaction.response.send_message(
                "Role introuvable.",
                ephemeral=True
            )

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)

            return await interaction.response.send_message(
                f"❌ Rôle {role.mention} retiré.",
                ephemeral=True
            )

        await interaction.user.add_roles(role)

        await interaction.response.send_message(
            f"✅ Rôle {role.mention} ajouté.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Roles(bot))
