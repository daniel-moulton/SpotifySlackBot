import logging
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from config.settings import get_env_variable

# Initialize Spotify API client
spotify_client = Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=get_env_variable("SPOTIFY_CLIENT_ID"),
        client_secret=get_env_variable("SPOTIFY_CLIENT_SECRET")
    )
)


def fetch_track_details(track_id: str):
    """Fetch track details from Spotify API."""
    try:
        track = spotify_client.track(track_id)
        if not track:
            logging.warning(f"No track found for ID: {track_id}")
            return None
        track_info = {
            "id": track["id"],
            "name": track["name"],
            "artists": [{"id": artist["id"], "name": artist["name"]} for artist in track["artists"]],
            "album": track["album"]["name"],
            "release_date": track["album"]["release_date"],
        }
        return track_info
    except Exception as e:
        logging.error(f"Error fetching track details for ID {track_id}: {e}")
        return None
