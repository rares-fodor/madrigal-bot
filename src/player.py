import discord
import logging
import asyncio
import mutagen

from dataclasses import dataclass

from src.models import Track
from src.consts import NOT_PLAYING
from src.utils import format_seconds


class ProgressAudioSource(discord.AudioSource):
    def __init__(self, source, seek_offset_sec: float = 0) -> None:
        super().__init__()
        self._source = source
        self.seek_offset = seek_offset_sec
        self.read_count = 0

    def read(self) -> bytes:
        data = self._source.read()
        if data:
            self.read_count += 1
        return data
    
    @property
    def progress(self) -> float:
        """Return the current time progress in the track"""
        return self.read_count * 0.02 + self.seek_offset

@dataclass
class NowPlayingTrack:
    audio_source: ProgressAudioSource
    track: Track
    path: str
    duration: float = 0

    def __post_init__(self):
        self.duration = _get_track_duration(self.path)

class ObservableQueue:
    def __init__(self, notify_callback) -> None:
        self._values = []
        self._notify_callback = notify_callback

    def _notify(self):
        self._notify_callback()

    def append(self, value):
        self._values.append(value) 
        self._notify()

    def insert(self, index, value):
        self._values.insert(index, value) 
        self._notify()

    def pop(self, index = 0):
        value = self._values.pop(index)
        self._notify()
        return value
    
    def clear(self):
        self._values.clear()
        self._notify()

    def get_values(self):
        return self._values

    def __len__(self):
        return len(self._values)
        
    def __getitem__(self, index):
        return self._values[index]
    
    def __iter__(self):
        return iter(self._values)
    
    def __repr__(self):
        return repr(self._values)

def _get_track_duration(path: str) -> float:
    """Return the track length in seconds"""
    audio: mutagen.FileType = mutagen.File(path)
    if audio:
        audio.info.pprint()
        return audio.info.length
    raise RuntimeError

class Player:
    ON_QUEUE_CHANGED = 'queue_changed'
    ON_TRACK_CHANGED = 'track_changed'

    def __init__(self, voice_client: discord.VoiceClient) -> None:
        self.queue = ObservableQueue(self._on_queue_changed)
        self.voice_client: discord.VoiceClient = voice_client
        self.active_views = {
            Player.ON_QUEUE_CHANGED: [],
            Player.ON_TRACK_CHANGED: []
        }
        self.current_track: NowPlayingTrack = None
        self.__logger = logging.getLogger("player")
        self.loop = asyncio.get_event_loop()

    def is_playing(self):
        return self.voice_client.is_playing()

    def get_now_playing_track(self):
        return self.current_track.track if self.current_track else None
    
    def get_current_track_progress(self):
        if self.current_track:
            return (self.current_track.audio_source.progress, self.current_track.duration)
        return None

    def get_queued_tracks(self):
        return [np.track for np in self.queue]

    def add_view(self, view, type: str):
        if type in self.active_views:
            views = self.active_views[type]
            views.insert(0, view)       # Enqueue to ensure first edited is most recent
            if len(views) > 3:          # Delete older /np messages
                view = views.pop()
                asyncio.create_task(view.delete())
        else:
            raise TypeError

    async def _remove_views(self):
        """ Delete tracked /np messages """
        for type in self.active_views:
            for view in self.active_views[type]:
                await view.delete()

    async def _notify_views(self, type: str):
        if type in self.active_views:
            for view in self.active_views[type]:
                await view.redraw()
        else:
            raise TypeError
    
    def _on_queue_changed(self):
        asyncio.create_task(self._notify_views(Player.ON_QUEUE_CHANGED))

    async def queue_track(self, path: str, track: Track):
        audio_source = ProgressAudioSource(discord.FFmpegPCMAudio(source=path, executable="ffmpeg"), seek_offset_sec=0)
        self.queue.append(NowPlayingTrack(audio_source, track, path))

        if not self.voice_client.is_playing():
            await self._play_next()

    async def _play_next(self, error=None):
        if error:
            self.__logger.error(f"Error after playback {error}")

        if self.queue:
            # Read first, then remove
            # Avoids a race condition where a redraw reads current track before it is set
            self.current_track = self.queue[0]
            self.queue.pop(0)

            after = lambda e: asyncio.run_coroutine_threadsafe(self._play_next(error=e), self.loop)
            self.voice_client.play(self.current_track.audio_source, after=after)
            self.__logger.info(f"Now playing: {self.current_track.track.pretty()} [{self.current_track.audio_source.progress}]")

        else:
            self.current_track = None
            self.__logger.info(f"Finished playback")

        # Call after setting self.current_track
        await self._notify_views(Player.ON_TRACK_CHANGED)

    async def remove_track(self, interaction: discord.Interaction, index: int, end_index: int = None):
        """
        Removes track at index, or if end_index is defined it removes tracks between given indices.
        """
        limit = len(self.queue) + 1     # Now playing track is not in the queue but we account for it
        if end_index is None:
            end_index = index

        if index < 0 or index > limit or end_index < 0 or end_index > limit:
            await interaction.response.send_message(f"Please use values 1 - {limit}", ephemeral=True)
            return

        if end_index < index:
            index, end_index = end_index, index

        titles = []
        need_skip = False
        for i in range(index, end_index + 1):
            if i == 0:
                need_skip = True
                titles.append(self.current_track.track.title)
                continue
            track: NowPlayingTrack = self.queue.pop()
            titles.append(track.track.title)
        
        if need_skip:
            # Requested skip of current track. Skip after removing rest to avoid race
            await self.skip()

        titles_removed = ", ".join(titles)
        await interaction.response.send_message(f"Removed [{titles_removed}] from the queue")

    async def clear(self, interaction: discord.Interaction=None):
        """
        Clear playlist. If a track is playing it will not be removed or stopped
        """
        if interaction:
            await interaction.response.send_message("Clearing playlist... 🌾")
        self.queue.clear()

    async def disconnect(self, interaction: discord.Interaction=None):
        """
        Clear playlist, stop playback, clean up messages
        """
        if interaction:
            await interaction.response.send_message(f"Thanks for listening! 💤")
        await self.clear()
        self.voice_client.stop()
        await self._remove_views()
        await self.voice_client.disconnect()

    def pause_play(self):
        """
        Toggle pause play
        """
        if self.voice_client.is_paused():
            self.voice_client.resume()
        else:
            self.voice_client.pause()


    async def pause(self, interaction: discord.Interaction=None):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            if interaction:
                await interaction.response.send_message("⏸ Paused playback")
        elif interaction:
            await interaction.response.send_message("Player is already paused :)")

    async def resume(self, interaction: discord.Interaction=None):
        if self.voice_client.is_paused():
            self.voice_client.resume()
            if interaction:
                await interaction.response.send_message("▶ Resuming playback")
        elif interaction:
            await interaction.response.send_message("Player is not paused :)") 

    async def skip(self, interaction: discord.Interaction=None):
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()
            if interaction:
                # Client is playing so we should have a track to print
                await interaction.response.send_message(f"Skipping {self.get_now_playing_track().pretty()}", ephemeral=True)
        elif interaction:
            await interaction.response.send_message(NOT_PLAYING, ephemeral=True)
    
    async def seek(self, seek_to: float, relative = False, interaction: discord.Interaction=None):
        """
        Seek to a specific time in the current track. If `relative` is True, seeking is relative
        to the current position
        """
        if self.current_track is None:
            self.__logger.warning("No track is playing")
            return

        progress = self.current_track.audio_source.progress

        if relative:
            seek_to = max(0, progress + seek_to)
        if seek_to > self.current_track.duration:
            if interaction:
                await interaction.response.send_message(f"Seek position exceeds track length, skipping")
                await self.skip()
                return

        ffmpeg_options = {
            "before_options": f"-ss {seek_to}"
        }

        new_source = ProgressAudioSource(discord.FFmpegPCMAudio(self.current_track.path, **ffmpeg_options), seek_offset_sec=seek_to)
        new_track = self.current_track
        new_track.audio_source = new_source
        self.queue.insert(0, new_track)

        # Skip to "seeked" track
        self.voice_client.stop()

        if interaction:
            await interaction.response.send_message(f"Skipped {self.current_track.track.pretty()} to {format_seconds(seek_to)}")

        await self._notify_views(Player.ON_TRACK_CHANGED)
