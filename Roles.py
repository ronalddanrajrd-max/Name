import discord
from discord import app_commands
from discord.ext import commands
from Helpers import *
import os


REACTION_ROLES = {}


class RolePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🛒 Acheteur",
        style=discord.ButtonStyle.success,
        custom_id="role_acheteur_btn"
    )
    async def acheteur(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        role_id = os.getenv("ROLE_ACHETEUR")

        if not role_id:
            return await interaction.response.send_message(
                "❌ ROLE_ACHETEUR manquant.",
                ephemeral=True
            )

        role = interaction.guild.get_role(int(role_id))

        if not role:
            return await interaction.response.send_message(
                "❌ Rôle Acheteur introuvable.",
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
        custom_id="role_whitelist_btn"
    )
    async def whitelist(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        role_id = os.getenv("ROLE_WHITELIST")

        if not role_id:
            return await interaction.response.send_message(
                "❌ ROLE_WHITELIST manquant.",
                ephemeral=True
            )

        role = interaction.guild.get_role(int(role_id))

        if not role:
            return await interaction.response.send_message(
                "❌ Rôle Whitelist introuvable.",
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


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==================================
    # ADD ROLE
    # ==================================

    @app_commands.command(
        name="add-role",
        description="Ajouter un rôle"
    )
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

            await interaction.response.send_message(
                embed=success_embed(
                    "Rôle ajouté",
                    f"{utilisateur.mention} a reçu {role.mention}."
                )
            )

        except Exception as e:
            await interaction.response.send_message(
                embed=error_embed("Erreur", str(e)),
                ephemeral=True
            )

    # ==================================
    # REMOVE ROLE
    # ==================================

    @app_commands.command(
        name="remove-role",
        description="Retirer un rôle"
    )
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

            await interaction.response.send_message(
                embed=success_embed(
                    "Rôle retiré",
                    f"{role.mention} retiré à {utilisateur.mention}."
                )
            )

        except Exception as e:
            await interaction.response.send_message(
                embed=error_embed("Erreur", str(e)),
                ephemeral=True
            )

    # ==================================
    # USER ROLES
    # ==================================

    @app_commands.command(
        name="user-roles",
        description="Voir les rôles d'un utilisateur"
    )
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
            title=f"🎭 Rôles de {target}",
            description="\n".join(roles) if roles else "Aucun rôle.",
            color=0x3498DB
        )

        await interaction.response.send_message(embed=embed)

    # ==================================
    # ROLE PANEL
    # ==================================

    @app_commands.command(
        name="role-panel",
        description="Créer un panel de rôles"
    )
    async def role_panel(
        self,
        interaction: discord.Interaction
    ):
        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title="🎭・Role Panel",
            description=(
                "Clique sur les boutons ci-dessous "
                "pour récupérer ou retirer tes rôles."
            ),
            color=0x000000
        )

        await interaction.channel.send(
            embed=embed,
            view=RolePanel()
        )

        await interaction.response.send_message(
            "✅ Panel de rôles envoyé.",
            ephemeral=True
        )

    # ==================================
    # REACTION ROLE
    # ==================================

    @app_commands.command(
        name="reaction-role",
        description="Créer un reaction role"
    )
    async def reaction_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        emoji: str,
        titre: str = "Reaction Role"
    ):
        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title=titre,
            description=f"Réagis avec {emoji} pour obtenir le rôle {role.mention}.",
            color=0x000000
        )

        msg = await interaction.channel.send(embed=embed)

        try:
            await msg.add_reaction(emoji)
        except:
            return await interaction.response.send_message(
                "❌ Emoji invalide.",
                ephemeral=True
            )

        REACTION_ROLES[msg.id] = {
            "role_id": role.id,
            "emoji": emoji
        }

        await interaction.response.send_message(
            f"✅ Reaction role créé : {emoji} → {role.mention}",
            ephemeral=True
        )

    # ==================================
    # REACTION ADD
    # ==================================

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return

        data = REACTION_ROLES.get(payload.message_id)

        if not data:
            return

        if str(payload.emoji) != data["emoji"]:
            return

        guild = self.bot.get_guild(payload.guild_id)

        if not guild:
            return

        member = guild.get_member(payload.user_id)

        if not member:
            return

        role = guild.get_role(data["role_id"])

        if not role:
            return

        try:
            await member.add_roles(role)
        except:
            pass

    # ==================================
    # REACTION REMOVE
    # ==================================

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        data = REACTION_ROLES.get(payload.message_id)

        if not data:
            return

        if str(payload.emoji) != data["emoji"]:
            return

        guild = self.bot.get_guild(payload.guild_id)

        if not guild:
            return

        member = guild.get_member(payload.user_id)

        if not member:
            return

        role = guild.get_role(data["role_id"])

        if not role:
            return

        try:
            await member.remove_roles(role)
        except:
            pass


async def setup(bot):
    await bot.add_cog(Roles(bot))
