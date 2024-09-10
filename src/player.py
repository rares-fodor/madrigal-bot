import discord

from src.models import Track

discord.opus.load_opus("libopus.so")

class Player:
    def __init__(self, client: discord.Client) -> None:
        self.queue = []
        self.now_playing = None
        self.client = client
        pass

    async def queue_track(self, interaction: discord.Interaction, path: str, track: Track):
        audio_source = discord.FFmpegPCMAudio(source=path, executable="ffmpeg")
        voice_client = discord.utils.get(self.client.voice_clients, guild=interaction.guild)
        voice_client.play(audio_source)

    def remove_track(self, index: int):
        pass

    def clear(self):
        pass

    def pause(self):
        pass

    def resume(self):
        pass

    def skip(self):
        pass
