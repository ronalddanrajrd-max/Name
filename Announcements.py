import discord
from discord import app_commands
from discord.ext import commands
import os
from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *

class Announcements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ══════════ /vente-create ══════════
    @app_commands.command(name="vente-create", description="💳 Créer une commande")
    @app_commands.describe(acheteur="Acheteur", script="Script", prix="Prix €", paiement="Méthode", notes="Notes")
    @app_commands.choices(paiement=[
        app_commands.Choice(name="💳 PayPal", value="paypal"),
        app_commands.Choice(name="₿ Crypto", value="crypto"),
        app_commands.Choice(name="🏦 Virement", value="virement"),
        app_commands.Choice(name="🎁 Gratuit", value="gratuit"),
        app_commands.Choice(name="🔄 Autre", value="autre"),
    ])
    async def vente_create(self, interaction: discord.Interaction, acheteur: discord.Member, script: str, prix: float, paiement: str, notes: str = None):
        if not await check_permission(interaction, "staff"): return
        order_id = generate_id("OKV")
        await db_execute("INSERT INTO ventes (order_id, user_id, username, script_name, price, payment_method, notes) VALUES (?,?,?,?,?,?,?)",
            (order_id, str(acheteur.id), str(acheteur), script, prix, paiement, notes))
        embed = discord.Embed(title="💳 Nouvelle Commande", color=COLOR_VENTE, timestamp=discord.utils.utcnow())
        embed.add_field(name="🆔 Order ID", value=f"`{order_id}`", inline=True)
        embed.add_field(name="👤 Acheteur", value=acheteur.mention, inline=True)
        embed.add_field(name="📜 Script", value=script, inline=True)
        embed.add_field(name="💰 Prix", value=f"**{prix}€**", inline=True)
        embed.add_field(name="💳 Paiement", value=paiement.upper(), inline=True)
        embed.add_field(name="📊 Statut", value="⏳ En attente", inline=True)
        if notes: embed.add_field(name="📝 Notes", value=notes, inline=False)
        embed.set_footer(text=f"Créé par {interaction.user}")
        await interaction.response.send_message(embed=embed)
        await send_log(self.bot, "CHANNEL_LOGS", embed)
        try:
            notif = discord.Embed(title="💳 Ta commande OkveHUB a été enregistrée !", color=COLOR_VENTE, timestamp=discord.utils.utcnow())
            notif.add_field(name="🆔 Order ID", value=f"`{order_id}`", inline=True)
            notif.add_field(name="📜 Script", value=script, inline=True)
            notif.add_field(name="💰 Prix", value=f"**{prix}€**", inline=True)
            await acheteur.send(embed=notif)
        except: pass

    # ══════════ /vente-complete ══════════
    @app_commands.command(name="vente-complete", description="✅ Compléter une commande")
    @app_commands.describe(orderid="ID de la commande", whitelist="Ajouter à la whitelist ?")
    async def vente_complete(self, interaction: discord.Interaction, orderid: str, whitelist: bool = True):
        if not await check_permission(interaction, "staff"): return
        order = await db_fetchone("SELECT * FROM ventes WHERE order_id=?", (orderid.upper(),))
        if not order:
            return await interaction.response.send_message(embed=error_embed("Introuvable", f"Commande `{orderid}` non trouvée."), ephemeral=True)
        if order["status"] == "completed":
            return await interaction.response.send_message(embed=error_embed("Déjà complétée", "Cette commande est déjà complétée."), ephemeral=True)
        await db_execute("UPDATE ventes SET status='completed', staff_id=?, completed_at=strftime('%s','now') WHERE order_id=?",
            (str(interaction.user.id), orderid.upper()))
        if whitelist:
            await db_execute("""INSERT INTO whitelist (user_id, username, added_by, reason, script_access) VALUES (?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET script_access=excluded.script_access""",
                (order["user_id"], order["username"], str(interaction.user.id), f"Achat: {order['script_name']}", order["script_name"]))
            member = interaction.guild.get_member(int(order["user_id"]))
            if member:
                wl_role = os.getenv("ROLE_WHITELIST")
                if wl_role:
                    role = interaction.guild.get_role(int(wl_role))
                    if role: await member.add_roles(role)
                buy_role = os.getenv("ROLE_ACHETEUR")
                if buy_role:
                    role = interaction.guild.get_role(int(buy_role))
                    if role: await member.add_roles(role)
        embed = success_embed("Commande Complétée !", f"Commande `{orderid.upper()}` complétée.\n{'✅ **' + order['username'] + '** ajouté à la whitelist.' if whitelist else ''}")
        await interaction.response.send_message(embed=embed)
        try:
            user = await self.bot.fetch_user(int(order["user_id"]))
            notif = discord.Embed(title="✅ Ta commande OkveHUB est prête !", description="Ton script a été livré ! Merci pour ton achat.", color=COLOR_SUCCESS, timestamp=discord.utils.utcnow())
            notif.add_field(name="🆔 Order ID", value=f"`{orderid.upper()}`", inline=True)
            notif.add_field(name="📜 Script", value=order["script_name"], inline=True)
            await user.send(embed=notif)
        except: pass

    # ══════════ /vente-cancel ══════════
    @app_commands.command(name="vente-cancel", description="❌ Annuler une commande")
    @app_commands.describe(orderid="ID de la commande", raison="Raison")
    async def vente_cancel(self, interaction: discord.Interaction, orderid: str, raison: str):
        if not await check_permission(interaction, "staff"): return
        order = await db_fetchone("SELECT * FROM ventes WHERE order_id=?", (orderid.upper(),))
        if not order:
            return await interaction.response.send_message(embed=error_embed("Introuvable", f"Commande `{orderid}` non trouvée."), ephemeral=True)
        await db_execute("UPDATE ventes SET status='cancelled', staff_id=? WHERE order_id=?", (str(interaction.user.id), orderid.upper()))
        await interaction.response.send_message(embed=error_embed("Commande Annulée", f"Commande `{orderid.upper()}` annulée.\n**Raison:** {raison}"))
        try:
            user = await self.bot.fetch_user(int(order["user_id"]))
            await user.send(embed=discord.Embed(title="❌ Ta commande OkveHUB a été annulée", description=f"**Raison:** {raison}", color=COLOR_ERROR, timestamp=discord.utils.utcnow()))
        except: pass

    # ══════════ /vente-list ══════════
    @app_commands.command(name="vente-list", description="📋 Lister les commandes")
    @app_commands.choices(filtre=[
        app_commands.Choice(name="⏳ En attente", value="pending"),
        app_commands.Choice(name="✅ Complétées", value="completed"),
        app_commands.Choice(name="❌ Annulées", value="cancelled"),
        app_commands.Choice(name="📋 Toutes", value="all"),
    ])
    async def vente_list(self, interaction: discord.Interaction, filtre: str = "pending"):
        if not await check_permission(interaction, "staff"): return
        if filtre == "all":
            rows = await db_fetchall("SELECT * FROM ventes ORDER BY created_at DESC")
        else:
            rows = await db_fetchall("SELECT * FROM ventes WHERE status=? ORDER BY created_at DESC", (filtre,))
        if not rows:
            return await interaction.response.send_message(embed=info_embed("Aucune commande", "Aucune commande trouvée."), ephemeral=True)
        icons = {"pending": "⏳", "completed": "✅", "cancelled": "❌"}
        lines = [f"{icons.get(r['status'], '❓')} `{r['order_id']}` — **{r['script_name']}** — {r['price']}€ — <@{r['user_id']}>" for r in rows[:20]]
        embed = discord.Embed(title=f"💳 Commandes OkveHUB ({len(rows)})", description="\n".join(lines), color=COLOR_VENTE, timestamp=discord.utils.utcnow())
        if len(rows) > 20: embed.set_footer(text=f"20/{len(rows)} affichés")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ══════════ /vente-stats ══════════
    @app_commands.command(name="vente-stats", description="📊 Statistiques des ventes")
    async def vente_stats(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"): return
        all_rows = await db_fetchall("SELECT * FROM ventes")
        completed = [r for r in all_rows if r["status"] == "completed"]
        pending = [r for r in all_rows if r["status"] == "pending"]
        cancelled = [r for r in all_rows if r["status"] == "cancelled"]
        revenue = sum(r["price"] for r in completed)
        embed = discord.Embed(title="📊 Stats Ventes OkveHUB", color=COLOR_GOLD, timestamp=discord.utils.utcnow())
        embed.add_field(name="💰 Revenu Total", value=f"**{revenue:.2f}€**", inline=True)
        embed.add_field(name="✅ Complétées", value=f"`{len(completed)}`", inline=True)
        embed.add_field(name="⏳ En attente", value=f"`{len(pending)}`", inline=True)
        embed.add_field(name="❌ Annulées", value=f"`{len(cancelled)}`", inline=True)
        embed.add_field(name="📦 Total", value=f"`{len(all_rows)}`", inline=True)
        await interaction.response.send_message(embed=embed)

    # ══════════ /script-list ══════════
    @app_commands.command(name="script-list", description="📦 Voir tous les scripts disponibles")
    async def script_list(self, interaction: discord.Interaction):
        rows = await db_fetchall("SELECT * FROM scripts WHERE active=1 ORDER BY name ASC")
        if not rows:
            return await interaction.response.send_message(embed=info_embed("Catalogue vide", "Aucun script disponible."), ephemeral=True)
        embed = discord.Embed(title="📦 Catalogue OkveHUB", color=COLOR_MAIN, timestamp=discord.utils.utcnow())
        embed.description = "\n\n".join(f"**{r['name']}** — `{r['price']}€`\n└ {r['description'] or 'Aucune description'}" for r in rows)
        embed.set_footer(text=f"{len(rows)} script(s) disponible(s)")
        await interaction.response.send_message(embed=embed)

    # ══════════ /script-add ══════════
    @app_commands.command(name="script-add", description="➕ Ajouter un script au catalogue")
    @app_commands.describe(nom="Nom", prix="Prix €", description="Description", categorie="Catégorie")
    async def script_add(self, interaction: discord.Interaction, nom: str, prix: float, description: str = None, categorie: str = "general"):
        if not await check_permission(interaction, "admin"): return
        try:
            await db_execute("INSERT INTO scripts (name, description, price, category) VALUES (?,?,?,?)", (nom, description, prix, categorie))
            await interaction.response.send_message(embed=success_embed("Script Ajouté", f"**{nom}** ajouté à `{prix}€`."))
        except:
            await interaction.response.send_message(embed=error_embed("Erreur", "Un script avec ce nom existe déjà."), ephemeral=True)

    # ══════════ /script-remove ══════════
    @app_commands.command(name="script-remove", description="🗑️ Retirer un script du catalogue")
    @app_commands.describe(nom="Nom du script")
    async def script_remove(self, interaction: discord.Interaction, nom: str):
        if not await check_permission(interaction, "admin"): return
        await db_execute("UPDATE scripts SET active=0 WHERE name=?", (nom,))
        await interaction.response.send_message(embed=success_embed("Script Retiré", f"**{nom}** retiré du catalogue."))

async def setup(bot):
    await bot.add_cog(Announcements(bot))
