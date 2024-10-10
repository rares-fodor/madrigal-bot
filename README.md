## Madrigal Music Bot
Madrigal is a Discord bot that allows you to play your local music files directly in voice channels.

### Features
* Play local music
* Control playback with commands like skip, seek, pause, resume, etc.
* Display currently playing track with a real-time progress bar

### Commands
* `/play <query>`: Searches your local library and either queues the result if there is one exact match, or displays a list if there are multiple. You can then select an option from the list to be queued.

* `/seek <seek_type> <time>`: Seek through the current track. You can move either forward or back from the current time or at an exact timestamp.
    
    ⚠️ If your input exceeds the track duration it will be skipped.
    * `<seek_type>` values: `forward`, `back`, `exact`
    * `<time>` uses `hh:mm:ss` format

* `/remove <index> [<end_index>]`: Remove tracks from the queue. If only `<index>` is provided, the track at that position will be removed. If both `<index>` and `<end_index>` are provided all tracks in the range (inclusive) will be removed.

* `/queue` : Displays a list view of the current queue. The message for this command will be updated automatically if any changes are made to the list (ex. skipping, removing tracks, etc.).

    ⚠️ If more than three `/queue` messages are requested the third most recent will be automatically deleted.

* `/np`: Shows the current playing track as well as a progress bar indicating the current playback progress. This command also offers a few control buttons that wrap the `/seek`, `/pause`, `/resume` and the `/skip` commands. For the `/seek` buttons the default `<time>` value is 10 seconds. The message for this command will be updated automatically if any changes are made to the current track (ex. seeking, skipping, pausing, etc.).

    ⚠️ If more than three `/np` messages are requested, the third most recent will be automatically deleted.

* `/pause`: Pauses playback

* `/resume`: Resumes playback

* `/stop`: Stops playback, removes `/np` and `/queue` messages and disconnects the bot from channel

* `/clear`: Removes tracks from the queue. If a track is playing it will not be removed.

* `/shazam`: Sends issuer a DM with the current playing track's artist and title.


### Installation guide

Clone this repository and open the directory.

To use madrigal you must first create a developer account with Discord [here](https://discord.com/developers). Then you must create an [application](https://discord.com/developers/applications).

Edit the `.env.example` file and add your token and the path to your music collection.

From this point you may decide to either run this bot natively or as a docker container.

#### Native installation

Install the program's dependencies with:
```
$: pip install -r requirements.txt
```

Rename the `.env.example` file:
```
$: cp .env.example .env
```

Run the bot with:
```
$: python -m src
```

#### Docker installation
##### TODO