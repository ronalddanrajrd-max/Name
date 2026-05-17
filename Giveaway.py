import discord
from discord.ext import commands, tasks
import json, random
from Database import db_fetchall, db_execute
from Helpers import *

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        rows = await db_fetchall("SELECT * FROM giveaways WHERE ended=0 AND ends_at <= ?", (now_ts(),))
        for gw in rows:
            participants = json.loads(gw["participants"] or "[]")
            channel = self.bot.get_channel(int(gw["channel_id"]))
            if not channel:
                await db_execute("UPDATE giveaways SET ended=1 WHERE message_id=?", (gw["message_id"],))
                continue

            if not participants:
                embed = discord.Embed(title="🎉 Fin du Giveaway", description=f"**Lot:** {gw['prize']}\n\n😢 Personne n'a participé.", color=COLOR_ERROR, timestamp=discord.utils.utcnow())
                await channel.send(embed=embed)
            else:
                winners = random.sample(participants, min(gw["winners_count"], len(participants)))
                winners_text = " ".join(f"<@{w}>" for w in winners)
                embed = discord.Embed(title="🏆 Fin du Giveaway !", description=f"**Lot:** {gw['prize']}\n\n🎊 Félicitations {winners_text} !\n\n👥 **{len(participants)}** participant(s).", color=COLOR_GOLD, timestamp=discord.utils.utcnow())
                await channel.send(content=f"🎉 Félicitations {winners_text} !", embed=embed)

            await db_execute("UPDATE giveaways SET ended=1 WHERE message_id=?", (gw["message_id"],))

    @check_giveaways.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Giveaway(bot))
