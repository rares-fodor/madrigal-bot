import os
import mutagen
import logging

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict

from .db_manager import DatabaseManager

@dataclass
class Directory:
    id: Optional[int]
    path: str

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
        album = audio.get('album', ['Unknown Album'])[0]

        return TrackMetadata(title, artist, album, albumartist)


class FileScanner:
    def __init__(self, library_path: str, db: DatabaseManager) -> None:
        self.db = db
        self.library_path = library_path
        self.cached_dirs: Dict[str, Directory] = {}
        self.new_directories: List[Directory] = []
        self.new_tracks: List[Tuple[str, TrackMetadata]] = []
        self.updated_tracks: List[Tuple[str, TrackMetadata]] = []
        self.deleted_directories: List[Directory] = []
        self.__logger = logging.getLogger('scanner')

        # Initialize database schema
        self.db.executescript('db/schema.sql')
    
    def scan(self):
        self.db.cursor.execute("SELECT * FROM directories")
        cached_directories = [Directory(*row) for row in self.db.cursor.fetchall()]
        self.cached_dirs = {dir.path: dir for dir in cached_directories}

        for directory in self.cached_dirs.values():
            if not os.path.isdir(directory.path):
                self.deleted_directories.append(directory)
                continue

        library_directory = Directory(None, self.library_path)
        self._scan_directory(library_directory)
            
        self._delete_stale_tracks()
        self._delete_stale_directories()

        self._commit_directories()
        self._commit_tracks()

        # Commit transaction
        self.db.connection.commit()

    def _scan_directory(self, directory: Directory):
        self.__logger.info(f"Scanning directory {directory.path}")

        self.db.cursor.execute("SELECT * FROM tracks WHERE dir_id = ?", (directory.id,))
        cached_files = [Track(*row) for row in self.db.cursor.fetchall()]
        files_on_disk = os.listdir(directory.path)
        has_audio = False

        for filename in files_on_disk:
            filepath = os.path.join(directory.path, filename)

            if os.path.isdir(filepath):
                new_directory = Directory(None, filepath)
                if filepath in self.cached_dirs:
                    new_directory = self.cached_dirs[filepath]
                self._scan_directory(new_directory)

            if os.path.isfile(filepath):
                cached_track = next((t for t in cached_files if t.filename == filename), None)
                mtime = int(os.path.getmtime(filepath))
                if cached_track and cached_track.mtime == mtime:
                    # Cached and up-to-date
                    has_audio = True
                    continue

                self.__logger.info(f"Scanning track {filepath}")
                metadata = MetadataManager().get_metadata(filepath)
                if not metadata:
                    continue

                has_audio = True
                
                if cached_track:
                    # Track exists in db but has changed on disk
                    self.updated_tracks.append((filepath, metadata))
                else:
                    # Track is not in db
                    self.new_tracks.append((filepath, metadata))

        if has_audio:
            if directory.path not in self.cached_dirs:
                # New directory with audio
                self.new_directories.append(directory)
        elif directory.path in self.cached_dirs:
            # Directory no longer has audio in it, untrack
            self.deleted_directories.append(directory)

    
    def _delete_stale_directories(self):
        for dir in self.deleted_directories:
            self.__logger.info(f"Deleting directory {dir.path}")
            self.db.cursor.execute("DELETE FROM directories WHERE path = ?", (dir.path,))
        
        self.deleted_directories.clear()
    
    def _delete_stale_tracks(self):
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
            
            self.__logger.info(f"Deleting track {path}")
            deleted_tracks.append(os.path.basename(path))

        placeholders = ', '.join('?' for _ in deleted_tracks)
        query = f"DELETE FROM tracks WHERE filename IN ({placeholders})"
        self.db.cursor.execute(query, deleted_tracks)

    def _commit(self):
        self._commit_directories()
        self._commit_tracks()
        self.db.connection.commit()

    def _commit_directories(self):
        for directory in self.new_directories:
            self.__logger.info(f"Inserting directory {directory.path}")
            query = "INSERT INTO directories (path) VALUES (?)" 
            self.db.cursor.execute(query, (directory.path, ))
        self.new_directories.clear()

    def _commit_tracks(self):
        self.db.cursor.execute("SELECT dir_id, path FROM directories")
        directories = {path: dir_id for dir_id, path in self.db.cursor.fetchall()}

        for track in self.new_tracks:
            filename = os.path.basename(track[0])
            dir_path = os.path.dirname(track[0])
            mtime = int(os.path.getmtime(track[0]))

            artist_id = self._get_or_insert_artist(track[1].artist)
            albumartist_id = self._get_or_insert_artist(track[1].albumartist)
            album_id = self._get_or_insert_album(track[1].album, albumartist_id)
            dir_id = directories.get(dir_path)

            self.__logger.info(f"Inserting track {filename}")

            query = """
                INSERT INTO tracks (title, artist_id, album_id, dir_id, filename, mtime)
                    VALUES (?, ?, ?, ?, ?, ?)
            """
            self.db.cursor.execute(query, (track[1].title, artist_id, album_id, dir_id, filename, mtime))
        
        for track in self.updated_tracks:
            title = track[1].title
            artist_id = self._get_or_insert_artist(track[1].artist)
            albumartist_id = self._get_or_insert_artist(track[1].albumartist)
            album_id = self._get_or_insert_album(track[1].album, albumartist_id)
            mtime = int(os.path.getmtime(track[0]))
            filename = os.path.basename(track[0])

            self.__logger.info(f"Updating track {filename}")

            query = """
                UPDATE tracks
                SET title = ?, artist_id = ?, album_id = ?, mtime = ?
                WHERE filename = ?
            """
            self.db.cursor.execute(query, (title, artist_id, album_id, mtime, filename))
        
        self.new_tracks.clear()
        self.updated_tracks.clear()

    def _get_or_insert_artist(self, name: str):
        self.db.cursor.execute("SELECT artist_id FROM artists WHERE name = ?", (name, ))
        artist_id = self.db.cursor.fetchone()

        if artist_id is None:
            self.__logger.info(f"Inserting artist {name}")
            self.db.cursor.execute("INSERT INTO artists (name) VALUES (?)", (name, ))
            return self.db.cursor.lastrowid

        return artist_id[0]

    def _get_or_insert_album(self, name: str, artist_id: int):
        self.db.cursor.execute("SELECT album_id FROM albums WHERE name = ? AND artist_id = ?", (name, artist_id))
        album_id = self.db.cursor.fetchone()

        if album_id is None:
            self.__logger.info(f"Inserting album {name}")
            self.db.cursor.execute("INSERT INTO albums (name, artist_id) VALUES (?, ?)", (name, artist_id))
            return self.db.cursor.lastrowid

        return album_id[0]
