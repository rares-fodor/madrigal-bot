import discord
import logging
import asyncio

from dataclasses import dataclass
from typing import List

from src.models import Track

@dataclass
class NowPlayingTrack:
    audio_source: discord.AudioSource
    track: Track

class Player:
    def __init__(self, voice_client: discord.VoiceClient, client: discord.Client) -> None:
        self.queue: List[NowPlayingTrack] = []
        self.now_playing: NowPlayingTrack = None
        self.voice_client: discord.VoiceClient = voice_client
        self.client = client
        self.active_views = []
        self.__logger = logging.getLogger("player")

    def get_now_playing_track(self):
        if self.now_playing:
            return self.now_playing.track
        return None
    
    def add_view(self, view):
        self.active_views.insert(0, view)       # Enqueue to ensure first edited is most recent
        if len(self.active_views) > 3:          # Delete older /np messages
            view = self.active_views.pop()
            asyncio.create_task(view.delete())
    
    def get_queued_tracks(self):
        return [np.track for np in self.queue]

    async def _notify_views(self):
        for view in self.active_views:
            if view.current_interaction:
                await view.redraw()

    async def queue_track(self, path: str, track: Track):
        audio_source = discord.FFmpegPCMAudio(source=path, executable="ffmpeg")
        self.queue.append(NowPlayingTrack(audio_source, track))

        if not self.voice_client.is_playing():
            await self._play_next()

    async def _play_next(self, error=None):
        if error:
            self.__logger.error(f"Error after playback {error}")
        if self.queue:
            self.now_playing = self.queue.pop(0)
            after = lambda e: asyncio.run_coroutine_threadsafe(self._play_next(error=e), self.client.loop)
            self.voice_client.play(self.now_playing.audio_source, after=after)
            self.__logger.info(f"Now playing: {self.now_playing.track.pretty()}")
        else:
            self.now_playing = None
            self.__logger.info(f"Finished playback")
        
        await self._notify_views()

    def remove_track(self, index: int):
        pass

    def clear(self):
        """
        Clear playlist. If a track is playing it will not be removed or stopped
        """
        self.queue.clear()

    def stop(self):
        """
        Clear playlist and stop playback
        """
        self.clear()
        self.voice_client.stop()

    def pause_play(self):
        """
        Toggle pause play
        """
        if self.voice_client.is_paused():
            self.voice_client.resume()
        else:
            self.voice_client.pause()

    async def pause(self, interaction: discord.Interaction):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            await interaction.response.send_message("⏸ Paused playback")
        else:
            await interaction.response.send_message("Player is already paused :)")

    async def resume(self, interaction: discord.Interaction):
        if self.voice_client.is_paused():
            self.voice_client.resume()
            await interaction.response.send_message("▶ Resuming playback")
        else:
            await interaction.response.send_message("Player is not paused :)") 

    async def skip(self, interaction: discord.Interaction=None):
        if self.voice_client.is_playing():
            if interaction:
                await interaction.response.send_message(f"Skipping {self.now_playing.track.pretty()}", ephemeral=True)
            self.voice_client.pause()
            await self._play_next()