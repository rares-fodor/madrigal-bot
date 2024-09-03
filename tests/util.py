import os
import random
import shutil

from dataclasses import dataclass
from typing import List
from pydub import AudioSegment
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3


class DirTree(object):
    def __init__(self, path: str, children=None) -> None:
        self.path = path 
        self.files = []
        self.children = []
        
        if children is not None:
            for child in children:
                self.add_child(child)
    
    def add_child(self, node):
        assert isinstance(node, DirTree)
        self.children.append(node)

    def display(self):
        print(f"Path: {self.path}\nFiles:\n{'\n'.join(self.files)}Children:\n{'\n'.join(c.path for c in self.children)}\n")
        for child in self.children:
            child.display()

class DirManager:
    def __init__(self, p_dir=0.5, depth=(3, 6), branch=(2, 4)) -> None:
        self.p_dir = p_dir
        self.min_depth = depth[0]
        self.max_depth = depth[1]
        self.min_branch = branch[0]
        self.max_branch = branch[1]
        self.dir_counter = 0
        self.file_counter = 0
        self.tree: DirTree = None
        self.tree_ref_index = {}
    
    def _create_dir(self, parent: DirTree, depth):
        if depth > self.max_depth:
            return
        
        min_branch_guarantee = self.min_branch
        for _ in range(self.max_branch):
            if self.p_dir < random.random() and min_branch_guarantee == 0:
                continue
            elif min_branch_guarantee > 0:
                min_branch_guarantee -= 1

            dir_name = f"dir_{self.dir_counter}"
            dir_path = os.path.join(parent.path, dir_name)
            os.makedirs(dir_path, exist_ok=True)
            self.dir_counter += 1

            child = DirTree(path=dir_path)
            parent.add_child(child)
            self._create_dir(child, depth+1)

    def _create_ref_index(self):
        """
        Traverse the dir tree and map dir_names to their node reference.
        Should be called every time the tree is changed.
        """
        def recursion(node: DirTree):
            for c in node.children:
                if c.path not in self.tree_ref_index:
                    self.tree_ref_index[c.path] = c
                recursion(c)
        recursion(self.tree)        

    def _get_random_node(self) -> DirTree:
        return self.tree_ref_index[random.choice(list(self.tree_ref_index))]

    def create_tree(self, base_path: str):
        """
        Creates a directory tree starting at base_path. WARN: Will remove existing directores at path.
        """
        if os.path.isfile(base_path):
            raise ValueError(f"{base_path} is a file, cannot create directory tree here")
        try:
            os.makedirs(base_path)
        except OSError:
            shutil.rmtree(base_path)

        self.tree = DirTree(path=base_path)
        self._create_dir(self.tree, 0)
        self._create_ref_index()

    def create_files(self, count=0):
        """
        Selects count random nodes from the tree and creates a new file in each node.
        Returns a list of paths for the new files.
        """
        nodes = [self._get_random_node() for _ in range(count)]
        new_files = []

        for node in nodes:
            dir_path = node.path
            filename = f"file_{self.file_counter}"
            path = os.path.join(dir_path, filename)
            self.file_counter += 1
            with open(path, 'w') as _:
                pass
            new_files.append(path)
            node.files.append(path)

        return new_files
    
    def get_random_empty_dir(self):
        choice = self._get_random_node()
        while len(choice.files) > 0:
            choice = self._get_random_node()
        return choice.path

    def get_non_empty_directories(self):
        def non_empty_node(path: str):
            return len(self.tree_ref_index[path].files) > 0
        return list(filter(non_empty_node, list(self.tree_ref_index)))

@dataclass
class Artist:
    id: int
    name: str

@dataclass
class Album:
    id: int
    name: str
    artist_id: int

@dataclass
class Directory:
    id: int
    path: str

@dataclass
class Track:
    id: int
    title: str
    artist_id: int
    album_id: int
    albumartist_id: int
    dir_id: int

class LibraryManager:
    def __init__(self, base_path: str, dm: DirManager) -> None:
        dm.create_tree(base_path)
        self.dm = dm
        self.albums = []
        self.album_index = -1
        pass

    def make_album(self, count=0, title=None, artist=None, albumartist=None):
        paths = self.dm.create_files(count)
        for path in paths:
            audio = AudioSegment.silent(duration=1000)
            audio.export(path, format="mp3")

            audio = MP3(path, ID3=EasyID3)
            if title:
                audio['album'] = title
            if artist:
                audio['artist'] = artist
            if albumartist:
                audio['albumartist'] = albumartist
            audio.save()
        
        self.albums.append(paths)
        self.album_index += 1
        return self.album_index

    def move_album_to_empty(self, album_index):
        target_dir = self.dm.get_random_empty_dir()
        paths = self.albums[album_index]
        for path in paths:
            filename = os.path.basename(path)
            new_path = os.path.join(target_dir, filename)
            shutil.move(path, new_path)
    
    def move_album_to_nonempty(self, album_index):
        target_dir = self.dm.get_non_empty_directories()[0]
        paths = self.albums[album_index]
        for path in paths:
            filename = os.path.basename(path)
            new_path = os.path.join(target_dir, filename)
            shutil.move(path, new_path)
    
    def rm_album(self, album_index):
        paths = self.albums[album_index]
        self.albums.pop(album_index)
        self.album_index -= 1
        for path in paths:
            os.remove(path)
        
    def rename_track(self, path):
        """
        Rename the first track in album
        """
        new_path = f"{path}_renamed"
        shutil.move(path, new_path)
        return new_path

    def change_track_metadata(self, path):
        """
        Update the metadata of the first track in album.
        Returns the path to the updated track
        """
        audio = MP3(path, ID3=EasyID3)
        audio["title"] = "new_title"
        audio.save()
        return path

    def get_tracks_in_album(self, album_index):
        return self.albums[album_index]