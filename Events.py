import discord
from discord.ext import commands
import os
from Database import db_fetchone
from Helpers import *

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._spam = {}  # user_id -> [timestamps]

    # ══════════ ON READY ══════════
    @commands.Cog.listener()
    async def on_ready(self):
        import Logger
        Logger.success(f"Connecté en tant que {self.bot.user} ({self.bot.user.id})")
        Logger.info(f"Serveurs: {len(self.bot.guilds)}")
        await self.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="OkveHUB 🛡️"),
            status=discord.Status.online
        )

    # ══════════ ON MEMBER JOIN ══════════
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Vérifier blacklist
        bl = await db_fetchone("SELECT * FROM blacklist WHERE user_id=?", (str(member.id),))
        if bl:
            try:
                await member.send(embed=discord.Embed(
                    title="🚫 Accès refusé — OkveHUB",
                    description=f"Tu es blacklisté du serveur OkveHUB.\n**Raison:** {bl['reason']}",
                    color=COLOR_ERROR
                ))
            except: pass
            await member.kick(reason=f"Blacklisté: {bl['reason']}")
            return

        # Rôle non vérifié
        unverified_id = os.getenv("ROLE_UNVERIFIED")
        if unverified_id:
            role = member.guild.get_role(int(unverified_id))
            if role: await member.add_roles(role)

        # Remettre la whitelist si applicable
        wl = await db_fetchone("SELECT * FROM whitelist WHERE user_id=?", (str(member.id),))
        if wl and (not wl["expires_at"] or wl["expires_at"] > now_ts()):
            wl_role_id = os.getenv("ROLE_WHITELIST")
            if wl_role_id:
                role = member.guild.get_role(int(wl_role_id))
                if role: await member.add_roles(role)

        # Message de bienvenue
        ch_id = os.getenv("CHANNEL_BIENVENUE")
        if not ch_id: return
        channel = self.bot.get_channel(int(ch_id))
        if not channel: return

        embed = discord.Embed(
            title=f"👋 Bienvenue sur OkveHUB !",
            description=f"**{member.mention}** vient de rejoindre le serveur !\n\nLis les règles et profite de nos scripts 🚀",
            color=COLOR_MAIN,
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👥 Membre n°", value=f"`{member.guild.member_count}`", inline=True)
        embed.add_field(name="📅 Compte créé", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.set_footer(text="OkveHUB — Bienvenue !")
        await channel.send(embed=embed)

    # ══════════ ON MEMBER REMOVE ══════════
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        ch_id = os.getenv("CHANNEL_AUREVOIR")
        if not ch_id: return
        channel = self.bot.get_channel(int(ch_id))
        if not channel: return

        embed = discord.Embed(
            title="👋 Au revoir !",
            description=f"**{member}** a quitté le serveur.",
            color=COLOR_ERROR,
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👥 Membres restants", value=f"`{member.guild.member_count}`", inline=True)
        await channel.send(embed=embed)

    # ══════════ ANTI-SPAM ══════════
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return
        if is_staff(message.author): return  # Staff ignoré

        uid = str(message.author.id)
        import time
        now = time.time()

        if uid not in self._spam:
            self._spam[uid] = []

        self._spam[uid] = [t for t in self._spam[uid] if now - t < 5]
        self._spam[uid].append(now)

        if len(self._spam[uid]) >= 6:
            # Spam détecté
            try:
                await message.author.timeout(discord.utils.utcnow().__class__.fromtimestamp(now + 60) if False else None)
                from datetime import timedelta
                await message.author.timeout(timedelta(minutes=5), reason="Anti-spam automatique")
            except: pass

            try:
                await message.author.send(embed=discord.Embed(
                    title="🚫 Anti-Spam OkveHUB",
                    description="Tu as été temporairement mute (5 min) pour spam.",
                    color=COLOR_ERROR
                ))
            except: pass

            await message.channel.send(
                embed=discord.Embed(description=f"🚫 {message.author.mention} a été mute 5 min pour **spam**.", color=COLOR_WARNING),
                delete_after=5
            )
            self._spam[uid] = []

        await self.bot.process_commands(message)

    # ══════════ REACTION ROLES ══════════
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id: return
        from Database import db_fetchone as fetch
        entry = await fetch("SELECT role_id FROM reaction_roles WHERE message_id=? AND emoji=?",
            (str(payload.message_id), str(payload.emoji)))
        if not entry: return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return
        member = guild.get_member(payload.user_id)
        role = guild.get_role(int(entry["role_id"]))
        if member and role:
            await member.add_roles(role)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        from Database import db_fetchone as fetch
        entry = await fetch("SELECT role_id FROM reaction_roles WHERE message_id=? AND emoji=?",
            (str(payload.message_id), str(payload.emoji)))
        if not entry: return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return
        member = guild.get_member(payload.user_id)
        role = guild.get_role(int(entry["role_id"]))
        if member and role:
            await member.remove_roles(role)

    # ══════════ LOG COMMANDES ══════════
    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command):
        import Logger
        Logger.cmd(f"{interaction.user} | /{command.name} | #{interaction.channel}")

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        import Logger
        Logger.error(f"Erreur commande /{interaction.command.name if interaction.command else '?'}: {error}")
        try:
            await interaction.response.send_message(
                embed=discord.Embed(title="❌ Erreur", description=f"Une erreur est survenue: `{error}`", color=COLOR_ERROR),
                ephemeral=True
            )
        except: pass

async def setup(bot):
    await bot.add_cog(Events(bot))
