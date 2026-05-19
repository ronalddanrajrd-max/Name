import discord
from discord import app_commands
from discord.ext import commands
import os
import secrets
import aiohttp
import datetime

from Database import db_execute, db_fetchone, db_fetchall
from Helpers import *


PRICE_DISPLAY = "0.05$ LTC"


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


async def whitelist_after_payment(interaction, purchase_id, script_name, tx_hash=None):
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
        title="✅ Payment Confirmed",
        description=(
            "Your payment has been detected and your access has been delivered.\n\n"
            f"**Script:** `{script_name}`\n"
            f"**Key:** `{key_code}`\n\n"
            f"```lua\n{loader}\n```"
        ),
        color=0x2ECC71
    )
    embed.set_footer(text="OkveHUB Secure Delivery")

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
        tx_hash = tx.get("hash")

        tx_time = tx.get("confirmed") or tx.get("received")
        if not tx_time:
            continue

        tx_timestamp = int(
            datetime.datetime.fromisoformat(
                tx_time.replace("Z", "+00:00")
            ).timestamp()
        )

        # Important : ignore les anciennes transactions
        if tx_timestamp < created_at:
            continue

        # Important : ignore les transactions déjà utilisées
        used = await db_fetchone(
            "SELECT * FROM purchases WHERE tx_hash=?",
            (tx_hash,)
        )

        if used:
            continue

        total_received = 0

        for out in tx.get("outputs", []):
            if address in out.get("addresses", []):
                total_received += int(out.get("value", 0))

        if total_received >= required_satoshis:
            return tx_hash

    return None


class PurchaseCheckView(discord.ui.View):
    def __init__(self, purchase_id: str):
        super().__init__(timeout=900)
        self.purchase_id = purchase_id

    @discord.ui.button(
        label="✅ I Paid",
        style=discord.ButtonStyle.success,
        custom_id="okvehub_purchase_check_secure"
    )
    async def check_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        purchase = await db_fetchone(
            "SELECT * FROM purchases WHERE purchase_id=?",
            (self.purchase_id,)
        )

        if not purchase:
            return await interaction.response.send_message(
                "❌ Purchase not found.",
                ephemeral=True
            )

        if purchase["status"] == "completed":
            return await interaction.response.send_message(
                "✅ This purchase is already completed.",
                ephemeral=True
            )

        if str(interaction.user.id) != purchase["user_id"]:
            return await interaction.response.send_message(
                "❌ This purchase is not yours.",
                ephemeral=True
            )

        pending_embed = discord.Embed(
            title="⏳ Checking Payment",
            description=(
                "OkveHUB is verifying your Litecoin payment.\n\n"
                "```txt\n"
                "Status  : Pending\n"
                "Network : Litecoin\n"
                "Gateway : OkveHUB Secure Checkout\n"
                "```"
            ),
            color=0xF1C40F
        )
        pending_embed.set_footer(text="OkveHUB Payment Gateway")

        await interaction.response.send_message(embed=pending_embed, ephemeral=True)

        test_mode = os.getenv("PURCHASE_TEST_MODE", "false").lower() == "true"

        if test_mode:
            tx_hash = "TEST-LTC-" + secrets.token_hex(6).upper()
        else:
            address = os.getenv("LTC_ADDRESS")
            amount = float(purchase["amount_ltc"])
            created_at = int(purchase["created_at"])

            if not address:
                return await interaction.followup.send(
                    "❌ LTC_ADDRESS is missing in Railway.",
                    ephemeral=True
                )

            tx_hash = await check_ltc_payment(address, amount, created_at)

        if not tx_hash:
            fail_embed = discord.Embed(
                title="⌛ Payment Still Pending",
                description=(
                    "Payment was not detected yet.\n\n"
                    "**Important:**\n"
                    "• Make sure you sent the exact amount\n"
                    "• Wait a few minutes for network confirmation\n"
                    "• Click **I Paid** again after sending\n\n"
                    "If the issue continues, open a ticket."
                ),
                color=0xE67E22
            )
            fail_embed.set_footer(text="OkveHUB Payment Gateway")

            return await interaction.followup.send(embed=fail_embed, ephemeral=True)

        embed = await whitelist_after_payment(
            interaction,
            purchase["purchase_id"],
            purchase["script_name"],
            tx_hash
        )

        log = discord.Embed(
            title="💰 Purchase Completed",
            color=0x2ECC71
        )
        log.add_field(
            name="User",
            value=f"{interaction.user.mention}\n`{interaction.user.id}`",
            inline=False
        )
        log.add_field(
            name="Method",
            value="LTC TEST" if test_mode else "LTC",
            inline=True
        )
        log.add_field(
            name="Price",
            value=PRICE_DISPLAY,
            inline=True
        )
        log.add_field(
            name="Required LTC Amount",
            value=str(purchase["amount_ltc"]),
            inline=True
        )
        log.add_field(
            name="TX Hash",
            value=f"`{tx_hash}`",
            inline=False
        )
        log.set_footer(text="OkveHUB Purchase Logs")

        await send_purchase_log(interaction.guild, log)

        await interaction.followup.send(embed=embed, ephemeral=True)


class PurchasePanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="💰 Buy with LTC",
        style=discord.ButtonStyle.success,
        custom_id="okvehub_purchase_ltc_secure"
    )
    async def buy_ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        address = os.getenv("LTC_ADDRESS")
        amount = float(os.getenv("LTC_AMOUNT", "0.00092"))
        script_name = os.getenv("PURCHASE_SCRIPT", "main")

        if not address:
            return await interaction.response.send_message(
                "❌ LTC_ADDRESS missing in Railway.",
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
            title="💰 Litecoin Checkout",
            description=(
                "Your secure payment session has been created.\n\n"
                f"**Purchase ID:** `{purchase_id}`\n"
                f"**Product:** `{script_name}`\n"
                f"**Price:** `{PRICE_DISPLAY}`\n\n"
                "**Send payment to:**\n"
                f"`{address}`\n\n"
                "After sending the payment, click **I Paid** below."
            ),
            color=0xF1C40F
        )

        embed.add_field(
            name="Status",
            value="🟡 Pending payment",
            inline=True
        )

        embed.add_field(
            name="Delivery",
            value="Automatic after confirmation",
            inline=True
        )

        embed.set_footer(text="OkveHUB Secure Checkout")

        await interaction.response.send_message(
            embed=embed,
            view=PurchaseCheckView(purchase_id),
            ephemeral=True
        )

    @discord.ui.button(
        label="🧠 Buy with BrainDrop",
        style=discord.ButtonStyle.primary,
        custom_id="okvehub_purchase_braindrop_secure"
    )
    async def buy_braindrop(self, interaction: discord.Interaction, button: discord.ui.Button):
        username = os.getenv("BRAINDROP_USERNAME")

        if not username:
            return await interaction.response.send_message(
                "❌ BRAINDROP_USERNAME missing in Railway.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="🧠 BrainDrop Payment",
            description=(
                "Please send the payment to the username below:\n\n"
                f"`{username}`\n\n"
                "If the payment does not work, open a ticket or contact staff."
            ),
            color=0x5865F2
        )

        embed.add_field(
            name="Price",
            value=PRICE_DISPLAY,
            inline=True
        )

        embed.set_footer(text="OkveHUB BrainDrop Checkout")

        await interaction.response.send_message(embed=embed, ephemeral=True)


class Purchase(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="purchase-panel",
        description="Créer le panel d'achat OkveHUB"
    )
    async def purchase_panel(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "admin"):
            return

        embed = discord.Embed(
            title="🛒 OkveHUB Store",
            description=(
                "**Purchase your OkveHUB access securely.**\n\n"
                f"**Price:** `{PRICE_DISPLAY}`\n\n"
                "Choose your payment method below.\n\n"
                "💰 **Litecoin** — automatic verification\n"
                "🧠 **BrainDrop** — manual payment username\n\n"
                "Once your payment is confirmed, the system will automatically deliver:\n"
                "• Your whitelist access\n"
                "• Your buyer role\n"
                "• Your private loader key"
            ),
            color=0x000000
        )

        embed.set_footer(text="OkveHUB Purchase System")

        await interaction.channel.send(embed=embed, view=PurchasePanel())

        await interaction.response.send_message(
            "✅ Purchase panel sent.",
            ephemeral=True
        )

    @app_commands.command(
        name="purchase-list",
        description="Voir les achats"
    )
    async def purchase_list(self, interaction: discord.Interaction):
        if not await check_permission(interaction, "staff"):
            return

        rows = await db_fetchall(
            "SELECT * FROM purchases ORDER BY created_at DESC LIMIT 15"
        )

        if not rows:
            return await interaction.response.send_message(
                "No purchases found.",
                ephemeral=True
            )

        lines = []

        for r in rows:
            status = "✅ completed" if r["status"] == "completed" else "🟡 pending"
            lines.append(
                f"`{r['purchase_id']}` — <@{r['user_id']}> — **{r['method']}** — {status}"
            )

        embed = discord.Embed(
            title="🛒 Purchase History",
            description="\n".join(lines),
            color=0x3498DB
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await init_purchase_db()
    await bot.add_cog(Purchase(bot))
