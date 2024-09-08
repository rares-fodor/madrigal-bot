import discord
import logging

from src.db_manager import DatabaseManager
from dataclasses import dataclass
from typing import List


@dataclass
class Track:
    title: str
    artist: str
    album: str


class TrackResultsView(discord.ui.View):
    def __init__(self, *, timeout: float | None = 180, results: List[Track]):
        super().__init__(timeout=timeout)
        self.results = results
        self.page = 0
        self.results_per_page = 5
        self.max_page = (len(results) - 1) // self.results_per_page

        self.set_buttons()

    def set_buttons(self):
        self.clear_items()

        start_index = self.page * self.results_per_page
        end_index = min(start_index + self.results_per_page, len(self.results))
        for i in range(start_index, end_index):
            self.add_item(TrackSelectionButton(i, self.results[i]))

        if self.max_page == 0:
            return

        if self.page > 0:
            self.add_item(PreviousPageButton())
        else:
            self.add_item(PreviousPageButton(disabled=True))
        if self.page < self.max_page:
            self.add_item(NextPageButton())
        else:
            self.add_item(NextPageButton(disabled=True))

    async def update_view(self, interaction: discord.Interaction):
        """
        Updates the embed and buttons when navigating pages.
        """
        embed = self.create_embed()
        self.set_buttons()
        await interaction.response.edit_message(embed=embed, view=self)

    def create_embed(self):
        """
        Create an embed with the current page of results.
        """
        embed = discord.Embed(
            title=f"Search Results (Page {self.page + 1}/{self.max_page + 1})",
            description="Select a track to play:",
            color=discord.Color.yellow(),
        )
        start_index = self.page * self.results_per_page
        end_index = min(start_index + self.results_per_page, len(self.results))
        for i, track in enumerate(self.results[start_index:end_index], start=1):
            embed.add_field(
                name=f"{start_index + i}. {track.title} - {track.artist}",
                value=f"{track.album}",
                inline=False,
            )
        return embed


class TrackSelectionButton(discord.ui.Button):
    def __init__(self, index: int, track: Track):
        super().__init__(label=f"{index + 1}", style=discord.ButtonStyle.primary, row=1)
        self.track = track

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Playing {self.track.title} - {self.track.artist} ({self.track.album})")


class PreviousPageButton(discord.ui.Button):
    def __init__(self, disabled = False):
        super().__init__(label="Previous", style=discord.ButtonStyle.secondary, disabled=disabled, row=2)

    async def callback(self, interaction: discord.Interaction):
        view: TrackResultsView = self.view
        view.page -= 1
        await view.update_view(interaction)


class NextPageButton(discord.ui.Button):
    def __init__(self, disabled = False):
        super().__init__(label="Next", style=discord.ButtonStyle.secondary, disabled=disabled, row=2)

    async def callback(self, interaction: discord.Interaction):
        view: TrackResultsView = self.view
        view.page += 1
        await view.update_view(interaction)


class Bot:
    def __init__(self, db: DatabaseManager, intents=discord.Intents.default()) -> None:
        self.db = db
        self.client = discord.Client(intents=intents)
        self.tree = discord.app_commands.CommandTree(client=self.client)
        self.__logger = logging.getLogger("bot")

        self.client.event(self.on_ready)

        self._register_commands()

    async def on_ready(self):
        await self.tree.sync()
        self.__logger.info("Bot is ready")

    def _register_commands(self):
        @self.tree.command(
            name="play",
            description="Play a song from your local library",
        )
        async def play_command(interaction: discord.Interaction, query: str):
            results = self.find_tracks_on_disk(query)
            if len(results) == 1:
                await interaction.response.send_message(f"Playing {results[0].title} by {results[0].artist}")
            elif len(results) > 1:
                view = TrackResultsView(results=results)
                embed = view.create_embed()
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await interaction.response.send_message("No results found :(")

    def find_tracks_on_disk(self, query: str):
        """
        Search the database for rows matching the query string. Returns the matching rows.
        """
        qstr = "SELECT * FROM tracks_fts WHERE tracks_FTS MATCH ? || \"*\""
        self.db.cursor.execute(qstr, (query, ))

        results = [Track(*row) for row in self.db.cursor.fetchall()]
        self.__logger.info(f"Found {len(results)} rows, best match {results[0] if results else 'None'}")

        return results
