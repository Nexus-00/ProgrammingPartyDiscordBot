# ProgrammingPartyDiscordBot
Bot made for discord programming party bot during Summer 2024.

## Setup:
1. Clone the repository
   - Do `git clone` in the terminal
2. Run Docker.
   - `docker-compose up -d` to start the database
3. Install all python dependencies
   - `pip install -r requirements.txt`
4. Create a `.env` file in the root directory based on `.env.example` and set the following values
    - `DISCORD_TOKEN` — your Discord bot token
    - `MONGO_CONNECTION_STRING` — your MongoDB connection string
5. Run the bot
    - `python bot.py`