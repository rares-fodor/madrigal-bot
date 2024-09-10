import discord
import logging

from src.db_manager import DatabaseManager
from src.views.track_select import TrackResultsView
from src.models import Track
from src.player import Player

class Bot:
    def __init__(self, db: DatabaseManager, intents=discord.Intents.default()) -> None:
        self.db = db
        self.client = discord.Client(intents=intents)
        self.tree = discord.app_commands.CommandTree(client=self.client)
        self.players = Player(client=self.client)
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
            # Test whether issuer is connected to a voice channel or if the bot is already connected
            voice_client = discord.utils.get(self.client.voice_clients, guild=interaction.guild)
            user = interaction.guild.get_member(interaction.user.id)

            if not voice_client:
                if not user or not user.voice:
                    response_content = "You are not connected to a voice channel! Please issue this command after connecting to one"
                    await interaction.response.send_message(response_content)
                    return
                else:
                    await user.voice.channel.connect()

            # Go through with finding the track
            results = self.find_tracks_on_disk(query)
            if len(results) == 1:
                await self.play_selected_track(results[0], interaction)
            elif len(results) > 1:
                view = TrackResultsView(results=results, on_select=self.play_selected_track)
                await view.display(interaction=interaction)
            else:
                await interaction.response.send_message("No results found :(")

        @self.tree.command(
            name="stop",
            description="Clear playlist and disconnect from voice channel"
        )
        async def stop_command(interaction: discord.Interaction):
            # TODO, also clear the playlist
            voice_client = discord.utils.get(self.client.voice_clients, guild=interaction.guild)
            await voice_client.disconnect()
            await interaction.response.send_message(f"Cleared playlist, thanks for listening! 💤")

    def find_tracks_on_disk(self, query: str):
        """
        Search the database for rows matching the query string. Returns the matching rows.
        """
        qstr = "SELECT rowid,* FROM tracks_fts WHERE tracks_FTS MATCH ? || \"*\""
        self.db.cursor.execute(qstr, (query, ))

        results = [Track(*row) for row in self.db.cursor.fetchall()]
        self.__logger.info(f"Found {len(results)} rows, best match {results[0] if results else 'None'}")

        return results

    async def play_selected_track(self, track: Track, interaction: discord.Interaction):
        await interaction.response.send_message(f"🎶 Playing {track.artist} - {track.title} ({track.album}) 🎶")
        self.__logger.info(f"Selected {track}")

        path = self._get_path_for_track_id(track.id)
        self.__logger.info(f"Found path {path}")
        
        await self.player.queue_track(interaction, path, track)
        pass

    def _get_path_for_track_id(self, id: int):
        """
        Concatenate filename and path columns from tracks and directories and return the result for id
        """
        q_str = """
            SELECT directories.path || '/' || tracks.filename AS path
            FROM tracks
            JOIN directories
            ON tracks.dir_id = directories.dir_id
            WHERE tracks.track_id = ?
        """
        self.db.cursor.execute(q_str, (id, ))
        path = self.db.cursor.fetchone()
        if path:
            return path[0]
        return None