import discord
from discord.ext import commands
from discord import app_commands


class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="avatar", description="Gets the avatar of a user in various formats."
    )
    async def avatar(self, interaction: discord.Interaction, member: discord.Member = None):
        """Gets the avatar of a user in various formats."""
        if member is None:
            member = interaction.user

        formats = ["png", "jpg", "webp"]
        embed = discord.Embed(title=f"{member.display_name}'s Avatar")
        embed.set_image(url=member.avatar.url)

        description = ""
        for fmt in formats:
            try:
                avatar_url = member.avatar.replace(format=fmt).url
                description += f"[{fmt.upper()}]({avatar_url})\n"
            except Exception as e:
                description += f"{fmt.upper()}: Error getting format - {e}\n"

        embed.description = description
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(ProfileCog(bot))
