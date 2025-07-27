import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_env_variable(var_name):
    """Get an environment variable."""
    value = os.getenv(var_name)
    if value is None:
        raise ValueError(f"Environment variable '{var_name}' not found.")
    return value


def setup_logging(log_file: str = "slack_bot.log", level: int = logging.INFO):
    """
    Set up logging configuration.

    Args:
        log_file (str): Path to the log file.
        level (int): Logging level (default: logging.INFO).
    """
    # Clear existing logging handlers
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    # Clear the log file before starting the application
    if os.path.exists(log_file):
        with open(log_file, "w"):
            pass  # Truncate the file

    # Set up logging
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=log_file,
    )
    logger = logging.getLogger(__name__)
    logger.info("Logging setup complete.")
