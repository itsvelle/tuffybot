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
from typing import Optional, Dict

import discord
from discord import app_commands
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
        # Maps module name (e.g. "cogs.ping_cog") -> last modification time
        self._cog_mtimes: Dict[str, float] = {}
        # Background task that watches the cogs directory for changes
        self._cog_watcher_task: Optional[asyncio.Task] = None

    async def add_cog(self, cog: commands.Cog, *, override: bool = False) -> None:
        """Override add_cog to automatically apply allowed_contexts to all app commands."""
        # Apply allowed_contexts to all app commands in the cog
        for command in cog.__cog_app_commands__:
            if isinstance(command, app_commands.Command):
                # Only apply if not already set
                if (
                    not hasattr(command, "_allowed_contexts")
                    or command._allowed_contexts is None
                ):
                    command.allowed_contexts = app_commands.AppCommandContext(
                        guild=True, dm_channel=True, private_channel=True
                    )

        # Call the parent add_cog method
        await super().add_cog(cog, override=override)

    async def setup_hook(self) -> None:  # called by discord.py on startup
        await self.load_cogs()
        # Sync application (slash) commands to the default guilds/global namespace
        try:
            await self.tree.sync()
        except (
            Exception
        ) as exc:  # keep broad catch to avoid crashing on partial failures
            print(f"Warning: failed to sync app commands: {exc}")
        # Start the background watcher task after initial load/sync
        if self._cog_watcher_task is None:
            # create_task so it runs independently of setup_hook
            self._cog_watcher_task = asyncio.create_task(self._cog_watcher())

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
            fullpath = os.path.join(cogs_dir, entry)
            try:
                mtime = os.path.getmtime(fullpath)
            except Exception:
                mtime = 0.0
            try:
                await self.load_extension(module)
                print(f"Loaded cog: {module}")
                # record the mtime even on success so the watcher has a baseline
                self._cog_mtimes[module] = mtime
            except Exception as exc:
                print(f"Failed to load {module}: {exc}")
                # still record mtime so changes will be detected later
                self._cog_mtimes.setdefault(module, mtime)

    async def on_ready(self) -> None:
        # Avoid referencing self.user attributes that may be None in some type-checkers;
        # At runtime this will be set.
        user = self.user
        if user is not None:
            print(f"Logged in as {user} (ID: {user.id})")
        else:
            print("Bot is ready (user unknown)")

    async def _cog_watcher(self, interval: float = 1.0) -> None:
        """Poll the `cogs/` directory and load/reload extensions when files change.

        This is a simple polling watcher (no external deps) intended to be robust
        and easy to run in typical hosting environments.
        """
        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
        if not os.path.isdir(cogs_dir):
            return

        try:
            while True:
                # Build current map of py files -> mtime
                current: Dict[str, float] = {}
                for entry in sorted(os.listdir(cogs_dir)):
                    if not entry.endswith(".py") or entry.startswith("__"):
                        continue
                    module = f"cogs.{entry[:-3]}"
                    fullpath = os.path.join(cogs_dir, entry)
                    try:
                        current[module] = os.path.getmtime(fullpath)
                    except Exception:
                        current[module] = 0.0

                # Detect added files
                for module, mtime in current.items():
                    if module not in self._cog_mtimes:
                        # New cog file
                        try:
                            await self.load_extension(module)
                            print(f"Watcher: loaded new cog {module}")
                        except Exception as exc:
                            print(f"Watcher: failed to load new cog {module}: {exc}")
                        self._cog_mtimes[module] = mtime
                        # Resync commands after changes
                        try:
                            await self.tree.sync()
                        except Exception as exc:
                            print(f"Watcher: failed to sync app commands: {exc}")

                # Detect modified files
                for module, mtime in current.items():
                    prev = self._cog_mtimes.get(module)
                    if prev is None:
                        continue
                    if mtime > prev:
                        # File changed - reload if loaded, otherwise load
                        try:
                            if module in self.extensions:
                                await self.reload_extension(module)
                                print(f"Watcher: reloaded cog {module}")
                            else:
                                await self.load_extension(module)
                                print(f"Watcher: loaded cog {module} (was not loaded)")
                        except Exception as exc:
                            print(f"Watcher: failed to reload/load {module}: {exc}")
                        self._cog_mtimes[module] = mtime
                        try:
                            await self.tree.sync()
                        except Exception as exc:
                            print(f"Watcher: failed to sync app commands: {exc}")

                # Detect removed files
                removed = [m for m in list(self._cog_mtimes.keys()) if m not in current]
                for module in removed:
                    # Unload the extension if it's loaded
                    try:
                        if module in self.extensions:
                            await self.unload_extension(module)
                            print(f"Watcher: unloaded removed cog {module}")
                    except Exception as exc:
                        print(f"Watcher: failed to unload removed cog {module}: {exc}")
                    self._cog_mtimes.pop(module, None)
                    try:
                        await self.tree.sync()
                    except Exception as exc:
                        print(f"Watcher: failed to sync app commands: {exc}")

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            # Expected during shutdown
            return

    async def close(self) -> None:
        # Cancel watcher task if running and wait for it to finish
        task = getattr(self, "_cog_watcher_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await super().close()


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
