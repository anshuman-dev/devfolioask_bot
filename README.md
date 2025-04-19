# Judge Helper Bot

A Telegram bot that helps partners with questions about judging, platform setup, and judge invitations.

## Features

- Gitbook documentation scraping
- Auto-categorization of content
- Weekly scheduled updates
- Command-based searches
- Admin statistics

## Setup

### Create the Bot on Telegram

1. Find @BotFather on Telegram
2. Send `/newbot`
3. Name your bot and pick a username
4. Save the API token you receive

### Local Development

1. Clone this repo
2. Copy `.env.example` to `.env` and fill in your values:
3. Install dependencies:
pip install -r requirements.txt
4. Run the bot:
python app.py

## Deployment to Render

1. Create a new Web Service in your Render dashboard
2. Connect your GitHub repo
3. Set these values:
- Build Command: `pip install -r requirements.txt`
- Start Command: `python app.py`
4. Add the Environment Variables (same as in .env)
5. Deploy

## Commands

### User Commands
- `/start` - Introduction
- `/help` - Show commands
- `/search` - Search all topics
- `/judging` - Judging questions
- `/setup` - Platform setup help
- `/invite` - Judge invitation help
- `/contact` - Get human support

### Admin Commands
- `/refresh` - Update knowledge base
- `/stats` - View usage statistics