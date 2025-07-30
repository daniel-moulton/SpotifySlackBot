"""Unit tests for utility functions."""

import pytest
from slack_bot.utils import (
    extract_spotify_track_id,
    is_valid_spotify_id,
    convert_emoji_to_number,
    convert_number_to_emoji,
    verify_user_exists,
    get_user_id,
    get_name_from_id,
    format_leaderboard_table,
    format_unrated_songs_table,
    handle_song_stats,
    handle_user_stats,
    get_rating_stats,
    get_message_time,
    parse_command_arguments,
    send_response,
    format_stats_message
)


@pytest.mark.parametrize(
    """
    message,
    expected_result,
    """,
    [
        # Success; valid Spotify track ID
        (
            "https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6",
            "6rqhFgbbKwnb9MLmUQDhG6",
        ),
        # Success; valid Spotify link in message
        (
            "Check out this track: https://open.spotify.com/track/6rqhFgbbKwnb9MLmUQDhG6",
            "6rqhFgbbKwnb9MLmUQDhG6",
        ),
        # Failure; invalid Spotify track ID
        (
            "https://open.spotify.com/track/invalid",
            "invalid",
        ),
        # Failure; no Spotify link in message
        (
            "This is not a Spotify link",
            None,
        ),
    ],
)
def test_extract_spotify_track_id(message, expected_result):
    """Test extracting Spotify track ID from a message."""
    result = extract_spotify_track_id(message)
    assert result == expected_result


@pytest.mark.parametrize(
    """
    spotify_id,
    expected_result,
    """,
    [
        # Success; valid Spotify ID (22 characters)
        ("6rqhFgbbKwnb9MLmUQDhG6", True),
        # Failure; invalid Spotify ID
        ("invalid", False),
        # Failure; empty string
        ("", False),
        # Failure; integer input
        (1234567890123456789012, False),
        # Failure; None
        (None, False),
    ],
)
def test_is_valid_spotify_id(spotify_id, expected_result):
    """Test validating Spotify track ID."""
    result = is_valid_spotify_id(spotify_id)
    assert result == expected_result


@pytest.mark.parametrize(
    """
    emoji,
    expected_number,
    """,
    # Slack sends emojis as strings, not as Unicode characters
    [
        # Success; valid emoji to number conversion
        ("one", 1),
        ("five", 5),
        ("keycap_ten", 10),
        # Failure; invalid emoji
        ("invalid_emoji", 0),
        ("❓", 0),
        ("", 0),
    ],
)
def test_convert_emoji_to_number(emoji, expected_number):
    """Test converting emoji to number."""
    result = convert_emoji_to_number(emoji)
    assert result == expected_number


@pytest.mark.parametrize(
    """
    number,
    expected_emoji,
    """,
    [
        # Success; valid number to emoji conversion (returns Unicode emojis)
        (1, "1️⃣"),
        (5, "5️⃣"),
        (10, "🔟"),
        # Failure; invalid numbers (returns string representation)
        (0, "0"),
        (-1, "-1"),
        (11, "11"),
        (100, "100"),
    ],
)
def test_convert_number_to_emoji(number, expected_emoji):
    """Test converting number to emoji."""
    result = convert_number_to_emoji(number)
    assert result == expected_emoji
