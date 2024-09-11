import discord
import logging
import atexit
import asyncio

from typing import Dict

from src.db_manager import DatabaseManager
from src.views.track_select import TrackResultsView
from src.models import Track
from src.player import Player

class Bot:
    def __init__(self, db: DatabaseManager, intents=discord.Intents.default()) -> None:
        self.db = db
        self.client = discord.Client(intents=intents)
        self.tree = discord.app_commands.CommandTree(client=self.client)
        self.players: Dict[discord.Guild, Player] = {}
        self.__logger = logging.getLogger("bot")

        self._register_commands()

        self.client.event(self.on_ready)

        atexit.register(self._sync_on_exit)

    async def on_ready(self):
        await self.tree.sync()
        self.__logger.info("Bot is ready")

    async def _on_exit(self):
        self.__logger.info("Program exitting, closing connection to discord...")
        await self.client.close()

    def _sync_on_exit(self):
        self.__logger.info("Running atexit cleanup")
        asyncio.run(self._on_exit())

    def _register_commands(self):
        @self.tree.command(
            name="play",
            description="Play a song from your local library",
        )
        async def play_command(interaction: discord.Interaction, query: str):
            await self._ensure_connection(interaction=interaction)

            results = self.find_tracks_on_disk(query)
            if len(results) == 1:
                await self._play_selected_track(results[0], interaction)
            elif len(results) > 1:
                view = TrackResultsView(results=results, on_select=self._play_selected_track)
                await view.display(interaction=interaction)
            else:
                await interaction.response.send_message("No results found :(")

        @self.tree.command(
            name="stop",
            description="Clear playlist and disconnect from voice channel"
        )
        async def stop_command(interaction: discord.Interaction):
            player = self.players.get(interaction.guild)
            player.stop()
            await interaction.response.send_message(f"Thanks for listening! 💤")
            await player.voice_client.disconnect()

        @self.tree.command(
            name="pause",
            description="Pause playback"
        )
        async def pause_command(interaction: discord.Interaction):
            player = self.players.get(interaction.guild)
            await player.pause(interaction)

    def find_tracks_on_disk(self, query: str):
        """
        Search the database for rows matching the query string. Returns the matching rows.
        """
        qstr = "SELECT rowid,* FROM tracks_fts WHERE tracks_FTS MATCH ? || \"*\""
        self.db.cursor.execute(qstr, (query, ))

        results = [Track(*row) for row in self.db.cursor.fetchall()]
        self.__logger.info(f"Found {len(results)} rows, best match {results[0] if results else 'None'}")

        return results

    async def _play_selected_track(self, track: Track, interaction: discord.Interaction):
        self.__logger.info(f"Selected {track}")

        path = self._get_path_for_track_id(track.id)
        self.__logger.info(f"Found path {path}")
        
        player = self.players.get(interaction.guild)
        if not player:
            self.__logger.error(f"Player instance not found for {interaction.guild}")
            return

        await interaction.response.send_message(f"🎶 Playing {track.artist} - {track.title} ({track.album}) 🎶")
        await player.queue_track(path, track)
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

    async def _ensure_connection(self, interaction: discord.Interaction) -> None:
        """
        Ensure that the bot is connected to a voice channel.
        If the bot is already connected it will continue using that connection.
        If not connected, attempts to connect to the issuer's voice channel if they are connected to one.
        """
        voice_client = discord.utils.get(self.client.voice_clients, guild=interaction.guild)
        user = interaction.guild.get_member(interaction.user.id)

        # If the bot is already connected to a voice channel, we don't need to reconnect
        if voice_client and voice_client.is_connected():
            return
        
        # If neither the bot, nor the issuer are connected to a voice channel we do not connect
        if not user or not user.voice:
            response_content = "You are not connected to a voice channel. Please connect to one before issuing this command."
            await interaction.response.send_message(content=response_content)
            return
        
        self.__logger.info(f"Bot connecting to {user.voice.channel} in guild {interaction.guild.name}")
        voice_client = await user.voice.channel.connect()
        self.players[interaction.guild] = Player(voice_client=voice_client)
