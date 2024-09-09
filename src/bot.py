import discord
import logging

from src.db_manager import DatabaseManager
from src.views.track_select import TrackResultsView
from src.models import Track

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
            name="play",
            description="Play a song from your local library",
        )
        async def play_command(interaction: discord.Interaction, query: str):
            results = self.find_tracks_on_disk(query)
            if len(results) == 1:
                await self.play_selected_track(results[0], interaction)
            elif len(results) > 1:
                view = TrackResultsView(results=results, on_select=self.play_selected_track)
                await view.display(interaction=interaction)
            else:
                await interaction.response.send_message("No results found :(")

    def find_tracks_on_disk(self, query: str):
        """
        Search the database for rows matching the query string. Returns the matching rows.
        """
        qstr = "SELECT * FROM tracks_fts WHERE tracks_FTS MATCH ? || \"*\""
        self.db.cursor.execute(qstr, (query, ))

        results = [Track(*row) for row in self.db.cursor.fetchall()]
        self.__logger.info(f"Found {len(results)} rows, best match {results[0] if results else 'None'}")

        return results

    async def play_selected_track(self, track: Track, interaction: discord.Interaction):
        await interaction.response.send_message(f"Playing {track.artist} - {track.title} ({track.album})")
        self.__logger.info(f"Selected {track}")
        pass