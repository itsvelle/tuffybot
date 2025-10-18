import discord
from discord.ext import commands
from discord import app_commands


class PingCog(commands.Cog, name="Ping"):
    """Cog for ping-related commands"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's response time")
    async def ping(self, interaction: discord.Interaction):
        """Check the bot's response time."""
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"Pong! ^~^ Response time: {latency}ms")


async def setup(bot):
    await bot.add_cog(PingCog(bot))
