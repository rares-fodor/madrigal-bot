CREATE TABLE IF NOT EXISTS artists (
    artist_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS albums (
    album_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    artist_id INTEGER NOT NULL,
    UNIQUE(name, artist_id),
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
);

CREATE TABLE IF NOT EXISTS directories (
    dir_id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS tracks (
    track_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    artist_id INTEGER NOT NULL,
    album_id INTEGER NOT NULL,
    dir_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    mtime INTEGER NOT NULL,
    UNIQUE(dir_id, filename),
    FOREIGN KEY (artist_id) REFERENCES artists(artist_id),
    FOREIGN KEY (album_id) REFERENCES albums(album_id),
    FOREIGN KEY (dir_id) REFERENCES directories(dir_id)
);

CREATE VIEW IF NOT EXISTS tracks_view AS
SELECT
    t.track_id AS rowid,
    t.title,
    ar.name AS artist_name,
    al.name AS album_title
FROM
    tracks t
JOIN
    artists ar ON t.artist_id = ar.artist_id
JOIN
    albums al ON t.album_id = al.album_id;

CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5 (
    title,
    artist_name,
    album_title,
    content='tracks_view',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS tracks_fts_insert AFTER INSERT ON tracks
BEGIN
    INSERT INTO tracks_fts(rowid, title, artist_name, album_title)
    SELECT
        new.track_id,
        new.title,
        (SELECT name FROM artists WHERE artist_id = new.artist_id),
        (SELECT name FROM albums WHERE album_id = new.album_id);
END;

CREATE TRIGGER IF NOT EXISTS tracks_fts_update AFTER UPDATE ON tracks
BEGIN
    DELETE FROM tracks_fts WHERE rowid = old.track_id;
    INSERT INTO tracks_fts(rowid, title, artist_name, album_title)
    SELECT
        new.track_id,
        new.title,
        (SELECT name FROM artists WHERE artist_id = new.artist_id),
        (SELECT name FROM albums WHERE album_id = new.album_id);
END;

CREATE TRIGGER IF NOT EXISTS tracks_fts_delete AFTER DELETE ON tracks
BEGIN
    DELETE FROM tracks_fts WHERE rowid = old.track_id;
END;
