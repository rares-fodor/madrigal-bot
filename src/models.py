from dataclasses import dataclass
from typing import Optional

@dataclass
class Track:
    title: str
    artist: str
    album: str

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