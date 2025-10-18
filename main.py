"""Main entrypoint for the Discord bot.

Responsibilities:
- Initialize a commands.Bot with all intents enabled
- Auto-load all Python modules in the `cogs/` package as extensions
- Read DISCORD_TOKEN from a `.env` file
- Sync application (slash) commands on startup
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv


def get_token() -> str:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN not found in environment. Please add it to a .env file."
        )
    return token


class TuffyBot(commands.Bot):
    def __init__(self, command_prefix: str = "!") -> None:
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=command_prefix, intents=intents, help_command=None
        )

    async def setup_hook(self) -> None:  # called by discord.py on startup
        await self.load_cogs()
        # Sync application (slash) commands to the default guilds/global namespace
        try:
            await self.tree.sync()
        except (
            Exception
        ) as exc:  # keep broad catch to avoid crashing on partial failures
            print(f"Warning: failed to sync app commands: {exc}")

    async def load_cogs(self) -> None:
        """Load all python files inside the cogs directory as extensions."""
        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
        if not os.path.isdir(cogs_dir):
            print("No cogs directory found; skipping cog loading.")
            return

        for entry in sorted(os.listdir(cogs_dir)):
            if not entry.endswith(".py") or entry.startswith("__"):
                continue
            module = f"cogs.{entry[:-3]}"
            try:
                await self.load_extension(module)
                print(f"Loaded cog: {module}")
            except Exception as exc:
                print(f"Failed to load {module}: {exc}")

    async def on_ready(self) -> None:
        # Avoid referencing self.user attributes that may be None in some type-checkers;
        # At runtime this will be set.
        user = self.user
        if user is not None:
            print(f"Logged in as {user} (ID: {user.id})")
        else:
            print("Bot is ready (user unknown)")


async def main(token: Optional[str] = None) -> None:
    token = token or get_token()
    bot = TuffyBot()

    try:
        async with bot:
            await bot.start(token)
    except KeyboardInterrupt:
        print("Received exit, logging out...")
        await bot.close()
    except Exception:
        # Print exception to stderr for CI/hosting visibility then re-raise
        print("Unhandled exception while running the bot:", file=sys.stderr)
        raise


if __name__ == "__main__":
    # Allow passing a token as the first CLI arg for quick testing (optional)
    cli_token: Optional[str] = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(cli_token))
