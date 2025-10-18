from discord.ext import commands
from discord import app_commands, Interaction


class Hello(commands.Cog):
    """A simple hello world cog with a slash command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @app_commands.command(name="hello", description="Says hello to you!")
    async def hello(self, interaction: Interaction) -> None:
        """A simple hello command usable as a slash command."""
        await interaction.response.send_message(f"Hello, {interaction.user.mention} 👋")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        # This will print when the bot is ready; useful for basic feedback during startup.
        print(f"{self.__class__.__name__} cog is ready")


async def setup(bot: commands.Bot) -> None:
    """Standard extension setup function used by discord.py to add the cog."""
    await bot.add_cog(Hello(bot))
