import discord
from discord import app_commands
from discord.ext import commands

from Helpers import check_permission


class Reglement(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="reglement", description="Envoyer le règlement OkveHUB")
    async def reglement(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title="📜・Règlement Officiel — OkveHUB",
            description=(
                "Bienvenue sur le serveur officiel **OkveHUB**.\n\n"
                "En rejoignant ce serveur et en utilisant nos scripts, vous acceptez automatiquement ce règlement."
            ),
            color=0x000000
        )

        embed.add_field(
            name="🔒・Partage & Revente",
            value=(
                "• Le partage de script est strictement interdit.\n"
                "• Le partage de key est strictement interdit.\n"
                "• La revente de nos scripts est interdite.\n"
                "• Le leak du script ou du loader entraîne une blacklist permanente."
            ),
            inline=False
        )

        embed.add_field(
            name="🔑・Système de Key",
            value=(
                "• Une key est personnelle.\n"
                "• Une key ne doit pas être partagée.\n"
                "• Les accès peuvent être liés au HWID.\n"
                "• Toute tentative de contournement est interdite."
            ),
            inline=False
        )

        embed.add_field(
            name="⛔・Blacklist",
            value=(
                "Vous pouvez être blacklist pour :\n"
                "• partage de script ou de key ;\n"
                "• tentative de dump ;\n"
                "• revente ;\n"
                "• scam ;\n"
                "• contournement du système."
            ),
            inline=False
        )

        embed.add_field(
            name="💬・Comportement",
            value=(
                "• Respect obligatoire envers tous les membres.\n"
                "• Aucun spam.\n"
                "• Aucun scam.\n"
                "• Aucune insulte ou provocation excessive."
            ),
            inline=False
        )

        embed.add_field(
            name="🛠️・Support",
            value=(
                "• Ouvrez un ticket en cas de problème.\n"
                "• Soyez patient avec le staff.\n"
                "• Les remboursements ne sont pas garantis."
            ),
            inline=False
        )

        embed.add_field(
            name="✅・Acceptation",
            value=(
                "En utilisant **OkveHUB**, vous acceptez :\n"
                "• le règlement du serveur ;\n"
                "• le système whitelist ;\n"
                "• les protections anti-partage ;\n"
                "• les sanctions appliquées par le staff."
            ),
            inline=False
        )

        embed.set_footer(text="OkveHUB Protection System")

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Règlement envoyé.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Reglement(bot))
