import discord

from src.player import Player

class QueueView(discord.ui.View):
    def __init__(self, player: Player):
        super().__init__(timeout=None)
        self.player = player
        self.current_interaction = None
        self.message = None
        self.player.add_view(self, Player.ON_QUEUE_CHANGED)

    async def delete(self):
        await self.message.delete()

    async def display(self, interaction: discord.Interaction):
        embed = self._get_embed()
        await interaction.response.send_message(view=self, embed=embed)
        self.current_interaction = interaction
        self.message = await interaction.original_response()

    async def redraw(self, interaction: discord.Interaction=None):
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
        queue = self.player.get_queued_tracks()

        title = "" if track else "No track playing"
        embed = discord.Embed(
            color = discord.Color.yellow(),
            title=title
        )

        if track:
            embed.add_field(
                name=f"Now playing:",
                value=f"1. {track.pretty_noalbum()}\n({track.album})",
                inline=False
            )
        if len(queue) >= 1:
            later_tracks = []   # List of strings with multiple tracks each, used in field
            track_count = 0
            current_chunk = ""
            
            for i, track in enumerate(queue, 2):
                track_info = f"{i}. {track.pretty_noalbum()} ({track.album})\n"
                
                # Account for very large track metadata
                if track_count >= 5 or len(current_chunk) + len(track_info) > 1024:
                    later_tracks.append(current_chunk)  # Save the current chunk
                    current_chunk = track_info          # Start a new chunk
                    track_count = 1
                else:
                    current_chunk += track_info
                    track_count += 1

            # Append remaining tracks in the last chunk
            if current_chunk:
                later_tracks.append(current_chunk)

            # Add fields for each chunk of tracks
            field_count = 0
            for index, chunk in enumerate(later_tracks):
                if field_count >= 25 - 1:  # Leave room for a final "Continued..." field
                    embed.add_field(
                        name="Continued...",
                        value="Queue is too long to display fully.",
                        inline=True
                    )
                    break

                embed.add_field(
                    name="Later:" if index == 0 else "\u200b",  # Use the title "Later:" only once
                    value=chunk,
                )

                field_count += 1

        return embed
