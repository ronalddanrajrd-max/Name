import discord
from discord import app_commands
from discord.ext import commands
import os
import secrets
import time
import aiohttp

from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *


def make_loader(key_code: str):
    base_url = os.getenv("BASE_URL", "https://name-production-e582.up.railway.app").rstrip("/")
    return f'''script_key="{key_code}";
loadstring(game:HttpGet("{base_url}/load?key=" .. script_key))()'''


async def init_purchase_db():
    await db_execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        purchase_id TEXT PRIMARY KEY,
        user_id TEXT,
        username TEXT,
        method TEXT,
        script_name TEXT DEFAULT 'main',
        amount_ltc REAL,
        status TEXT DEFAULT 'pending',
        created_at INTEGER DEFAULT (strftime('%s','now')),
        completed_at INTEGER,
        tx_hash TEXT
    )
    """)


async def give_buyer_roles(member: discord.Member):
    for role_id in [os.getenv("ROLE_WHITELIST"), os.getenv("ROLE_ACHETEUR")]:
        if role_id:
            role = member.guild.get_role(int(role_id))
            if role:
                try:
                    await member.add_roles(role)
                except:
                    pass


async def send_purchase_log(guild, embed):
    log_id = os.getenv("PURCHASE_LOG_CHANNEL")
    if not log_id or not guild:
        return

    channel = guild.get_channel(int(log_id))
    if channel:
        try:
            await channel.send(embed=embed)
        except:
            pass


async def whitelist_after_payment(interaction: discord.Interaction, purchase_id: str, script_name: str, tx_hash: str = None):
    key_code = "OKV-" + secrets.token_hex(8).upper()

    await db_execute(
        "INSERT INTO keys (key_code, script_name, used_by, used_at) VALUES (?, ?, ?, strftime('%s','now'))",
        (key_code, script_name, str(interaction.user.id))
    )

    await db_execute("""
    INSERT INTO whitelist (user_id, username, added_by, reason, script_access)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        username=excluded.username,
        reason=excluded.reason,
        script_access=excluded.script_access
    """, (
        str(interaction.user.id),
        str(interaction.user),
        "purchase_auto",
        f"Purchase {purchase_id}",
        script_name
    ))

    await db_execute(
        "UPDATE purchases SET status='completed', completed_at=strftime('%s','now'), tx_hash=? WHERE purchase_id=?",
        (tx_hash, purchase_id)
    )

    await give_buyer_roles(interaction.user)

    loader = make_loader(key_code)

    embed = discord.Embed(
        title="✅ Purchase Completed",
        description=(
            f"Merci pour ton achat !\n\n"
            f"**Script:** `{script_name}`\n"
            f"**Key:** `{key_code}`\n\n"
            f"```lua\n{loader}\n```"
        ),
        color=COLOR_SUCCESS
    )

    return embed


async def check_ltc_payment(address: str, required_amount: float, created_at: int):
    url = f"https://api.blockcypher.com/v1/ltc/main/addrs/{address}/full?limit=50"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=15) as resp:
            if resp.status != 200:
                return None

            data = await resp.json()

    required_satoshis = int(required_amount * 100_000_000)

    for tx in data.get("txs", []):
        confirmed = tx.get("confirmed")
        received = tx.get("received")
        tx_time = confirmed or received

        tx_hash = tx.get("hash")
        outputs = tx.get("outputs", [])

        total_received = 0

        for out in outputs:
            if address in out.get("addresses", []):
                total_received += int(out.get("value", 0))

        if total_received >= required_satoshis:
            return tx_hash

    return None


class PurchaseCheckView(discord.ui.View):
    def __init__(self, purchase_id: str):
        super().__init__(timeout=900)
        self.purchase_id = purchase_id

    @discord.ui.button(label="✅ I Paid", style=discord.ButtonStyle.success)
    async def check_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        purchase = await db_fetchone(
            "SELECT * FROM purchases WHERE purchase_id=?",
            (self.purchase_id,)
        )

        if not purchase:
            return await interaction.response.send_message("❌ Achat introuvable.", ephemeral=True)

        if purchase["status"] == "completed":
            return await interaction.response.send_message("✅ Cet achat est déjà validé.", ephemeral=True)

        if str(interaction.user.id) != purchase["user_id"]:
            return await interaction.response.send_message("❌ Ce paiement ne t'appartient pas.", ephemeral=True)

        address = os.getenv("LTC_ADDRESS")
        amount = float(purchase["amount_ltc"])
        created_at = int(purchase["created_at"])

        tx_hash = await check_ltc_payment(address, amount, created_at)

        if not tx_hash:
            return await interaction.response.send_message(
                "⏳ Paiement pas encore détecté. Attends quelques minutes puis reclique.",
                ephemeral=True
            )

        embed = await whitelist_after_payment(
            interaction,
            purchase["purchase_id"],
            purchase["script_name"],
            tx_hash
        )

        log = discord.Embed(title="💰 Purchase Completed", color=COLOR_SUCCESS)
        log.add_field(name="User", value=f"{interaction.user.mention}\n`{interaction.user.id}`", inline=False)
        log.add_field(name="Method", value="LTC", inline=True)
        log.add_field(name="Amount", value=str(amount), inline=True)
        log.add_field(name="TX", value=f"`{tx_hash}`", inline=False)
        await send_purchase_log(interaction.guild, log)

        await interaction.response.send_message(embed=embed, ephemeral=True)


class PurchasePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="💰 Buy with LTC", style=discord.ButtonStyle.success, custom_id="okvehub_buy_ltc")
    async def buy_ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        address = os.getenv("LTC_ADDRESS")
        amount = float(os.getenv("LTC_AMOUNT", "0.01"))
        script_name = os.getenv("PURCHASE_SCRIPT", "main")

        if not address:
            return await interaction.response.send_message(
                "❌ LTC_ADDRESS manquant dans Railway.",
                ephemeral=True
            )

        purchase_id = "PUR-" + secrets.token_hex(4).upper()

        await db_execute("""
        INSERT INTO purchases (purchase_id, user_id, username, method, script_name, amount_ltc)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            purchase_id,
            str(interaction.user.id),
            str(interaction.user),
            "ltc",
            script_name,
            amount
        ))

        embed = discord.Embed(
            title="💰 Litecoin Payment",
            description=(
                f"**Purchase ID:** `{purchase_id}`\n"
                f"**Amount:** `{amount} LTC`\n"
                f"**Address:**\n`{address}`\n\n"
                f"Après paiement, clique sur **I Paid**."
            ),
            color=0xF1C40F
        )

        await interaction.response.send_message(
            embed=embed,
            view=PurchaseCheckView(purchase_id),
            ephemeral=True
        )

    @discord.ui.button(label="🧠 Buy with BrainDrop", style=discord.ButtonStyle.primary, custom_id="okvehub_buy_braindrop")
    async def buy_braindrop(self, interaction: discord.Interaction, button: discord.ui.Button):
        username = os.getenv("BRAINDROP_USERNAME")

        if not username:
            return await interaction.response.send_message(
                "❌ BRAINDROP_USERNAME manquant dans Railway.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🧠 BrainDrop Payment",
            description=(
                f"Envoie le paiement à ce pseudo :\n"
                f"`{username}`\n\n"
                f"Si ça ne marche pas, ouvre un ticket ou contacte le staff."
            ),
            color=0x5865F2
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


class Purchase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="purchase-panel", description="Créer le panel d'achat OkveHUB")
    async def purchase_panel(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title="🛒 OkveHUB Purchase",
            description=(
                "Acheter un accès au script OkveHUB.\n\n"
                "Choisis ton moyen de paiement :\n"
                "💰 **LTC** — paiement automatique\n"
                "🧠 **BrainDrop** — paiement via pseudo"
            ),
            color=0x000000
        )

        await interaction.channel.send(embed=embed, view=PurchasePanel())
        await interaction.response.send_message("✅ Panel d'achat envoyé.", ephemeral=True)

    @app_commands.command(name="purchase-list", description="Voir les achats")
    async def purchase_list(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "staff"):
            return

        rows = await db_fetchall("SELECT * FROM purchases ORDER BY created_at DESC LIMIT 15")

        if not rows:
            return await interaction.response.send_message("Aucun achat.", ephemeral=True)

        lines = []
        for r in rows:
            lines.append(
                f"`{r['purchase_id']}` — <@{r['user_id']}> — **{r['method']}** — `{r['status']}`"
            )

        embed = discord.Embed(
            title="🛒 Purchases",
            description="\n".join(lines),
            color=0x3498DB
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="purchase-complete", description="Valider manuellement un achat")
    async def purchase_complete(self, interaction: discord.Interaction, purchase_id: str):
        if not await check_permission(interaction, "staff"):
            return

        purchase = await db_fetchone(
            "SELECT * FROM purchases WHERE purchase_id=?",
            (purchase_id,)
        )

        if not purchase:
            return await interaction.response.send_message("❌ Achat introuvable.", ephemeral=True)

        member = interaction.guild.get_member(int(purchase["user_id"]))
        if not member:
            return await interaction.response.send_message("❌ Membre introuvable.", ephemeral=True)

        interaction.user = member

        embed = await whitelist_after_payment(
            interaction,
            purchase["purchase_id"],
            purchase["script_name"],
            "manual"
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await init_purchase_db()
    await bot.add_cog(Purchase(bot))
