import pytest
import os
import random
from tests.util import DirManager, LibraryManager
from src.scanner import FileScanner
from src.scanner import Track
from src.scanner import Directory

@pytest.fixture(scope="function")
def get_library_manager():
    dm = DirManager(p_dir=0.3, depth=(2,4), branch=(1,4))
    lm = LibraryManager("./tests/tree", dm)
    return lm

@pytest.fixture(scope="function")
def get_scanner():
    if os.path.exists('./test_db.sqlite'):
        os.remove('./test_db.sqlite')

    return FileScanner(library_path="./tests/tree", db_path="./test_db.sqlite")


def test_directory_tracking(get_library_manager, get_scanner):
    """
    Scan after creating an empty directory tree. Scanner shouldn't track directories if there are no audio files in them
    """
    get_scanner.scan()

    assert get_scanner.db.count_rows("directories") == 0


def test_no_audio_files(get_library_manager, get_scanner):
    """
    Scan after creating non-audio files in the tree. Scanner shouldn't pick them up.
    """
    get_library_manager.dm.create_files(10)
    get_scanner.scan()

    assert get_scanner.db.count_rows("tracks") == 0

def test_detect_album(get_library_manager, get_scanner):
    """
    Create an album and test whether the scanner correctly detects and tracks it.
    """
    get_library_manager.make_album(8, "Thriller", "MJ", "MJ")
    get_scanner.scan()

    assert get_scanner.db.count_rows("tracks") == 8
    assert get_scanner.db.count_rows("directories") == get_library_manager.dm.get_non_empty_directories().__len__()

def test_correct_mtime(get_library_manager, get_scanner):
    """
    Verify whether inserted tracks have the correct mtime value set
    """
    get_library_manager.make_album(5, "AlbumTitle", "ArtistName", "ArtistName")
    get_scanner.scan()

    get_scanner.db.cursor.execute("SELECT * FROM tracks")
    cached_tracks = [Track(*row) for row in get_scanner.db.cursor.fetchall()]
    get_scanner.db.cursor.execute("SELECT * FROM directories")
    cached_dirs = [Directory(*row) for row in get_scanner.db.cursor.fetchall()]

    for track in cached_tracks:
        parent_dir = next((d for d in cached_dirs if d.id == track.dir_id), None)
        filepath = os.path.join(parent_dir.path, track.filename)
        assert int(os.path.getmtime(filepath)) == track.mtime

def test_placeholders(get_library_manager, get_scanner):
    """
    Create an album with no metadata and test whether the placeholders are set correctly
    """
    get_library_manager.make_album(5)
    get_scanner.scan()

    assert get_scanner.db.cursor.execute("SELECT * FROM albums WHERE name = ?", ("Unknown Album", )).fetchall().__len__() == 1
    assert get_scanner.db.cursor.execute("SELECT * FROM artists WHERE name = ?", ("Unknown Artist", )).fetchall().__len__() == 1
    assert get_scanner.db.count_rows("artists") == 1
    assert get_scanner.db.count_rows("albums") == 1

def test_rm_album(get_library_manager, get_scanner):
    """
    Create an album, scan, remove it, scan again. Tables tracks and directories should be clear
    """

    index = get_library_manager.make_album(10, "Awesome album", "Great singer", "Great singer")
    get_scanner.scan()

    get_library_manager.rm_album(index)
    get_scanner.scan()

    assert get_scanner.db.count_rows("tracks") == 0
    assert get_scanner.db.count_rows("directories") == 0

def test_move_to_empty(get_library_manager, get_scanner):
    """
    Create an album, scan, move it above the tracked dirs
    """
    index = get_library_manager.make_album(10, "Awesome album", "Great singer", "Great singer")
    get_scanner.scan()

    get_library_manager.move_album_to_empty(index)
    get_scanner.scan()

    assert get_scanner.db.count_rows("directories") == 1

def test_move_album_to_nonempty(get_library_manager, get_scanner):
    """
    Create an album, scan, move it, scan again
    """
    index = get_library_manager.make_album(10, "Awesome album", "Great singer", "Great singer")
    get_scanner.scan()

    get_library_manager.move_album_to_nonempty(index)
    get_scanner.scan()

    assert get_scanner.db.count_rows("directories") == 1

def test_rename_file(get_library_manager, get_scanner):
    index = get_library_manager.make_album(10, "Awesome album", "Great singer", "Great singer")
    get_scanner.scan()

    path = random.choice(get_library_manager.get_tracks_in_album(index))
    prev_filename = os.path.basename(path)
    p_dir = os.path.dirname(path)

    new_path = get_library_manager.rename_track(path)
    new_filename = os.path.basename(new_path)

    get_scanner.scan()

    get_scanner.db.cursor.execute("SELECT * FROM directories WHERE path = ?", (p_dir, ))
    directory = [Directory(*row) for row in get_scanner.db.cursor.fetchall()][0]

    get_scanner.db.cursor.execute("SELECT * FROM tracks WHERE filename = ? AND dir_id = ?", (prev_filename, directory.id))
    assert get_scanner.db.cursor.fetchall().__len__() == 0

    get_scanner.db.cursor.execute("SELECT * FROM tracks WHERE filename = ? AND dir_id = ?", (new_filename, directory.id))
    new_track = [Track(*row) for row in get_scanner.db.cursor.fetchall()][0]

    # New mtime is correct
    assert new_track.mtime == int(os.path.getmtime(new_path))
    # Doesn't create a new track
    assert get_scanner.db.count_rows("tracks") == 10