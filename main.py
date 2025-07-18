import os
import discord
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Sellers' user IDs
SELLERS_IDS = [1387197480994603190, 1334348969987411978]

@bot.event
async def on_ready():
    print(f"🤖 Bot is online as {bot.user}")

@bot.command()
async def table(ctx):
    button = Button(label="Make Order", style=discord.ButtonStyle.success)

    async def button_callback(interaction):
        if interaction.user != ctx.author:
            await interaction.response.send_message("This button is not for you 😅", ephemeral=True)
            return

        # Notify sellers
        for seller_id in SELLERS_IDS:
            seller = bot.get_user(seller_id)
            if seller:
                try:
                    await seller.send(f"📢 Member **{interaction.user}** wants to place an order.")
                except Exception as e:
                    print(f"Error sending DM to {seller_id}: {e}")

        await interaction.response.send_message("✅ Your order request was sent to the sellers!", ephemeral=True)

    button.callback = button_callback
    view = View()
    view.add_item(button)

    msg = (
        "**🎬 Animation Order**\n\n"
        "The price and form of the order will be discussed with the seller.\n"
        "Click below to place an order:"
    )

    await ctx.send(msg, view=view)

bot.run(TOKEN)
