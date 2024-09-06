import discord
import logging

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client=client)
logger = logging.getLogger("bot")

@client.event
async def on_ready():
    await tree.sync()
    logger.info("Bot is ready")
