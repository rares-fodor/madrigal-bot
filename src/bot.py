import discord
import logging
import atexit
import asyncio

from typing import Dict
from enum import Enum

from src.db_manager import DatabaseManager
from src.views.track_select import TrackResultsView
from src.views.now_playing import NowPlayingView
from src.views.queue import QueueView
from src.models import Track
from src.player import Player
from src.consts import NOT_PLAYING

def _parse_seconds(time: str):
    parts = time.split(':')

    if not all(part.isdigit() for part in parts):
        raise ValueError(f"Invalid format: {time}. Time must be either hh:mm:ss, mm:ss, or ss")
    
    # Reverse parts to align them from least significant (seconds) to most significant (hours)
    parts = list(map(int, parts[::-1]))

    scalars = (1, 60, 3600)
    return sum(part * scalar for part, scalar in zip(parts, scalars))

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
                await self._queue_selected_track(results[0], interaction)
            elif len(results) > 1:
                view = TrackResultsView(results=results, on_select=self._queue_selected_track)
                await view.display(interaction=interaction)
            else:
                await interaction.response.send_message("No results found :(", ephemeral=True)

        @self.tree.command(
            name="stop",
            description="Clear playlist and disconnect from voice channel"
        )
        async def stop_command(interaction: discord.Interaction):
            player = self.players.get(interaction.guild)
            if not player:
                await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
                return
            await player.disconnect(interaction)

        @self.tree.command(
            name="pause",
            description="Pause playback"
        )
        async def pause_command(interaction: discord.Interaction):
            player = self.players.get(interaction.guild)
            if not player:
                await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
                return
            await player.pause(interaction)

        @self.tree.command(
            name="resume",
            description="Resume playback"
        )
        async def resume_command(interaction: discord.Interaction):
            player = self.players.get(interaction.guild)
            if not player:
                await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
                return
            await player.resume(interaction)

        @self.tree.command(
            name="clear",
            description="Clear the playlist"
        )
        async def clear_command(interaction: discord.Interaction):
            player = self.players.get(interaction.guild)
            if not player:
                await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
                return
            await player.clear(interaction)

        @self.tree.command(
            name="skip",
            description="Skip the current track"
        )
        async def skip_command(interaction: discord.Interaction):
            player = self.players.get(interaction.guild)
            if not player:
                await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
                return
            await player.skip(interaction)

        @self.tree.command(
            name="np",
            description="Show the current playlist"
        )
        async def now_playing_command(interaction: discord.Interaction):
            player = self.players.get(interaction.guild)
            if not player:
                await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
                return
            view = NowPlayingView(author=interaction.user, player=player)
            await view.display(interaction)
        
        @self.tree.command(
            name="shazam",
            description="Get the current playing track as a direct message"
        )
        async def shazam_command(interaction: discord.Interaction):
            player = self.players.get(interaction.guild)
            if not player:
                await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
                return

            track = player.get_now_playing_track()
            if not track:
                await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
                return
            
            try:
                await interaction.user.send(track.pretty())
                await interaction.response.send_message(f"DM sent!", ephemeral=True)
            except discord.Forbidden:
                content = f"Couldn't send DM. Check your privacy settings! In the meantime: {track.pretty()}"
                await interaction.response.send_message(content=content, ephemeral=True)
        
        @self.tree.command(
            name="queue",
            description="Get a list view of the queued tracks"
        )
        async def queue_command(interaction: discord.Interaction):
            player = self.players.get(interaction.guild)
            if not player:
                await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
                return

            view = QueueView(player=player)
            await view.display(interaction)

        class SeekType(str, Enum):
            FORWARD = "forward"
            BACK = "back"
            EXACT = "exact"

        seek_type_choices = [
            discord.app_commands.Choice(name=choice.value, value=choice.value)
                for choice in SeekType
        ]
        @self.tree.command(
            name="seek",
            description="Forward/rewind or skip to a position in the current track"
        )
        @discord.app_commands.describe(
            seek_type="Choose how to seek through the track",
            time="The time to seek by (forward/back) or to (exact). Format: hh:mm:ss or mm:ss or sss"
        )
        @discord.app_commands.choices(seek_type=seek_type_choices)
        async def seek_command(interaction: discord.Interaction, seek_type: discord.app_commands.Choice[str], time: str):
            player = self.players.get(interaction.guild)
            if not player:
                await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
                return
            
            try:
                seek_to = _parse_seconds(time)
                relative = seek_type.value != SeekType.EXACT
                if seek_type.value == SeekType.BACK:
                    seek_to = -seek_to
                
                await player.seek(seek_to, relative, interaction)

            except ValueError as e:
                await interaction.response.send_message(str(e), ephemeral=True)
            
    def find_tracks_on_disk(self, query: str):
        """
        Search the database for rows matching the query string. Returns the matching rows.
        """
        qstr = "SELECT rowid,* FROM tracks_fts WHERE tracks_FTS MATCH ? || \"*\""
        self.db.cursor.execute(qstr, (query, ))

        results = [Track(*row) for row in self.db.cursor.fetchall()]
        self.__logger.info(f"Found {len(results)} rows, best match {results[0] if results else 'None'}")

        return results

    async def _queue_selected_track(self, track: Track, interaction: discord.Interaction):
        self.__logger.info(f"Selected {track}")

        path = self._get_path_for_track_id(track.id)
        self.__logger.info(f"Found path {path}")
        
        player = self.players.get(interaction.guild)
        if not player:
            self.__logger.error(f"Player instance not found for {interaction.guild}")
            return

        await interaction.response.send_message(f"🎶 Queued {track.artist} - {track.title} ({track.album}) 🎶", ephemeral=True)
        await player.queue_track(path, track)

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
        self.players[interaction.guild] = Player(client=self.client, voice_client=voice_client)
