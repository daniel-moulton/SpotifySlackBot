import os
import re
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bot.handlers import register_handlers
from config.settings import get_env_variable, setup_logging
from database.database import SpotifyBotDatabase


# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Slack app
app = App(token=get_env_variable("SLACK_BOT_TOKEN"))

# Initialize database
db = SpotifyBotDatabase()

# Register handlers
register_handlers(app, db)

if __name__ == "__main__":
    try:
        handler = SocketModeHandler(app, get_env_variable("SLACK_APP_TOKEN"))
        logger.info("Starting Slack app...")
        handler.start()
        logger.info("Slack app started successfully!")
    except Exception as e:
        logger.error(f"Failed to start Slack app: {e}")
        raise
