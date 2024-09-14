from dataclasses import dataclass
from typing import Optional

@dataclass
class Track:
    id: int
    title: str
    artist: str
    album: str

    def pretty(self) -> str:
        return f"{self.title} - {self.artist} ({self.album})"
    def pretty_noalbum(self) -> str:
        return f"{self.title} - {self.artist}"

@dataclass
class DirectoryRow:
    id: Optional[int]
    path: str

@dataclass
class TrackRow:
    id: Optional[str]
    title: str
    artist_id: int
    album_id: int
    dir_id: int
    filename: int
    mtime: int

@dataclass
class TrackMetadata:
    title: str
    artist: str
    album: str
    albumartist: str