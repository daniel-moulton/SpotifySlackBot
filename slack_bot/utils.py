import re


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
        "keycap_ten": 10
    }
    return emoji_to_number.get(emoji, 0)


def get_name_from_id(user_id: str, app) -> str:
    """
    Get the display name of a user from their Slack user ID.

    Args:
        user_id (str): The Slack user ID.

    Returns:
        str: The display name of the user, or "Unknown User" if not found.
    """
    user_id = app.client.users_info(user=user_id)
    if user_id and user_id.get("ok"):
        return user_id["user"].get("profile", {}).get("display_name", "Unknown User")


def format_leaderboard_table(songs_data: list,
                             title: str = "🎵 Top Songs Leaderboard") -> str:
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
            rank_display = rank_medals[i-1]
        else:
            rank_display = f"{i}th"

        # Rating
        avg_rating = song['average_reaction']
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
        title = song['title'][:25] + "..." if len(song['title']) > 28 else song['title']
        artists = ", ".join(song['artists'])  # Join the list of artists into a single string
        artists = artists[:21] + "..." if len(artists) > 24 else artists
        link = f"<{song['message_link']}|*_Go to song_*>"

        message += f"{title:<30} | {artists:<24} | {link}\n"

    message += "```"
    return message
