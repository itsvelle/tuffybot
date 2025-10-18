# TuffyBot - Discord Bot

A simple Discord bot built with discord.py that automatically loads cogs from the `cogs/` folder.

## Features

- Automatic cog loading from `cogs/` folder
- All Discord intents enabled
- Hybrid commands (work as both prefix and slash commands)
- Environment variable configuration for security

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure your bot:
   - Copy `.env.example` to `.env`
   - Add your Discord bot token to `.env`

3. Run the bot:
```bash
python main.py
```

## Project Structure

```
tuffybot/
├── main.py              # Main bot file
├── cogs/                # Folder for bot cogs/extensions
│   └── hello.py         # Example hello world cog
├── .env                 # Environment variables (not in git)
├── .env.example         # Example environment file
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Adding New Cogs

To add a new cog:

1. Create a new Python file in the `cogs/` folder
2. Follow the structure of `cogs/hello.py`
3. The bot will automatically load it on startup

## Commands

- `!hello` or `/hello` - Says hello to you!

## Configuration

Edit `.env` file to configure:
- `DISCORD_TOKEN` - Your Discord bot token

## Getting a Discord Bot Token

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section
4. Click "Reset Token" to get your token
5. Enable all Privileged Gateway Intents in the Bot settings
6. Copy the token to your `.env` file
