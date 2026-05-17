import discord
from discord.ext import commands, tasks
import aiosqlite
import time
import os
import json
import math
import random
from utils.helpers import *
from utils.logger import send_log
from utils.database import DB_PATH


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_data: dict = {}     # {user_id: [timestamps]}
        self.check_reminders.start()
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_reminders.cancel()
        self.check_giveaways.cancel()

    # ══════════════════ MEMBER JOIN ══════════════════
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild

        # Vérif blacklist → kick immédiat
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT 1 FROM blacklist WHERE user_id=?", (str(member.id),))
            if await cur.fetchone():
                await member.kick(reason="Blacklisté OkveHUB")
                return

        # Rôle membre par défaut
        role_id = os.getenv("ROLE_MEMBRE")
        if role_id:
            role = guild.get_role(int(role_id))
            if role:
                await member.add_roles(role)

        # Canal de bienvenue
        ch_id = os.getenv("CHANNEL_BIENVENUE")
        if ch_id:
            channel = guild.get_channel(int(ch_id))
            if channel:
                async with aiosqlite.connect(DB_PATH) as db:
                    db.row_factory = aiosqlite.Row
                    cur = await db.execute("SELECT * FROM guild_config WHERE guild_id=?", (str(guild.id),))
                    cfg = await cur.fetchone()

                welcome_msg = (cfg["welcome_message"] if cfg else "Bienvenue {user} sur **OkveHUB** ! 🎉") \
                    .replace("{user}", member.mention) \
                    .replace("{username}", member.name) \
                    .replace("{server}", guild.name) \
                    .replace("{count}", str(guild.member_count))

                embed = discord.Embed(
                    title="👋 Nouveau membre !",
                    description=welcome_msg,
                    color=Colors.MAIN
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="📅 Compte créé", value=dt(member.created_at, "D"), inline=True)
                embed.add_field(name="👥 Membre N°", value=f"**{guild.member_count}**", inline=True)
                embed.set_footer(text="OkveHUB • Bienvenue !")
                embed.timestamp = discord.utils.utcnow()
                await channel.send(content=member.mention, embed=embed)

        # Log join/leave
        log_ch_id = os.getenv("CHANNEL_JOIN_LEAVE")
        if log_ch_id:
            log_ch = guild.get_channel(int(log_ch_id))
            if log_ch:
                embed = discord.Embed(title="📥 Membre rejoint", color=Colors.SUCCESS)
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="Utilisateur", value=f"{member} (`{member.id}`)")
                embed.add_field(name="Compte créé", value=dt(member.created_at), inline=True)
                embed.add_field(name="Membres total", value=f"**{guild.member_count}**", inline=True)
                embed.timestamp = discord.utils.utcnow()
                await log_ch.send(embed=embed)

        await send_log("JOIN", fields=[
            {"name": "Utilisateur", "value": f"{member} ({member.id})", "inline": True},
            {"name": "Compte créé", "value": dt(member.created_at), "inline": True},
        ])

    # ══════════════════ MEMBER LEAVE ══════════════════
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild

        log_ch_id = os.getenv("CHANNEL_JOIN_LEAVE")
        if log_ch_id:
            log_ch = guild.get_channel(int(log_ch_id))
            if log_ch:
                roles = ", ".join(r.mention for r in reversed(member.roles) if r.id != guild.id) or "Aucun"
                embed = discord.Embed(title="📤 Membre parti", color=Colors.ERROR)
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.add_field(name="Utilisateur", value=f"{member} (`{member.id}`)")
                embed.add_field(name="A rejoint", value=dt(member.joined_at) if member.joined_at else "?", inline=True)
                embed.add_field(name="Membres total", value=f"**{guild.member_count}**", inline=True)
                embed.add_field(name="Rôles", value=truncate(roles, 1024))
                embed.timestamp = discord.utils.utcnow()
                await log_ch.send(embed=embed)

        await send_log("LEAVE", fields=[{"name": "Utilisateur", "value": f"{member} ({member.id})"}])

    # ══════════════════ MESSAGE CREATE ══════════════════
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # AUTOMOD
        await self._automod(message)

        # XP
        await self._handle_xp(message)

    async def _automod(self, message: discord.Message):
        member = message.author
        guild = message.guild
        content = message.content

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM automod WHERE guild_id=?", (str(guild.id),))
            am = await cur.fetchone()

        if not am:
            return

        bypass = json.loads(am["bypass_roles"] or "[]")
        if any(str(r.id) in bypass for r in member.roles) or member.guild_permissions.manage_messages:
            return

        now = time.time()

        # Anti-spam
        if am["anti_spam"]:
            key = str(member.id)
            ts_list = self.spam_data.get(key, [])
            ts_list = [t for t in ts_list if now - t < am["spam_interval"]]
            ts_list.append(now)
            self.spam_data[key] = ts_list
            if len(ts_list) >= am["spam_threshold"]:
                await message.delete()
                warn = await message.channel.send(f"{member.mention} ⚠️ **Anti-Spam** ! Tu envoies trop de messages.")
                await asyncio.sleep(5)
                await warn.delete()
                self.spam_data[key] = []
                return

        # Anti-invite
        if am["anti_invite"]:
            import re
            if re.search(r"discord\.(gg|com/invite|app\.com/invite)/\S+", content, re.IGNORECASE):
                await message.delete()
                warn = await message.channel.send(f"{member.mention} ❌ Les invitations Discord sont interdites.")
                await asyncio.sleep(5)
                await warn.delete()
                return

        # Anti-caps
        if am["anti_caps"] and len(content) > 10:
            letters = [c for c in content if c.isalpha()]
            if letters:
                caps_pct = sum(1 for c in letters if c.isupper()) / len(letters) * 100
                if caps_pct >= am["caps_threshold"]:
                    await message.delete()
                    warn = await message.channel.send(f"{member.mention} ⚠️ Évite d'écrire en MAJUSCULES excessives.")
                    await asyncio.sleep(4)
                    await warn.delete()
                    return

        # Anti-mass mention
        if am["anti_mention"]:
            total_mentions = len(message.mentions) + len(message.role_mentions)
            if total_mentions >= am["max_mentions"]:
                await message.delete()
                warn = await message.channel.send(f"{member.mention} ❌ Trop de mentions !")
                await asyncio.sleep(5)
                await warn.delete()
                return

        # Mots bannis
        banned = json.loads(am["banned_words"] or "[]")
        if banned and any(w.lower() in content.lower() for w in banned):
            await message.delete()
            warn = await message.channel.send(f"{member.mention} ❌ Mot interdit détecté.")
            await asyncio.sleep(4)
            await warn.delete()

    async def _handle_xp(self, message: discord.Message):
        member = message.author
        guild = message.guild

        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM guild_config WHERE guild_id=?", (str(guild.id),))
            cfg = await cur.fetchone()
            cooldown = cfg["xp_cooldown"] if cfg else 60
            xp_rate = cfg["xp_rate"] if cfg else 15

            cur2 = await db.execute("SELECT * FROM levels WHERE user_id=? AND guild_id=?", (str(member.id), str(guild.id)))
            data = await cur2.fetchone()

            now_ms = int(time.time() * 1000)
            if data and (now_ms - data["last_message"]) < (cooldown * 1000):
                return

            xp_gain = random.randint(10, xp_rate + 10)
            old_level = data["level"] if data else 0

            await db.execute("""
                INSERT INTO levels (user_id, guild_id, xp, level, total_messages, last_message) VALUES (?,?,?,0,1,?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET
                  xp = xp + ?,
                  total_messages = total_messages + 1,
                  last_message = ?
            """, (str(member.id), str(guild.id), xp_gain, now_ms, xp_gain, now_ms))
            await db.commit()

            cur3 = await db.execute("SELECT xp FROM levels WHERE user_id=? AND guild_id=?", (str(member.id), str(guild.id)))
            new_xp = (await cur3.fetchone())[0]

        new_level = calculate_level(new_xp)
        if new_level > old_level:
            await db.execute = None  # déjà fermé
            async with aiosqlite.connect(DB_PATH) as db2:
                await db2.execute("UPDATE levels SET level=? WHERE user_id=? AND guild_id=?", (new_level, str(member.id), str(guild.id)))
                await db2.commit()

            lvl_ch_id = os.getenv("CHANNEL_NIVEAUX")
            ch = guild.get_channel(int(lvl_ch_id)) if lvl_ch_id else message.channel
            if ch:
                embed = discord.Embed(
                    title="🎉 Level Up !",
                    description=f"Félicitations {member.mention} ! Tu atteins le **niveau {new_level}** ! 🚀",
                    color=Colors.GOLD
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.timestamp = discord.utils.utcnow()
                await ch.send(embed=embed)

    # ══════════════════ MESSAGE DELETE LOG ══════════════════
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        log_ch_id = os.getenv("CHANNEL_LOGS")
        if not log_ch_id:
            return
        ch = message.guild.get_channel(int(log_ch_id))
        if not ch:
            return
        embed = discord.Embed(title="🗑️ Message supprimé", color=Colors.WARNING)
        embed.add_field(name="Auteur", value=f"{message.author} (`{message.author.id}`)", inline=True)
        embed.add_field(name="Salon", value=f"<#{message.channel.id}>", inline=True)
        embed.add_field(name="Contenu", value=truncate(message.content or "*Pas de texte*", 1020))
        if message.attachments:
            embed.add_field(name="Pièces jointes", value=f"{len(message.attachments)} fichier(s)")
        embed.timestamp = discord.utils.utcnow()
        await ch.send(embed=embed)

    # ══════════════════ MEMBER UPDATE (boost) ══════════════════
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if not before.premium_since and after.premium_since:
            guild = after.guild
            boost_ch_id = os.getenv("CHANNEL_BOOSTS")
            if boost_ch_id:
                ch = guild.get_channel(int(boost_ch_id))
                if ch:
                    embed = discord.Embed(
                        title="🚀 Nouveau Boost !",
                        description=f"{after.mention} vient de booster **{guild.name}** ! Merci ! 💜",
                        color=0xFF73FA
                    )
                    embed.set_thumbnail(url=after.display_avatar.url)
                    embed.add_field(name="Total boosts", value=f"**{guild.premium_subscription_count}**")
                    embed.timestamp = discord.utils.utcnow()
                    await ch.send(content=after.mention, embed=embed)

    # ══════════════════ TÂCHES PÉRIODIQUES ══════════════════
    @tasks.loop(seconds=30)
    async def check_reminders(self):
        now = int(time.time())
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM reminders WHERE sent=0 AND remind_at<=?", (now,))
            rows = await cur.fetchall()
            for r in rows:
                try:
                    ch = self.bot.get_channel(int(r["channel_id"]))
                    if ch:
                        await ch.send(f"<@{r['user_id']}> ⏰ **Rappel :** {r['content']}")
                    else:
                        user = await self.bot.fetch_user(int(r["user_id"]))
                        if user:
                            await user.send(f"⏰ **Rappel :** {r['content']}")
                    await db.execute("UPDATE reminders SET sent=1 WHERE id=?", (r["id"],))
                except Exception:
                    pass
            await db.commit()

    @tasks.loop(seconds=10)
    async def check_giveaways(self):
        now = int(time.time() * 1000)
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM giveaways WHERE ended=0 AND ends_at<=?", (now,))
            rows = await cur.fetchall()
            for gw in rows:
                try:
                    await db.execute("UPDATE giveaways SET ended=1 WHERE id=?", (gw["id"],))
                    await db.commit()

                    ch = self.bot.get_channel(int(gw["channel_id"]))
                    if not ch:
                        continue
                    msg = await ch.fetch_message(int(gw["message_id"]))
                    if not msg:
                        continue

                    entries = json.loads(gw["entries"] or "[]")
                    if not entries:
                        await msg.reply("🎉 Giveaway terminé — Aucun participant.")
                        continue

                    pool = entries.copy()
                    count = min(gw["winners_count"], len(pool))
                    winners = random.sample(pool, count)
                    mentions = " ".join(f"<@{w}>" for w in winners)
                    await msg.reply(f"🎉 Félicitations {mentions} ! Vous gagnez **{gw['prize']}** !")
                    await msg.edit(content=f"🎉 **GIVEAWAY TERMINÉ** | Gagnant(s) : {mentions}")
                except Exception as e:
                    print(f"Erreur giveaway: {e}")

    @check_reminders.before_loop
    @check_giveaways.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()


import asyncio

async def setup(bot):
    await bot.add_cog(Events(bot))
