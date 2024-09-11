import discord

from src.models import Track

discord.opus.load_opus("libopus.so")

class Player:
    def __init__(self, voice_client: discord.VoiceClient) -> None:
        self.queue = []
        self.now_playing = None
        self.voice_client: discord.VoiceClient = voice_client
        pass

    async def queue_track(self, path: str, track: Track):
        audio_source = discord.FFmpegPCMAudio(source=path, executable="ffmpeg")
        self.voice_client.play(audio_source)

    def remove_track(self, index: int):
        pass

    def clear(self):
        pass

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
