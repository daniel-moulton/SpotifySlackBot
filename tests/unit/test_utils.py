"""Unit tests for utility functions."""

import pytest
from slack_bot.utils import extract_spotify_track_id, is_valid_spotify_id


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
