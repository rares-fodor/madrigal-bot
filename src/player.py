import discord

from src.models import Track

@dataclass
class NowPlayingTrack:
    audio_source: discord.AudioSource
    track: Track

class Player:
    def __init__(self, voice_client: discord.VoiceClient) -> None:
        self.queue: List[NowPlayingTrack] = []
        self.now_playing: NowPlayingTrack = None
        self.voice_client: discord.VoiceClient = voice_client
        pass

    async def queue_track(self, path: str, track: Track):
        audio_source = discord.FFmpegPCMAudio(source=path, executable="ffmpeg")
        self.queue.append(NowPlayingTrack(audio_source, track))
        if not self.voice_client.is_playing() and not self.voice_client.is_paused():
            self._play_next()

    def _play_next(self, error = None):
        if error:
            self.__logger.error(f"Error after playback {error}")
        if self.queue:
            self.now_playing = self.queue.pop(0)
            self.voice_client.play(self.now_playing.audio_source, after=lambda e: self._play_next(e))
        else:
            self.now_playing = None
        self.__logger.info(f"Now playing: {self.now_playing.track}")

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

    def skip(self):
        pass
