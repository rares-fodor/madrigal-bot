import os
import mutagen
from pydub import AudioSegment

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Create directory structure
dir1_path = os.path.join(ROOT_DIR, "dir1")
dir2_path = os.path.join(ROOT_DIR, "dir1", "dir2")
dir3_path = os.path.join(ROOT_DIR, "dir3")

os.makedirs(dir1_path, exist_ok=True)
os.makedirs(dir2_path, exist_ok=True)
os.makedirs(dir3_path, exist_ok=True)

def create_mock_audio(path, title=None, artist=None, album=None, albumartist=None):
    audio = AudioSegment.silent(duration=1000)
    audio.export(path, format="mp3")

    audio = mutagen.File(path, easy=True)
    if title:
        audio["title"] = title
    if artist:
        audio["artist"] = artist 
    if album:
        audio["album"] = album 
    if albumartist:
        audio["albumartist"] = albumartist
    
    audio.save()
    return path

track1 = create_mock_audio(os.path.join(dir1_path, "track1.mp3"), title="Macarena", artist="Macarena Band", album="Greatest Wedding Hits", albumartist="Various Artists")
track2 = create_mock_audio(os.path.join(dir1_path, "track2.mp3"), title="Cherry Cherry Lassie", artist="Two German Fellows", album="Greatest Wedding Hits")
track3 = create_mock_audio(os.path.join(dir1_path, "no_album.mp3"), title="Evisceration Plague", artist="Fill Call-ins")
track4 = create_mock_audio(os.path.join(dir3_path, "no_metadata.mp3"))
track5 = create_mock_audio(os.path.join(dir2_path, "only_artist.mp3"), artist="The nouns")

# track2 assert albumartist same as artist
# inserting track1 creates two rows in artist table
# track3 has album="Unknown Album"
# track4 has title="<filename>" artist="Unknown Artist" album="Uknown Album"
# similar track5