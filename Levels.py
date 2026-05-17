import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import time
from utils.helpers import *
from utils.database import DB_PATH


class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    niveau = app_commands.Group(name="niveau", description="Système de niveaux XP")

    @niveau.command(name="rank", description="Voir ton niveau ou celui d'un membre")
    async def rank(self, interaction: discord.Interaction, membre: discord.Member = None):
        user = membre or interaction.user
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM levels WHERE user_id=? AND guild_id=?", (str(user.id), str(interaction.guild.id)))
            data = await cur.fetchone()

        if not data:
            return await interaction.response.send_message(embed=embed_info(f"**{user.name}** n'a pas encore d'XP. Écris des messages !"), ephemeral=True)

        level = calculate_level(data["xp"])
        current_xp = xp_for_level(level)
        next_xp = xp_for_level(level + 1)
        prog_xp = data["xp"] - current_xp
        needed = next_xp - current_xp
        pct = min(100, int((prog_xp / needed) * 100)) if needed > 0 else 100

        bar = progress_bar(pct)

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT user_id FROM levels WHERE guild_id=? ORDER BY xp DESC", (str(interaction.guild.id),))
            all_users = [r[0] for r in await cur.fetchall()]
        rank = (all_users.index(str(user.id)) + 1) if str(user.id) in all_users else "?"

        embed = discord.Embed(title=f"📊 Niveau — {user.name}", color=Colors.PURPLE)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="🎯 Niveau", value=f"**{level}**", inline=True)
        embed.add_field(name="⭐ XP Total", value=f"**{data['xp']:,}**", inline=True)
        embed.add_field(name="🏆 Classement", value=f"**#{rank}**", inline=True)
        embed.add_field(name="💬 Messages", value=f"**{data['total_messages']:,}**", inline=True)
        embed.add_field(name=f"Progression → Niveau {level + 1}",
                        value=f"`{bar}` **{pct}%**\n{prog_xp:,} / {needed:,} XP", inline=False)
        embed.set_footer(text="OkveHUB • Système de niveaux")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)

    @niveau.command(name="top", description="Classement XP du serveur")
    async def top(self, interaction: discord.Interaction, page: app_commands.Range[int, 1, 20] = 1):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM levels WHERE guild_id=? ORDER BY xp DESC", (str(interaction.guild.id),))
            all_rows = await cur.fetchall()

        per_page = 10
        pages = max(1, -(-len(all_rows) // per_page))
        page = min(page, pages)
        items = paginate(list(all_rows), per_page, page - 1)

        medals = ["🥇", "🥈", "🥉"]
        desc = "\n".join(
            f"{medals[i] if (page-1)*per_page+i < 3 else f'`{(page-1)*per_page+i+1}.`'} "
            f"<@{r['user_id']}> — **Niveau {calculate_level(r['xp'])}** • {r['xp']:,} XP"
            for i, r in enumerate(items)
        ) or "*Aucun membre classé.*"

        embed = discord.Embed(title=f"🏆 Classement XP — {interaction.guild.name}", description=desc, color=Colors.GOLD)
        embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text=f"Page {page}/{pages} • {len(all_rows)} membres classés")
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.send_message(embed=embed)

    @niveau.command(name="setxp", description="Définir l'XP d'un membre (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def setxp(self, interaction: discord.Interaction, membre: discord.Member, xp: app_commands.Range[int, 0, 9999999]):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        level = calculate_level(xp)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                INSERT INTO levels (user_id,guild_id,xp,level,total_messages,last_message) VALUES (?,?,?,?,0,0)
                ON CONFLICT(user_id,guild_id) DO UPDATE SET xp=?, level=?
            """, (str(membre.id), str(interaction.guild.id), xp, level, xp, level))
            await db.commit()
        await interaction.response.send_message(embed=embed_success(f"✅ XP de **{membre}** défini à **{xp:,}** (Niveau **{level}**)."))

    @niveau.command(name="reset", description="Réinitialiser l'XP d'un membre (Admin)")
    @app_commands.default_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction, membre: discord.Member):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE levels SET xp=0, level=0, total_messages=0 WHERE user_id=? AND guild_id=?",
                             (str(membre.id), str(interaction.guild.id)))
            await db.commit()
        await interaction.response.send_message(embed=embed_success(f"✅ XP de **{membre}** réinitialisé."))


async def setup(bot):
    await bot.add_cog(Levels(bot))
