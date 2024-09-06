import discord
import logging

from src.db_manager import DatabaseManager
from dataclasses import dataclass

@dataclass
class TrackView:
    title: str
    artist: str
    album: str

class Bot:
    def __init__(self, db: DatabaseManager, intents=discord.Intents.default()) -> None:
        self.db = db
        self.client = discord.Client(intents=intents)
        self.tree = discord.app_commands.CommandTree(client=self.client)
        self.__logger = logging.getLogger("bot")

        self.client.event(self.on_ready)

        self._register_commands()

    async def on_ready(self):
        await self.tree.sync()
        self.__logger.info("Bot is ready")

    def _register_commands(self):
        @self.tree.command(
            name="search",
            description="Search for music in your local storage",
        )
        async def search_command(interaction: discord.Interaction, query: str):
            results = self.find_tracks_on_disk(query)
            if results:
                await interaction.response.send_message(f"Found {len(results)} tracks. First one is {results[0]}")
            else:
                await interaction.response.send_message("No tracks found")

    def find_tracks_on_disk(self, query: str):
        """
        Search the database for rows matching the query string. Returns the matching rows
        """
        qstr = "SELECT * FROM tracks_fts WHERE tracks_FTS MATCH ? || \"*\""
        self.db.cursor.execute(qstr, (query, ))
        results = [TrackView(*row) for row in self.db.cursor.fetchall()]
        return results
