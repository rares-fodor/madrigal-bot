import discord

from typing import List, Callable
from src.models import Track

TrackSelectionCallback = Callable[[Track, discord.Interaction], None]

class TrackResultsView(discord.ui.View):
    def __init__(self, results: List[Track], on_select: TrackSelectionCallback):
        super().__init__()
        self.on_select = on_select
        self.results = results
        self.page = 0
        self.results_per_page = 5
        self.max_page = (len(results) - 1) // self.results_per_page
        self.original_response: discord.InteractionMessage = None

        self.set_buttons()

    async def display(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self.create_embed(), view=self, ephemeral=True)
        self.original_response = await interaction.original_response()

    def set_buttons(self):
        self.clear_items()

        start_index = self.page * self.results_per_page
        end_index = min(start_index + self.results_per_page, len(self.results))
        for i in range(start_index, end_index):
            self.add_item(TrackSelectionButton(i, self.results[i], self.on_select))

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
    def __init__(self, index: int, track: Track, on_select: TrackSelectionCallback):
        super().__init__(label=f"{index + 1}", style=discord.ButtonStyle.primary, row=1)
        self.track = track
        self.on_select = on_select

    async def callback(self, interaction: discord.Interaction):
        await self.on_select(self.track, interaction)
        view: TrackResultsView = self.view
        await view.original_response.edit(view=None, embed=onSelectEmbed(self.track))


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


def onSelectEmbed(track: Track):
    embed = discord.Embed(
        color=discord.Color.yellow(),
        title="Track selected"
    )
    embed.add_field(
        name=f"{track.artist} - {track.title}",
        value=track.album
    )
    return embed