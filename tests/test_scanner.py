import pytest
import os
from tests.util import DirManager, LibraryManager
from src.scanner import FileScanner

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

def test_move_to_empty(get_library_manager, get_scanner):
    """
    Create an album, scan, move it above the tracked dirs
    """
    index = get_library_manager.make_album(10, "Awesome album", "Great singer", "Great singer")
    get_scanner.scan()

    get_library_manager.move_album_to_empty(index)
    get_scanner.scan()

    # Moving the album tracks from where they were assigned into a single directory
    # Previous directories should be untracked
    # Tracks should be updated with their new paths
    assert get_scanner.db.count_rows("directories") == 1

def test_move_album_to_nonempty(get_library_manager, get_scanner):
    """
    Create an album, scan, move it, scan again
    """
    index = get_library_manager.make_album(10, "Awesome album", "Great singer", "Great singer")
    get_scanner.scan()

    get_library_manager.move_album_to_nonempty(index)
    get_scanner.scan()

    # Moving the album tracks from where they were assigned into a single directory
    # Previous directories should be untracked
    # Tracks should be updated with their new paths
    assert get_scanner.db.count_rows("directories") == 1