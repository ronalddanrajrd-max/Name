import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import time
import json
import random
import os
from utils.helpers import *
from utils.database import DB_PATH


class GiveawayEnterView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎉 Participer", style=discord.ButtonStyle.primary, custom_id="giveaway_enter")
    async def enter(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM giveaways WHERE message_id=?", (str(interaction.message.id),))
            gw = await cur.fetchone()

        if not gw:
            return await interaction.response.send_message(embed=embed_error("Giveaway introuvable."), ephemeral=True)
        if gw["ended"]:
            return await interaction.response.send_message(embed=embed_error("Ce giveaway est terminé."), ephemeral=True)
        if int(time.time() * 1000) > gw["ends_at"]:
            return await interaction.response.send_message(embed=embed_error("Ce giveaway est expiré."), ephemeral=True)

        entries = json.loads(gw["entries"] or "[]")
        uid = str(interaction.user.id)

        if uid in entries:
            # Retirer sa participation
            entries.remove(uid)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE giveaways SET entries=? WHERE message_id=?", (json.dumps(entries), str(interaction.message.id)))
                await db.commit()
            await interaction.response.send_message(embed=embed_info(f"Tu t'es **retiré** du giveaway. ({len(entries)} participants)"), ephemeral=True)
        else:
            entries.append(uid)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE giveaways SET entries=? WHERE message_id=?", (json.dumps(entries), str(interaction.message.id)))
                await db.commit()
            await interaction.response.send_message(embed=embed_success(f"🎉 Tu participes au giveaway ! ({len(entries)} participants)"), ephemeral=True)


class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.add_view(GiveawayEnterView())

    gw = app_commands.Group(name="giveaway", description="Système de giveaways")

    @gw.command(name="create", description="Créer un giveaway")
    @app_commands.describe(salon="Salon", duree="Durée (ex: 1h, 7d)", lot="Prix à gagner", gagnants="Nombre de gagnants")
    @app_commands.default_permissions(manage_events=True)
    async def gw_create(self, interaction: discord.Interaction,
                        salon: discord.TextChannel,
                        duree: str,
                        lot: str,
                        gagnants: app_commands.Range[int, 1, 20] = 1):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        secs = parse_duration(duree)
        if secs <= 0:
            return await interaction.response.send_message(embed=embed_error("Durée invalide. Ex: `1h`, `7d`"), ephemeral=True)

        ends_at = int(time.time() * 1000) + (secs * 1000)

        embed = discord.Embed(title="🎉 GIVEAWAY !", color=Colors.GOLD)
        embed.description = "\n".join([
            f"**🏆 Lot :** {lot}",
            f"**🎯 Gagnants :** {gagnants}",
            f"**⏰ Fin :** {dt(ends_at)} ({dt(ends_at, 'F')})",
            f"**👤 Organisé par :** {interaction.user.mention}",
            "",
            "Clique sur 🎉 pour participer !"
        ])
        embed.set_footer(text=f"OkveHUB Giveaway • {gagnants} gagnant(s)")
        import datetime
        embed.timestamp = datetime.datetime.fromtimestamp(ends_at / 1000, tz=datetime.timezone.utc)

        msg = await salon.send(embed=embed, view=GiveawayEnterView())

        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO giveaways (message_id,channel_id,guild_id,host_id,prize,winners_count,ends_at,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (str(msg.id), str(salon.id), str(interaction.guild.id), str(interaction.user.id), lot, gagnants, ends_at, int(time.time() * 1000))
            )
            await db.commit()

        await interaction.response.send_message(embed=embed_success(f"🎉 Giveaway créé dans {salon.mention} !\n**Lot :** {lot}\n**Durée :** {format_duration(secs)}"), ephemeral=True)

    @gw.command(name="end", description="Terminer un giveaway immédiatement")
    @app_commands.default_permissions(manage_events=True)
    async def gw_end(self, interaction: discord.Interaction, message_id: str):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM giveaways WHERE message_id=?", (message_id,))
            gw = await cur.fetchone()

        if not gw:
            return await interaction.response.send_message(embed=embed_error("Giveaway introuvable."), ephemeral=True)
        if gw["ended"]:
            return await interaction.response.send_message(embed=embed_warning("Giveaway déjà terminé."), ephemeral=True)

        entries = json.loads(gw["entries"] or "[]")
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE giveaways SET ended=1 WHERE message_id=?", (message_id,))
            await db.commit()

        ch = self.bot.get_channel(int(gw["channel_id"]))
        if ch:
            try:
                msg = await ch.fetch_message(int(message_id))
                if entries:
                    winners = random.sample(entries, min(gw["winners_count"], len(entries)))
                    mentions = " ".join(f"<@{w}>" for w in winners)
                    await msg.reply(f"🎉 Félicitations {mentions} ! Vous gagnez **{gw['prize']}** !")
                    await msg.edit(content=f"🎉 **GIVEAWAY TERMINÉ** | {mentions}", view=None)
                else:
                    await msg.reply("🎉 Giveaway terminé — Aucun participant.")
            except Exception:
                pass

        await interaction.response.send_message(embed=embed_success("✅ Giveaway terminé."), ephemeral=True)

    @gw.command(name="reroll", description="Retirer un nouveau gagnant")
    @app_commands.default_permissions(manage_events=True)
    async def gw_reroll(self, interaction: discord.Interaction, message_id: str):
        if not is_mod(interaction.user):
            return await interaction.response.send_message(embed=embed_error("Permission refusée."), ephemeral=True)

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM giveaways WHERE message_id=?", (message_id,))
            gw = await cur.fetchone()

        if not gw:
            return await interaction.response.send_message(embed=embed_error("Giveaway introuvable."), ephemeral=True)

        entries = json.loads(gw["entries"] or "[]")
        if not entries:
            return await interaction.response.send_message(embed=embed_error("Aucun participant."), ephemeral=True)

        winner = random.choice(entries)
        ch = self.bot.get_channel(int(gw["channel_id"]))
        if ch:
            try:
                msg = await ch.fetch_message(int(message_id))
                await msg.reply(f"🎉 Nouveau tirage ! <@{winner}> gagne **{gw['prize']}** !")
            except Exception:
                pass

        await interaction.response.send_message(embed=embed_success(f"✅ Nouveau gagnant : <@{winner}>"), ephemeral=True)

    @gw.command(name="list", description="Voir les giveaways actifs")
    async def gw_list(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM giveaways WHERE guild_id=? AND ended=0", (str(interaction.guild.id),))
            rows = await cur.fetchall()

        desc = "\n".join(f"• **{r['prize']}** — {dt(r['ends_at'])} — <#{r['channel_id']}>" for r in rows) or "*Aucun giveaway actif.*"
        embed = discord.Embed(title=f"🎉 Giveaways actifs ({len(rows)})", description=desc, color=Colors.GOLD)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Giveaway(bot))
