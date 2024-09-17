import discord

from discord.ui import View
from src.player import Player

class NowPlayingView(View):
    def __init__(self, author: discord.User, player: Player) -> None:
        super().__init__(timeout=None)
        self.player = player
        self.author = author 
        self.current_interaction = None
        self.message = None
        self.player.add_view(self, Player.ON_TRACK_CHANGED)

    async def delete(self):
        await self.message.delete()

    async def interaction_check(self, interaction: discord.Interaction[discord.Client]) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to control the player", ephemeral=True)
            return False
        self.current_interaction = interaction
        return True

    async def display(self, interaction: discord.Interaction):
        embed = self._get_embed()

        if not self.player.get_now_playing_track():
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(view=self, embed=embed)

        self.current_interaction = interaction
        self.message = await interaction.original_response()

    async def redraw(self, interaction: discord.Interaction = None):
        embed = self._get_embed()
        track = self.player.get_now_playing_track()

        if not track:
            if self.message:
                await self.message.edit(view=None, embed=embed)
            return

        if interaction:
            await interaction.response.edit_message(view=self, embed=embed)
        elif self.message:
            await self.message.edit(view=self, embed=embed)

    def _get_embed(self):
        track = self.player.get_now_playing_track()
        if not track:
            return discord.Embed(
                title="No track playing"
            )
        return discord.Embed(color=discord.Color.yellow()).add_field(
            name="Now playing:",
            value=f"{track.pretty_noalbum()}\n({track.album})"
        )

    @discord.ui.button(
        label="⏪",
        style=discord.ButtonStyle.primary
    )
    async def seek_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        # await self.redraw(interaction)
        await interaction.response.send_message("Not implemented yet :(")

    @discord.ui.button(
        label="⏯",
        style=discord.ButtonStyle.primary
    )
    async def pause_play(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.pause_play()
        await self.redraw(interaction)

    @discord.ui.button(
        label="⏩",
        style=discord.ButtonStyle.primary
    )
    async def seek_forward(self, interaction: discord.Interaction, button: discord.ui.Button):
        # await self.redraw(interaction)
        await interaction.response.send_message("Not implemented yet :(")

    @discord.ui.button(
        label="⏭",
        style=discord.ButtonStyle.primary
    )
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.player.skip()
        await self.redraw(interaction=interaction)
