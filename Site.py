import discord
from discord import app_commands
from discord.ext import commands
import os


class Site(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="okvehubsite",
        description="Afficher le site OkveHUB"
    )
    async def okvehubsite(
        self,
        interaction: discord.Interaction
    ):
        owner_id = os.getenv("OWNER_ID")

        if not owner_id:
            return await interaction.response.send_message(
                "❌ OWNER_ID manquant dans Railway.",
                ephemeral=True
            )

        if str(interaction.user.id) != owner_id:
            return await interaction.response.send_message(
                "❌ Seul le owner peut utiliser cette commande.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🌐・OkveHUB Site",
            description=(
                "[Clique ici pour ouvrir le site]"
                "(https://name-production-e582.up.railway.app/)"
            ),
            color=0x000000
        )

        embed.set_footer(
            text="OkveHUB Website"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=False
        )


async def setup(bot):
    await bot.add_cog(Site(bot))
