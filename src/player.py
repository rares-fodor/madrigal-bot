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

    def pause(self):
        pass

    def resume(self):
        pass

    def skip(self):
        pass
