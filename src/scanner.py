import os
import mutagen
import logging

from dataclasses import dataclass
from db_manager import DatabaseManager
from typing import Optional, List, Tuple

logger = logging.getLogger('scanner')

@dataclass
class Directory:
    id: Optional[int]
    path: str
    mtime: str

@dataclass
class Track:
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

class MetadataManager:
    @staticmethod
    def get_metadata(path):
        filename = os.path.basename(path)

        audio = mutagen.File(path, easy=True)
        if audio is None:
            return None

        title = audio.get('title', [filename])[0]
        artist = audio.get('artist', ['Unknown Artist'])[0]
        albumartist = audio.get('albumartist', [artist])[0]
        album = audio.get('album', 'Unknown Album')[0]

        return TrackMetadata(title, artist, album, albumartist)


class FileScanner:
    def __init__(self, library_path: str) -> None:
        self.db = DatabaseManager('db/tracks.sqlite')
        self.library_path = library_path
        self.cached_dir_paths = []
        self.new_directories: List[Directory] = []
        self.new_tracks: List[Tuple[str, TrackMetadata]] = []
        self.updated_tracks: List[Tuple[str, TrackMetadata]] = []
        self.deleted_directories: List[Directory] = []

        # Initialize database schema
        self.db.executescript('db/schema.sql')
    
    def scan(self):
        self.db.cursor.execute("SELECT * FROM directories")
        cached_directories = [Directory(*row) for row in self.db.cursor.fetchall()]

        if not cached_directories:
            mtime = int(os.path.getmtime(self.library_path))
            library_directory = Directory(None, self.library_path, mtime)
            self.new_directories.append(library_directory)
            self.scan_directory(library_directory)
        else:
            self.cached_dir_paths = [d.path for d in cached_directories]
            for directory in cached_directories:
                if not os.path.isdir(directory.path):
                    self.deleted_directories.append(directory)
                    continue
                self.scan_directory(directory)
            
        self.delete_stale_tracks()
        self.delete_stale_directories()

        self.commit_directories()
        self.commit_tracks()

        # Commit transaction
        self.db.connection.commit()

    def scan_directory(self, directory: Directory):
        logger.info(f"Scanning directory {directory.path}")

        self.db.cursor.execute("SELECT * FROM tracks WHERE dir_id = ?", (directory.id,))
        cached_files = [Track(*row) for row in self.db.cursor.fetchall()]
        files_on_disk = os.listdir(directory.path)

        for filename in files_on_disk:
            filepath = os.path.join(directory.path, filename)
            mtime = int(os.path.getmtime(filepath))

            if os.path.isdir(filepath):
                if filepath not in self.cached_dir_paths:
                    new_directory = Directory(None, filepath, mtime)
                    self.new_directories.append(new_directory)
                    self.scan_directory(new_directory)

            if os.path.isfile(filepath):
                cached_track = next((t for t in cached_files if t.filename == filename), None)
                if cached_track and cached_track.mtime == mtime:
                    # Cached and up-to-date
                    continue

                logger.info(f"Scanning track {filepath}")
                metadata = MetadataManager().get_metadata(filepath)
                if not metadata:
                    continue
                
                if cached_track:
                    # Track exists in db but has changed on disk
                    self.updated_tracks.append((filepath, metadata))
                else:
                    # Track is not in db
                    self.new_tracks.append((filepath, metadata))
                
    
    def delete_stale_directories(self):
        for dir in self.deleted_directories:
            logger.info(f"Deleting directory {dir.path}")
            self.db.cursor.execute("DELETE FROM directories WHERE dir_id = ?", (dir.id,))
    
    def delete_stale_tracks(self):
        self.db.cursor.execute("""
            SELECT directories.path || '/' || tracks.filename AS path
            FROM tracks
            JOIN directories
            ON tracks.dir_id = directories.dir_id
        """)
        cached_track_paths = [path[0] for path in self.db.cursor.fetchall() if path is not None]
        deleted_tracks = []

        for path in cached_track_paths:
            if os.path.isfile(path):
                continue
            
            logger.info(f"Deleting track {path}")
            deleted_tracks.append(os.path.dirname(path))

        placeholders = ', '.join('?' for _ in deleted_tracks)
        query = f"DELETE FROM tracks WHERE filename IN ({placeholders})"
        self.db.cursor.execute(query, deleted_tracks)


    def commit(self):
        self.commit_directories()
        self.commit_tracks()
        self.db.connection.commit()

    def commit_directories(self):
        for directory in self.new_directories:
            logger.info(f"Inserting directory {directory.path}")
            query = "INSERT INTO directories (path, mtime) VALUES (?, ?)" 
            self.db.cursor.execute(query, (directory.path, directory.mtime))

    def commit_tracks(self):
        self.db.cursor.execute("SELECT dir_id, path FROM directories")
        directories = {path: dir_id for dir_id, path in self.db.cursor.fetchall()}

        for track in self.new_tracks:
            filename = os.path.basename(track[0])
            dir_path = os.path.dirname(track[0])
            mtime = int(os.path.getmtime(track[0]))

            artist_id = self.get_or_insert_artist(track[1].artist)
            albumartist_id = self.get_or_insert_artist(track[1].albumartist)
            album_id = self.get_or_insert_album(track[1].album, albumartist_id)
            dir_id = directories.get(dir_path)

            logger.info(f"Inserting track {filename}")

            query = """
                INSERT INTO tracks (title, artist_id, album_id, dir_id, filename, mtime)
                    VALUES (?, ?, ?, ?, ?, ?)
            """
            self.db.cursor.execute(query, (track[1].title, artist_id, album_id, dir_id, filename, mtime))
        
        for track in self.updated_tracks:
            title = track[1].title
            artist_id = self.get_or_insert_artist(track[1].artist)
            albumartist_id = self.get_or_insert_artist(track[1].albumartist)
            album_id = self.get_or_insert_album(track[1].album, albumartist_id)
            mtime = int(os.path.getmtime(track[0]))
            filename = os.path.basename(track[0])

            logger.info(f"Updating track {filename}")

            query = """
                UPDATE tracks
                SET title = ?, artist_id = ?, album_id = ?, mtime = ?
                WHERE filename = ?
            """
            self.db.cursor.execute(query, (title, artist_id, album_id, mtime, filename))

    def get_or_insert_artist(self, name: str):
        self.db.cursor.execute("SELECT artist_id FROM artists WHERE name = ?", (name, ))
        artist_id = self.db.cursor.fetchone()

        if artist_id is None:
            logger.info(f"Inserting artist {name}")
            self.db.cursor.execute("INSERT INTO artists (name) VALUES (?)", (name, ))
            return self.db.cursor.lastrowid

        return artist_id[0]

    def get_or_insert_album(self, name: str, artist_id: int):
        self.db.cursor.execute("SELECT album_id FROM albums WHERE name = ? AND artist_id = ?", (name, artist_id))
        album_id = self.db.cursor.fetchone()

        if album_id is None:
            logger.info(f"Inserting album {name}")
            self.db.cursor.execute("INSERT INTO albums (name, artist_id) VALUES (?, ?)", (name, artist_id))
            return self.db.cursor.lastrowid

        return album_id[0]
