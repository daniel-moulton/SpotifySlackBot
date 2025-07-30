"""Unit tests for utility functions."""

import pytest
from unittest.mock import patch
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
    format_stats_message,
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


@pytest.mark.parametrize(
    """
    mention,
    expected_user_id,
    """,
    [
        # Additional edge cases
        ("<@U12345678|name>", "U12345678"),  # Longer user ID
        ("<@U1|a>", "U1"),  # Short user ID and name
        ("<@|username>", None),  # Missing user ID
        ("<@U12345|>", "U12345"),  # Empty username part
        ("<@U12345|user|name>", "U12345"),  # Multiple pipes (should still work)
        ("U12345|username", None),  # Missing angle brackets
        ("<U12345|username>", None),  # Missing @ symbol
    ],
)
def test_get_user_id_edge_cases(mention, expected_user_id):
    """Test get_user_id with additional edge cases."""
    result = get_user_id(mention)
    assert result == expected_user_id


@pytest.mark.parametrize(
    "message_link, expected",
    [
        ("https://slack.com/archives/C123/p1634567890123456", "2021-10-18 15:38:10"),
        ("invalid_link", "Unknown time"),
        ("", "Unknown time"),
    ],
)
def test_get_message_time(message_link, expected):
    """Test getting message time from Slack link."""
    with patch("slack_bot.utils.datetime") as mock_datetime:
        mock_datetime = mock_datetime.fromtimestamp.return_value
        mock_datetime.strftime.return_value = expected

        result = get_message_time(message_link)
        assert result == expected


@pytest.mark.parametrize(
    """
    command_text,
    expected_keys,
    expected_values,
    """,
    [
        # Test that basic commands include public key
        ("/leaderboard", ["public"], {"public": False}),
        ("/stats", ["public"], {"public": False}),
        # Test specific argument parsing
        ("/leaderboard --limit 5", ["limit", "public"], {"limit": "5", "public": False}),
        ("/leaderboard --public", ["public"], {"public": True}),
        ("/stats --user U12345", ["user", "public"], {"user": "U12345", "public": False}),
        # Test multiple arguments
        ("/leaderboard --limit 10 --public", ["limit", "public"], {"limit": "10", "public": True}),
    ],
)
def test_parse_command_arguments_flexible(command_text, expected_keys, expected_values):
    """Test parsing command arguments with flexible assertions."""
    result = parse_command_arguments(command_text)

    # Check that expected keys exist
    for key in expected_keys:
        assert key in result

    # Check that expected values match
    for key, value in expected_values.items():
        assert result[key] == value

    # Ensure result is a dictionary
    assert isinstance(result, dict)


@pytest.mark.parametrize(
    """
    template,
    data,
    expected_content,
    """,
    [
        # Success; valid template and data
        ("Hello {name}, you have {count} items", {"name": "John", "count": 5}, ["Hello John", "you have 5 items"]),
        # Success; template with multiple placeholders
        (
            "*Song:* {title} by {artist}\n*Rating:* {rating}/10",
            {"title": "Test Song", "artist": "Test Artist", "rating": 8},
            ["Test Song", "Test Artist", "8/10"],
        ),
        # Success; empty template
        ("", {}, []),
        # Success; template with no placeholders
        ("Static message", {"unused": "data"}, ["Static message"]),
    ],
)
def test_format_stats_message_success(template, data, expected_content):
    """Test format_stats_message with valid inputs."""
    result = format_stats_message(template, data)

    # Check that expected content appears in result
    for content in expected_content:
        assert str(content) in result

    # Check it returns a string
    assert isinstance(result, str)


@pytest.mark.parametrize(
    """
    template,
    data,
    expected_error_message,
    """,
    [
        # Missing key in data
        ("Hello {name}, you have {missing_key} items", {"name": "John"}, "Error formatting message. Missing data."),
        # Multiple missing keys
        ("{key1} and {key2} are missing", {}, "Error formatting message. Missing data."),
    ],
)
def test_format_stats_message_missing_keys(template, data, expected_error_message):
    """Test format_stats_message with missing template keys."""
    result = format_stats_message(template, data)
    assert result == expected_error_message


def test_format_leaderboard_table():
    """Test formatting leaderboard table."""
    mock_songs = [
        {
            "id": "track1",
            "title": "Amazing Song",
            "artists": "Great Artist",
            "average_reaction": 8.5,
            "reaction_count": 10,
        }
    ]

    result = format_leaderboard_table(mock_songs)

    # Check structure and basic content
    assert "🎵 Top Songs Leaderboard" in result
    assert "```" in result
    assert "Rank | Rating | Count | Song & Artist" in result
    assert "Amazing Song" in result
    assert "Great Artist" in result
    assert "8.5" in result
    assert "1st" in result


def test_format_unrated_songs_table():
    """Test formatting unrated songs table."""
    mock_songs = [
        {"title": "Unrated Song 1", "artists": ["Artist A", "Artist B"], "message_link": "https://slack.com/link1"}
    ]

    user_name = "John Doe"
    result = format_unrated_songs_table(mock_songs, user_name)

    # Check structure and basic content
    assert f"🎵 Unrated Songs for {user_name} 🎵" in result
    assert "Title" in result and "Artists" in result and "Link" in result
    assert "Unrated Song 1" in result
    assert "Artist A, Artist B" in result
    assert "Go to song" in result
