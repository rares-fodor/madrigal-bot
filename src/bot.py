import os
import sqlite3
import mutagen
from dotenv import load_dotenv
from dataclasses import dataclass

load_dotenv()

connection = sqlite3.connect('tracks.sqlite')
connection.row_factory = sqlite3.Row
cursor = connection.cursor()

def initialize_db():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS artists (
            artist_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS albums (
            album_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            UNIQUE(name, artist_id),
            FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS directories (
            dir_id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            mtime INTEGER NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracks (
            track_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            artist_id INTEGER NOT NULL,
            album_id INTEGER NOT NULL,
            dir_id INTEGER NOT NULL,
            filename TEXT UNIQUE NOT NULL,
            mtime INTEGER NOT NULL,
            FOREIGN KEY (artist_id) REFERENCES artists(artist_id),
            FOREIGN KEY (album_id) REFERENCES albums(album_id),
            FOREIGN KEY (dir_id) REFERENCES directories(dir_id)
        )
    ''')

    connection.commit()

@dataclass
class TrackMetadata:
    title: str
    artist: str
    albumartist: str
    album: str

@dataclass
class Directory:
    dir_id: str
    dir_path: str
    mtime: int 


def get_track_metadata(path: str):
    audio_file = mutagen.File(path, easy=True)

    if audio_file is None:
        return None
    title = audio_file.get('title', [None])[0]
    artist = audio_file.get('artist', ["Unknown Artist"])[0]
    albumartist = audio_file.get('albumartist', artist)[0]
    album = audio_file.get('album', ["Unknown Album"])[0]

    return TrackMetadata(title, artist, albumartist, album)


def get_or_create_artist(name: str):
    cursor.execute("SELECT artist_id FROM artists WHERE name = ?", (name,))
    artist_id = cursor.fetchone()

    if artist_id is None:
        cursor.execute("INSERT INTO artists (name) VALUES (?)", (name,))
        return cursor.lastrowid
    return artist_id[0]


def get_or_create_album(name: str, artist_id: int):
    cursor.execute("SELECT album_id FROM albums WHERE name = ? AND artist_id = ?", (name, artist_id))
    album_id = cursor.fetchone()

    if album_id is None:
        cursor.execute("INSERT INTO albums (name, artist_id) VALUES (?, ?)", (name, artist_id))
        return cursor.lastrowid
    return album_id[0]


def replace_track(filename: str, metadata: TrackMetadata, mtime: int, dir_id: int):
    artist_id = get_or_create_artist(metadata.artist)
    albumartist_id = get_or_create_artist(metadata.albumartist)
    album_id = get_or_create_album(metadata.album, albumartist_id)

    cursor.execute("REPLACE INTO tracks (title, artist_id, album_id, dir_id, filename, mtime) VALUES (?, ?, ?, ?, ?, ?)",
                (metadata.title, artist_id, album_id, dir_id, filename, mtime))
    connection.commit()


def remove_stale_tracks(dir_id: int, dir_path: str):
    # Remove tracks that are in db but not on disk
    files_in_dir = [file for file in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, file))]
    tracks_in_dir = []
    
    for file in files_in_dir:
        metadata = get_track_metadata(os.path.join(dir_path, file))
    
        if metadata:
            tracks_in_dir.append(file)
    
    placeholders = ', '.join('?' for _ in tracks_in_dir)
    query = f"DELETE FROM tracks WHERE dir_id = ? AND filename NOT IN ({placeholders})"
    cursor.execute(query, (dir_id, *tracks_in_dir))
    connection.commit()


class Scanner():
    def __init__(self, root_dir: str) -> None:
        cursor.execute("SELECT * FROM directories")
        cached_directories = [Directory(dir_id=id, dir_path=path, mtime=mtime) for (id, path, mtime) in cursor.fetchall()]

        if not cached_directories:
            # Insert the root dir in the db
            cursor.execute("INSERT INTO directories (path, mtime) VALUES (?, ?)", (root_dir, os.path.getmtime(root_dir)))
            connection.commit()
            cached_directories = [Directory(cursor.lastrowid, root_dir, 0)]

        self.cached_directories = cached_directories
        self.known_directories = [dir.dir_path for dir in cached_directories]

        for d in self.cached_directories:
            print(f"SCANNING {d.dir_path}")
            self.scan_directory(d.dir_id, d.dir_path)

            # Update the directory's mtime in the database
            cursor.execute("UPDATE directories SET mtime = ? WHERE dir_id = ?", (int(os.path.getmtime(d.dir_path)), d.dir_id))
            connection.commit()

    def scan_directory(self, dir_id: int, dir_path: str):
        # Fetch all tracks in directory
        cursor.execute("SELECT * FROM tracks WHERE dir_id = ?", (dir_id,))
        cached_tracks = [dict(row) for row in cursor.fetchall()]

        for filename in os.listdir(dir_path):
            filepath = os.path.join(dir_path, filename)
            mtime = int(os.path.getmtime(filepath))

            if os.path.isdir(filepath):
                self.process_subdirectory(filepath, mtime)
            elif os.path.isfile(filepath):
                self.process_file(filename, filepath, mtime, dir_id, cached_tracks)

        remove_stale_tracks(dir_id, dir_path)

    def process_file(self, filename: str, filepath: str, mtime: int, parent_id: int, cached_tracks: list):
        print(f"SCANNING {filename}")
        cached_track = next((track for track in cached_tracks if track['filename'] == filename), None)

        if cached_track and cached_track['mtime'] == mtime:
            print(f"Skipping '{filename}' as it is cached and up-to-date")
            return

        metadata = get_track_metadata(filepath)
        if metadata:
            replace_track(filename, metadata, mtime, parent_id)
        else:
            print(f"Skipping '{filename}' as it is not a valid audio file")

    def process_subdirectory(self, path: str, mtime: int):
        if path not in self.known_directories:
            # Cache new subdirectory...
            cursor.execute("INSERT INTO directories (path, mtime) VALUES (?, ?)", (path, mtime))
            connection.commit()

            # Add it to the scan queue
            self.cached_directories.append(Directory(dir_id=cursor.lastrowid, dir_path=path, mtime=0))


initialize_db()
scanner = Scanner(os.getenv('LIBRARY_PATH'))
