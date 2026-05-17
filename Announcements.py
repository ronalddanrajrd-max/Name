import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
from utils.helpers import *


class Announcements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    annonce = app_commands.Group(name="annonce", description="Système d'annonces OkveHUB")

    @annonce.command(name="envoyer", description="Envoyer une annonce dans un salon")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(salon="Salon cible", titre="Titre", message="Contenu", couleur="Couleur hex (#FF0000)", ping="@everyone / @here / ID rôle", image="URL image")
    async def envoyer(self, interaction: discord.Interaction,
                      salon: discord.TextChannel,
                      titre: str,
                      message: str,
                      couleur: str = None,
                      ping: str = None,
                      image: str = None):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        color = Colors.MAIN
        if couleur:
            try:
                color = int(couleur.lstrip("#"), 16)
            except Exception:
                pass

        embed = discord.Embed(title=f"📢 {titre}", description=message, color=color)
        embed.set_footer(text=f"Annonce par {interaction.user} • OkveHUB", icon_url=interaction.user.display_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        if image:
            embed.set_image(url=image)

        content = None
        if ping == "@everyone":
            content = "@everyone"
        elif ping == "@here":
            content = "@here"
        elif ping:
            content = f"<@&{ping}>"

        await salon.send(content=content, embed=embed)
        await interaction.response.send_message(embed=embed_success(f"✅ Annonce envoyée dans {salon.mention}."), ephemeral=True)

    @annonce.command(name="update", description="Annoncer une mise à jour de script")
    @app_commands.default_permissions(manage_messages=True)
    async def update(self, interaction: discord.Interaction,
                     salon: discord.TextChannel,
                     script: str,
                     version: str,
                     changements: str):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        embed = discord.Embed(title=f"🔄 Mise à jour — {script}", color=Colors.SUCCESS)
        embed.add_field(name="🏷️ Version", value=f"**{version}**", inline=True)
        embed.add_field(name="📅 Date", value=f"<t:{int(__import__('time').time())}:D>", inline=True)
        embed.add_field(name="📋 Changements", value=changements, inline=False)
        embed.set_footer(text="OkveHUB Updates")
        embed.timestamp = discord.utils.utcnow()

        await salon.send(content="@everyone", embed=embed)
        await interaction.response.send_message(embed=embed_success(f"✅ Annonce update envoyée dans {salon.mention}."), ephemeral=True)

    @annonce.command(name="promo", description="Annonce de promotion / vente")
    @app_commands.default_permissions(manage_messages=True)
    async def promo(self, interaction: discord.Interaction,
                    salon: discord.TextChannel,
                    script: str,
                    reduction: str,
                    prix: str,
                    duree: str):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        shop_url = os.getenv("SHOP_URL", "https://ton-site.com")
        embed = discord.Embed(title=f"🔥 PROMO — {script}", description=f"Offre exceptionnelle sur **{script}** !", color=Colors.GOLD)
        embed.add_field(name="💸 Réduction", value=f"**-{reduction}%**", inline=True)
        embed.add_field(name="💰 Prix final", value=f"**{prix}**", inline=True)
        embed.add_field(name="⏳ Durée", value=f"**{duree}**", inline=True)
        embed.add_field(name="🛒 Acheter", value=f"[Clique ici]({shop_url})")
        embed.set_footer(text="OkveHUB Shop • Offre limitée !")
        embed.timestamp = discord.utils.utcnow()

        await salon.send(content="@everyone", embed=embed)
        await interaction.response.send_message(embed=embed_success(f"✅ Annonce promo envoyée."), ephemeral=True)

    @annonce.command(name="dm", description="Envoyer un DM à tous les membres (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def dm_all(self, interaction: discord.Interaction,
                     message: str,
                     role: discord.Role = None):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        members = [m for m in interaction.guild.members if not m.bot]
        if role:
            members = [m for m in members if role in m.roles]

        sent, failed = 0, 0
        embed = discord.Embed(title="📬 Message de OkveHUB", description=message, color=Colors.MAIN)
        embed.set_footer(text="OkveHUB")
        embed.timestamp = discord.utils.utcnow()

        for member in members:
            try:
                await member.send(embed=embed)
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.3)

        await interaction.followup.send(embed=embed_success(f"📬 DM envoyé !\n✅ Réussis : **{sent}**\n❌ Échoués : **{failed}**"), ephemeral=True)

    @annonce.command(name="embed_simple", description="Annonce embed rapide avec couleur")
    @app_commands.default_permissions(manage_messages=True)
    async def embed_simple(self, interaction: discord.Interaction,
                           salon: discord.TextChannel,
                           description: str,
                           titre: str = "📢 Annonce",
                           ping: str = None):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        embed = discord.Embed(title=titre, description=description, color=Colors.MAIN)
        embed.set_footer(text="OkveHUB", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.timestamp = discord.utils.utcnow()

        content = "@everyone" if ping == "@everyone" else "@here" if ping == "@here" else f"<@&{ping}>" if ping else None
        await salon.send(content=content, embed=embed)
        await interaction.response.send_message(embed=embed_success(f"✅ Annonce envoyée dans {salon.mention}."), ephemeral=True)


async def setup(bot):
    await bot.add_cog(Announcements(bot))
