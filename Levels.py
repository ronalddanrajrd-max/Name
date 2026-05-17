import discord
from discord import app_commands
from discord.ext import commands
import random, os
from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._cooldown = {}

    def xp_for_level(self, level):
        return 100 * (level ** 2) + 50 * level + 100

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        uid = str(message.author.id)
        gid = str(message.guild.id)
        import time
        now = time.time()
        key = f"{uid}-{gid}"
        if key in self._cooldown and now - self._cooldown[key] < 60: return
        self._cooldown[key] = now

        row = await db_fetchone("SELECT * FROM levels WHERE user_id=? AND guild_id=?", (uid, gid))
        xp_gain = random.randint(15, 30)
        if not row:
            await db_execute("INSERT INTO levels (user_id, guild_id, xp, level, messages) VALUES (?,?,?,0,1)", (uid, gid, xp_gain))
            return
        new_xp = row["xp"] + xp_gain
        new_msgs = row["messages"] + 1
        new_level = row["level"]
        leveled_up = False
        while new_xp >= self.xp_for_level(new_level + 1):
            new_xp -= self.xp_for_level(new_level + 1)
            new_level += 1
            leveled_up = True
        await db_execute("UPDATE levels SET xp=?, level=?, messages=? WHERE user_id=? AND guild_id=?",
            (new_xp, new_level, new_msgs, uid, gid))
        if leveled_up:
            embed = discord.Embed(title="🎉 Level Up !", description=f"{message.author.mention} est maintenant niveau **{new_level}** ! 🚀", color=COLOR_GOLD)
            await message.channel.send(embed=embed, delete_after=10)

    @app_commands.command(name="rank", description="📊 Voir ton niveau XP")
    @app_commands.describe(utilisateur="Utilisateur")
    async def rank(self, interaction: discord.Interaction, utilisateur: discord.Member = None):
        target = utilisateur or interaction.user
        row = await db_fetchone("SELECT * FROM levels WHERE user_id=? AND guild_id=?", (str(target.id), str(interaction.guild_id)))
        if not row:
            return await interaction.response.send_message(embed=info_embed("Aucune donnée", f"**{target}** n'a pas encore de niveau."), ephemeral=True)
        needed = self.xp_for_level(row["level"] + 1)
        bar_filled = int((row["xp"] / needed) * 20)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        embed = discord.Embed(title=f"📊 Rang de {target}", color=target.color or COLOR_MAIN, timestamp=discord.utils.utcnow())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="⭐ Niveau", value=f"`{row['level']}`", inline=True)
        embed.add_field(name="✨ XP", value=f"`{row['xp']}/{needed}`", inline=True)
        embed.add_field(name="💬 Messages", value=f"`{row['messages']}`", inline=True)
        embed.add_field(name="📈 Progression", value=f"`{bar}` {int(row['xp']/needed*100)}%", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="🏆 Classement XP du serveur")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = await db_fetchall("SELECT * FROM levels WHERE guild_id=? ORDER BY level DESC, xp DESC LIMIT 10", (str(interaction.guild_id),))
        if not rows:
            return await interaction.response.send_message(embed=info_embed("Vide", "Aucune donnée de niveau."), ephemeral=True)
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        lines = []
        for i, r in enumerate(rows):
            user = interaction.guild.get_member(int(r["user_id"]))
            name = user.display_name if user else f"Utilisateur inconnu"
            lines.append(f"{medals[i]} **{name}** — Niveau `{r['level']}` — `{r['xp']} XP`")
        embed = discord.Embed(title="🏆 Classement OkveHUB", description="\n".join(lines), color=COLOR_GOLD, timestamp=discord.utils.utcnow())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="xp-add", description="➕ Ajouter de l'XP à un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur", quantite="Quantité d'XP")
    async def xp_add(self, interaction: discord.Interaction, utilisateur: discord.Member, quantite: int):
        if not await check_permission(interaction, "admin"): return
        row = await db_fetchone("SELECT * FROM levels WHERE user_id=? AND guild_id=?", (str(utilisateur.id), str(interaction.guild_id)))
        if not row:
            await db_execute("INSERT INTO levels (user_id, guild_id, xp, level, messages) VALUES (?,?,?,0,0)", (str(utilisateur.id), str(interaction.guild_id), quantite))
        else:
            await db_execute("UPDATE levels SET xp=xp+? WHERE user_id=? AND guild_id=?", (quantite, str(utilisateur.id), str(interaction.guild_id)))
        await interaction.response.send_message(embed=success_embed("XP Ajouté", f"**{quantite} XP** ajouté à {utilisateur.mention}."))

async def setup(bot):
    await bot.add_cog(Levels(bot))
