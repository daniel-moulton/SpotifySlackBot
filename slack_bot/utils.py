"""Utility functions for the Slack bot."""

import re
import logging
from datetime import datetime
from slack_bot.templates import SONG_STATS_TEMPLATE, USER_STATS_TEMPLATE

logger = logging.getLogger(__name__)


def extract_spotify_track_id(message_text: str) -> str:
    """
    Extract the Spotify track ID from a message text.

    Args:
        message_text (str): The text of the message containing the Spotify track URL.

    Returns:
        str: The extracted Spotify track ID, or None if no valid URL is found.
    """
    spotify_pattern = r"https://open\.spotify\.com/track/([a-zA-Z0-9]+)"
    match = re.search(spotify_pattern, message_text)
    return match.group(1) if match else None


def is_valid_spotify_id(spotify_id: str) -> bool:
    """
    Validate if the given string is a valid Spotify track ID.

    Spotify uses the same format for tracks, albums, and artists, which is a 22-character alphanumeric string.

    Args:
        spotify_id (str): The Spotify track ID to validate.

    Returns:
        bool: True if the ID is valid, False otherwise.
    """
    spotify_pattern = r"^[a-zA-Z0-9]{22}$"
    return bool(re.match(spotify_pattern, spotify_id))


# def extract_or_validate_track_id(input_str: str) -> Optional[str]:
#     """
#     Extract Spotify track ID from a string or valide if input is already a valid track ID.

#     Args:
#         input_str (str): The input string which may contain a Spotify track ID or a URL.

#     Returns:
#         Optional[str]: The extracted or validated Spotify track ID, or None if not found.
#     """
#     track_id = extract_spotify_track_id(input_str)

#     if track_id:
#         return track_id

#     # If no URL found, check if the input is a valid Spotify ID
#     if is_valid_spotify_id(input_str):
#         return input_str
#     return None


def convert_emoji_to_number(emoji: str) -> int:
    """
    Convert a Slack emoji reaction to a numeric value.

    Args:
        emoji (str): The emoji reaction string.

    Returns:
        int: The numeric value corresponding to the emoji.
    """
    emoji_to_number = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "keycap_ten": 10,
    }
    return emoji_to_number.get(emoji, 0)


def convert_number_to_emoji(number: int) -> str:
    """
    Convert a numeric value to its corresponding Slack emoji.

    Args:
        number (int): The numeric value (1-10).

    Returns:
        str: The emoji string for display.
    """
    number_to_emoji = {
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
        5: "5️⃣",
        6: "6️⃣",
        7: "7️⃣",
        8: "8️⃣",
        9: "9️⃣",
        10: "🔟",
    }
    return number_to_emoji.get(number, str(number))


def verify_user_exists(user_id: str, app) -> bool:
    """
    Verify if a user exists in Slack by their user ID.

    Args:
        user_id (str): The Slack user ID.

    Returns:
        bool: True if the user exists, False otherwise.
    """
    try:
        response = app.client.users_info(user=user_id)
        return response.get("ok", False)
    except Exception as e:
        logger.error("Error verifying user {user_id}: %s", e)
        return False


def get_user_id(user: str) -> str:
    """
    Extract the Slack user ID from a user mention string.

    Args:
        user (str): The user mention string (e.g., "<@U12345678>").

    Returns:
        str: The Slack user ID, or None if the format is incorrect.
    """
    match = re.match(r"<@([A-Z0-9]+)\|", user)
    return match.group(1) if match else None


def get_name_from_id(user_id: str, app) -> str:
    """
    Get the display name of a user from their Slack user ID.
    Up to caller to ensure the user exists (verify_user_exists).

    Args:
        user_id (str): The Slack user ID.

    Returns:
        str: The display name of the user, or "Unknown User" if not found.
    """
    response = app.client.users_info(user=user_id)
    return response["user"].get("profile", {}).get("display_name", "Unknown User")


def format_leaderboard_table(songs_data: list, title: str = "🎵 Top Songs Leaderboard") -> str:
    """
    Format the leaderboard table for top songs.

    Args:
        songs_data (list): List of dictionaries containing song data.
        title (str): Title for the leaderboard message.

    Returns:
        str: Formatted leaderboard message.
    """
    message = f"*{title}*\n"
    message += "```"
    message += "Rank | Rating | Count | Song & Artist\n"
    message += "-----|--------|-------|----------------------------------------------\n"

    for i, song in enumerate(songs_data, 1):
        # Use consistent text ranking
        if i <= 3:
            rank_medals = ["1st", "2nd", "3rd"]
            rank_display = rank_medals[i - 1]
        else:
            rank_display = f"{i}th"

        # Rating
        avg_rating = song["average_reaction"]
        rating_display = f"{avg_rating:.1f}" if avg_rating > 0 else "N/A"

        # Truncate long titles
        title_artist = f"{song['title']} - {song['artists']}"
        if len(title_artist) > 45:
            title_artist = title_artist[:42] + "..."

        message += f"{rank_display:<4} | {rating_display:<6} | {song['reaction_count']:<5} | {title_artist}\n"

    message += "```"
    return message


def format_unrated_songs_table(songs_data: list, user_name: str) -> str:
    """
    Format the unrated songs table for a specific user.

    Args:
        songs_data (list): List of dictionaries containing song data.
        user_name (str): The name of the user for whom the unrated songs are being displayed.

    Returns:
        str: Formatted unrated songs message.
    """
    message = f"*🎵 Unrated Songs for {user_name} 🎵*\n"
    message += "```"
    message += "Title                          | Artists                  | Link\n"
    message += "-------------------------------|--------------------------|-----------------------------\n"

    for song in songs_data:
        # Truncate long titles and artist names for better formatting
        title = song["title"][:25] + "..." if len(song["title"]) > 28 else song["title"]
        artists = ", ".join(song["artists"])  # Join the list of artists into a single string
        artists = artists[:21] + "..." if len(artists) > 24 else artists
        link = f"<{song['message_link']}|*_Go to song_*>"

        message += f"{title:<30} | {artists:<24} | {link}\n"

    message += "```"
    return message


def handle_song_stats(song_details: dict, reaction_details: list, app) -> str:
    """
    Handles /stats command to display statistics for a song.

    Args:
        song_details (dict): Dictionary containing song details with keys:
            - 'id': Spotify track ID.
            - 'title': Title of the song.
            - 'album': Album name.
            - 'artists': List of artists.
            - 'user': User who added the song.
            - 'message_link': Link to the song message.
        reaction_details (list): List of dictionaries containing reaction details with keys
            - 'user': User ID of the person who reacted.
            - 'reaction': User's rating of the song.
        app (App): The Slack app instance to interact with Slack API.

    Returns:
        str: Formatted message with song statistics.
    """
    if not song_details:
        return "No song details found."

    # Preprocess song details
    song_title: str = song_details.get("title", "Unknown Title")
    song_artists: str = ", ".join(song_details.get("artists", ["Unknown Artist"]))
    song_album: str = song_details.get("album", "Unknown Album")
    user: str = song_details.get("user", "Unknown User")
    user_name: str = get_name_from_id(user, app) if user != "Unknown User" else "Unknown User"
    message_link: str = song_details.get("message_link", "#")
    message_time: str = get_message_time(message_link) if message_link != "#" else "Unknown"
    message_link_fmt: str = f"<{message_link}|*_Go to song_*>" if message_link != "#" else "#"

    rating_stats: dict = get_rating_stats(reaction_details, app)

    data: dict = {
        "title": song_title,
        "artists": song_artists,
        "album": song_album,
        "user_name": user_name,
        "message_time": message_time,
        "message_link": message_link_fmt,
        "average_rating": rating_stats["average_rating"],
        "reaction_count": rating_stats["reaction_count"],
        "user_ratings": rating_stats["user_ratings"],
    }

    return format_stats_message(SONG_STATS_TEMPLATE, data)


def handle_user_stats(user_name: str, user_stats: dict, top_songs: list, top_artists: list) -> str:
    """
    Handles /stats command to display statistics for a user.

    Args:
        user_name (str): Display name of the user.
        user_stats (dict): Dictionary containing user statistics.
        top_songs (list): List of top-rated songs by the user.
        top_artists (list): List of top artists for the user.

    Returns:
        str: Formatted message with user statistics.
    """
    # Format top songs section
    if top_songs:
        top_songs_text = "*🎵 Top Songs:*\n"
        for i, song in enumerate(top_songs, 1):
            artists_str = ", ".join(song["artists"])
            top_songs_text += (
                f"{i}. {song['title']} - {artists_str} "
                f"({song['average_rating']:.1f}⭐, {song['reaction_count']} ratings)\n"
            )
    else:
        top_songs_text = "*🎵 Top Songs:*\nNo rated songs yet"

    # Format top artists section
    if top_artists:
        top_artists_text = "*🎤 Top Artists:*\n"
        for i, artist in enumerate(top_artists, 1):
            top_artists_text += (
                f"{i}. {artist['name']} ({artist['song_count']} songs, {artist['average_rating']:.1f}⭐ avg)\n"
            )
    else:
        top_artists_text = "*🎤 Top Artists:*\nNo songs submitted yet"

    # Prepare data for template
    data = {
        "user_name": user_name,
        "songs_submitted": user_stats["songs_submitted"],
        "ratings_given": user_stats["ratings_given"],
        "songs_rated": user_stats["songs_rated"],
        "total_rateable_songs": user_stats["total_rateable_songs"],
        "rating_percentage": user_stats["rating_percentage"],
        "avg_rating_given": user_stats["avg_rating_given"],
        "avg_rating_received": user_stats["avg_rating_received"],
        "top_songs_section": top_songs_text,
        "top_artists_section": top_artists_text,
    }

    return format_stats_message(USER_STATS_TEMPLATE, data)


def get_rating_stats(reaction_details: list, app) -> dict:
    """
    Calculate average rating and reaction count from reaction details.

    Args:
        reaction_details (list): List of dictionaries containing reaction details with keys:
            - 'user': User ID of the person who reacted.
            - 'reaction': User's rating of the song.
        app (App): The Slack app instance to interact with Slack API.

    Returns:
        dict: Dictionary with average_rating (str), reaction_count (int), user_ratings (str)
    """
    if not reaction_details:
        return {
            "average_rating": "N/A",
            "reaction_count": 0,
            "user_ratings": "No user ratings.",
        }

    total_rating: int = sum(reaction.get("reaction", 0) for reaction in reaction_details)
    reaction_count: int = len(reaction_details)
    average_rating: str = f"{(total_rating / reaction_count):.1f}" if reaction_count > 0 else "N/A"

    user_ratings: list = []
    for reaction in reaction_details:
        user_id: str = reaction.get("user")
        if user_id:
            user_name: str = get_name_from_id(user_id, app)
            rating_emoji: str = convert_number_to_emoji(reaction.get("reaction", 0))
            user_ratings.append(f"{user_name}: {rating_emoji}")

    user_ratings_str: str = "\n".join(user_ratings) if user_ratings else "No user ratings."

    return {
        "average_rating": average_rating,
        "reaction_count": reaction_count,
        "user_ratings": user_ratings_str,
    }


def get_message_time(message_link: str) -> str:
    """
    Extract the time from a Slack message link.

    Slack message links end in a format like "pX" where X is the epoch timestamp.

    Args:
        message_link (str): The Slack message link.

    Returns:
        str: The formatted time of the message (e.g., "2023-10-01 12:00:00").
    """
    match = re.search(r"p(\d+)", message_link)
    if match:
        epoch_time = int(match.group(1)) / 1_000_000  # Convert microseconds to seconds
        # Convert epoch time to a human-readable format
        return datetime.fromtimestamp(epoch_time).strftime("%Y-%m-%d %H:%M:%S")
    return "Unknown time"


def parse_command_arguments(command_text: str) -> dict:
    """
    Parse command arguments from a command text.

    Args:
        command_text (str): The text of the command (doesn't include the slash command).

    Returns:
        dict: A dictionary containing the parsed arguments and their values.
    """
    args = {"public": False}  # Default to private if not specified
    parts = command_text.split()

    for i, part in enumerate(parts):
        # Check for flags (--flag)
        if part.startswith("--"):
            key = part[2:]
            # Check if next part is a value or the next flag
            if i + 1 < len(parts) and not parts[i + 1].startswith("--"):
                args[key] = parts[i + 1]
            else:
                args[key] = True

    return args


def send_response(respond, say, message: str, is_public: bool = False) -> None:
    """
    Send a response message to the channel, either as a public message or an ephemeral message.

    Args:
        respond (function): The respond function from the Slack app context.
        say (function): The say function from the Slack app context.
        message (str): The message to send.
        is_public (bool): If True, sends a public message; if False, sends an ephemeral message.

    Returns:
        None
    """
    if is_public:
        say(message, unfurl_links=False, unfurl_media=False)
    else:
        respond(message, unfurl_links=False, unfurl_media=False)


def format_stats_message(template: str, data: dict) -> str:
    """
    Format a message using a template and data.

    Args:
        template (str): The message template with placeholders.
        data (dict): A dictionary containing the data to fill in the template.

    Returns:
        str: The formatted message.
    """
    try:
        return template.format(**data)
    except KeyError as e:
        logger.error("Missing key in data for formatting: %s", e)
        return "Error formatting message. Missing data."
