"""SpotifyBotDatabase class for managing a SQLite database for Spotify Slack bot"""

import sqlite3
import logging
from typing import Optional


# Configure logging
logger = logging.getLogger(__name__)


class SpotifyBotDatabase:
    """Database class for managing Spotify-related data in a SQLite database."""

    def __init__(self, db_path: str = "spotify_bot.db"):
        """
        Initialize the database connection and create tables if they do not exist.

        Args:
            db_path (str): Path to the SQLite database file. Defaults to "spotify_bot.db".
        """
        self.db_path = db_path
        self.connection = None
        self._connect()
        self._create_tables()

    def _connect(self):
        """Connect to the SQLite database."""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable row access by name
            logger.info("Connected to database at %s", self.db_path)
        except sqlite3.Error as e:
            logger.error("Error connecting to database: %s", e)
            raise

    def _create_tables(self):
        """Create tables if they do not exist."""
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                # Create songs table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS songs (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        album TEXT NOT NULL,
                        user TEXT NOT NULL,
                        message_link TEXT
                    )
                """
                )

                # Create artists table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS artists (
                        id TEXT PRIMARY KEY,
                        name TEXT UNIQUE NOT NULL
                    )
                """
                )

                # Create song_artists table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS song_artists (
                        song_id TEXT NOT NULL,
                        artist_id INTEGER NOT NULL,
                        FOREIGN KEY (song_id) REFERENCES songs (id),
                        FOREIGN KEY (artist_id) REFERENCES artists (id),
                        PRIMARY KEY (song_id, artist_id)
                    )
                """
                )

                # Create reactions table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS reactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        song_id TEXT NOT NULL,
                        user TEXT NOT NULL,
                        reaction INTEGER NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (song_id) REFERENCES songs (id)
                    )
                """
                )

                connection.commit()
                logger.info("Tables created successfully.")
            except sqlite3.Error as e:
                logger.error("Error creating tables: %s", e)
                connection.rollback()
                raise

    def close(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed.")
        else:
            logger.info("No database connection to close.")

    # Song-related methods
    def insert_song_with_artists(
        self,
        song_id: str,
        title: str,
        album: str,
        artists: list,
        user: str,
        message_link: Optional[str] = None,
    ) -> None:
        """
        Insert a song and its associated artists into the database.

        Args:
            song_id (str): Unique identifier for the song (uses Spotify track ID).
            title (str): Song title.
            album (str): Album name.
            artists (list): List of dictionaries containing arist ID (Spotify artist ID) and name.
            user (str): User ID of the person who added the song.
            message_link (str, optional): Link to the message containing the song.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                # Insert song into songs table
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO songs (id, title, album, user, message_link)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (song_id, title, album, user, message_link),
                )

                # Insert artists into artists table and associate with the song
                for artist in artists:
                    # Check if the artist already exists
                    cursor.execute(
                        """
                        SELECT id FROM artists WHERE id = ?
                    """,
                        (artist["id"],),
                    )
                    artist_row = cursor.fetchone()

                    if artist_row:
                        artist_id = artist_row["id"]
                    else:
                        # Insert the artist and fetch its id
                        cursor.execute(
                            """
                            INSERT INTO artists (id, name)
                            VALUES (?, ?)
                        """,
                            (artist["id"], artist["name"]),
                        )
                        artist_id = artist["id"]

                    # Associate the artist with the song
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO song_artists (song_id, artist_id)
                        VALUES (?, ?)
                    """,
                        (song_id, artist_id),
                    )

                connection.commit()
                logger.info(
                    "Inserted song '{title}' by %s successfully.", ", ".join(artist["name"] for artist in artists)
                )
            except sqlite3.Error as e:
                logger.error("Error inserting song with artists: %s", e)
                connection.rollback()
                raise

    def fetch_songs(self, song_id: Optional[str] = None) -> Optional[dict]:
        """
        Fetch song(s) from the database.

        Args:
            song_id (str, optional): Unique identifier for the song (uses Spotify track ID).
                                     If None, fetch all songs.

        Returns:
            dict or list: If song_id is provided, returns a dictionary with song details.
                          If song_id is None, returns a list of dictionaries with all song details.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                if song_id:
                    # Fetch a specific song
                    cursor.execute(
                        """
                        SELECT s.id, s.title, s.album, s.user, s.message_link, GROUP_CONCAT(a.name) AS artists
                        FROM songs s
                        LEFT JOIN song_artists sa ON s.id = sa.song_id
                        LEFT JOIN artists a ON sa.artist_id = a.id
                        WHERE s.id = ?
                        GROUP BY s.id
                    """,
                        (song_id,),
                    )
                    row = cursor.fetchone()
                    if row:
                        return {
                            "id": row["id"],
                            "title": row["title"],
                            "album": row["album"],
                            "artists": (row["artists"].split(",") if row["artists"] else []),
                            "user": row["user"],
                            "message_link": row["message_link"],
                        }
                    else:
                        logger.info("No song found with ID: %s", song_id)
                        return None
                else:
                    # Fetch all songs
                    cursor.execute(
                        """
                        SELECT s.id, s.title, s.album, GROUP_CONCAT(a.name) AS artists
                        FROM songs s
                        LEFT JOIN song_artists sa ON s.id = sa.song_id
                        LEFT JOIN artists a ON sa.artist_id = a.id
                        GROUP BY s.id
                    """
                    )
                    rows = cursor.fetchall()
                    return [
                        {
                            "id": row["id"],
                            "title": row["title"],
                            "album": row["album"],
                            "artists": (row["artists"].split(",") if row["artists"] else []),
                            "user": row["user"],
                            "message_link": row["message_link"],
                        }
                        for row in rows
                    ]
            except sqlite3.Error as e:
                logger.error("Error fetching songs: %s", e)
                raise

    def delete_song(self, song_id: str) -> None:
        """
        Delete a song and its associated artists from the database.

        Args:
            song_id (str): Unique identifier for the song (uses Spotify track ID).
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                # Delete from song_artists table
                cursor.execute(
                    """
                    DELETE FROM song_artists WHERE song_id = ?
                """,
                    (song_id,),
                )

                # Delete from songs table
                cursor.execute(
                    """
                    DELETE FROM songs WHERE id = ?
                """,
                    (song_id,),
                )

                # Delete from reactions table
                cursor.execute(
                    """
                    DELETE FROM reactions WHERE song_id = ?
                """,
                    (song_id,),
                )

                connection.commit()
                logger.info("Deleted song with ID: %s successfully.", song_id)
            except sqlite3.Error as e:
                logger.error("Error deleting song: %s", e)
                connection.rollback()
                raise

    def fetch_song_by_name(self, title: str) -> Optional[list[dict]]:
        """
        Fetch all song metadata that matches a given title.

        Args:
            title (str): Title of the song (or part of the title) to search for.

        Returns:
            list: List of dictionaries containing song details that match the title.
                  Returns None if no songs are found.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT id FROM songs WHERE title LIKE ?
                """,
                    (f"%{title}%",),
                )
                rows = cursor.fetchall()

                if not rows:
                    logger.info("No songs found with title: %s", title)
                    return None

                # Use fetch_songs to get full details for each song
                matching_songs = []
                for row in rows:
                    song_details = self.fetch_songs(song_id=row["id"])
                    if song_details:
                        matching_songs.append(song_details)

                return matching_songs if matching_songs else None
            except sqlite3.Error as e:
                logger.error("Error fetching song by name: %s", e)
                raise

    def update_song_message_link(self, song_id: str, message_link: str):
        """
        Update the message link for a song in the database.

        Args:
            song_id (str): Unique identifier for the song (uses Spotify track ID).
            message_link (str): New message link to be updated.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE songs
                    SET message_link = ?
                    WHERE id = ?
                """,
                    (message_link, song_id),
                )
                connection.commit()
                logger.info("Updated message link for song ID %s.", song_id)
            except sqlite3.Error as e:
                logger.error("Error updating message link: %s", e)
                connection.rollback()
                raise

    # Reaction-related methods
    def insert_reaction(self, song_id: str, user: str, reaction: int):
        """
        Insert a reaction for a song by a user.

        Args:
            song_id (str): Unique identifier for the song (uses Spotify track ID).
            user (str): User ID of the person reacting.
            reaction (int): Numeric value of the reaction.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO reactions (song_id, user, reaction)
                    VALUES (?, ?, ?)
                """,
                    (song_id, user, reaction),
                )
                connection.commit()
                logger.info("Inserted reaction {reaction} for song ID {song_id} by user %s.", user)
            except sqlite3.Error as e:
                logger.error("Error inserting reaction: %s", e)
                connection.rollback()
                raise

    def remove_reaction(self, song_id: str, user: str):
        """
        Remove a reaction for a song by a user.

        Args:
            song_id (str): Unique identifier for the song (uses Spotify track ID).
            user (str): User ID of the person whose reaction is to be removed.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    DELETE FROM reactions WHERE song_id = ? AND user = ?
                """,
                    (song_id, user),
                )
                connection.commit()
                logger.info("Removed reaction for song ID {song_id} by user %s.", user)
            except sqlite3.Error as e:
                logger.error("Error removing reaction: %s", e)
                connection.rollback()
                raise

    def fetch_reactions_for_track(self, song_id: str) -> list:
        """
        Fetch all reactions for a specific song.

        Args:
            song_id (str): Unique identifier for the song (uses Spotify track ID).

        Returns:
            list: List of dictionaries containing user ID and reaction value.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT user, reaction FROM reactions WHERE song_id = ?
                """,
                    (song_id,),
                )
                rows = cursor.fetchall()
                return [{"user": row["user"], "reaction": row["reaction"]} for row in rows]
            except sqlite3.Error as e:
                logger.error("Error fetching reactions: %s", e)
                raise

    def fetch_reactions_by_user(self, user: str):
        """
        Fetch all reactions made by a specific user.

        Args:
            user (str): User ID of the person whose reactions are to be fetched.

        Returns:
            list: List of dictionaries containing song ID and reaction value.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT song_id, reaction FROM reactions WHERE user = ?
                """,
                    (user,),
                )
                rows = cursor.fetchall()
                return [{"song_id": row["song_id"], "reaction": row["reaction"]} for row in rows]
            except sqlite3.Error as e:
                logger.error("Error fetching user reactions: %s", e)
                raise

    def fetch_reaction(self, song_id: str, user: str) -> Optional[int]:
        """
        Fetch a specific reaction for a song by a user.

        Args:
            song_id (str): Unique identifier for the song (uses Spotify track ID).
            user (str): User ID of the person whose reaction is to be fetched.

        Returns:
            int or None: Reaction value if found, otherwise None.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT reaction FROM reactions WHERE song_id = ? AND user = ?
                """,
                    (song_id, user),
                )
                row = cursor.fetchone()
                return row["reaction"] if row else None
            except sqlite3.Error as e:
                logger.error("Error fetching reaction: %s", e)
                raise

    # Stats-related methods
    def get_top_songs(self, limit: int = 10):
        """
        Get the top songs based on the average reaction value/rating
        (sum of all reactions divided by the number of reactions).

        Args:
            limit (int): Number of top songs to return. Defaults to 10.

        Returns:
            list: List of dictionaries containing song details, reaction count, and artists.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT
                        s.id,
                        s.title,
                        s.album,
                        COALESCE(AVG(r.reaction), 0) AS average_reaction,
                        COUNT(DISTINCT r.id) AS reaction_count,
                        (SELECT GROUP_CONCAT(a2.name, ', ')
                        FROM (SELECT DISTINCT a1.name, sa1.ROWID
                            FROM song_artists sa1 
                            JOIN artists a1 ON sa1.artist_id = a1.id 
                            WHERE sa1.song_id = s.id
                            ORDER BY sa1.ROWID) a2) AS artists
                    FROM songs s
                    LEFT JOIN reactions r ON s.id = r.song_id
                    LEFT JOIN song_artists sa ON s.id = sa.song_id
                    LEFT JOIN artists a ON sa.artist_id = a.id
                    GROUP BY s.id, s.title, s.album
                    HAVING COUNT(a.id) > 0
                    ORDER BY average_reaction DESC, reaction_count DESC
                    LIMIT ?
                """,
                    (limit,),
                )
                rows = cursor.fetchall()
                logger.info("Fetched top %s songs successfully.", limit)
                # print artists of each song
                logger.info("Top songs: %s", [(row["title"], row["artists"]) for row in rows])
                return [
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "album": row["album"],
                        "reaction_count": row["reaction_count"],
                        "average_reaction": row["average_reaction"],
                        "artists": row["artists"] if row["artists"] else "Unknown",
                    }
                    for row in rows
                ]
            except sqlite3.Error as e:
                logger.error("Error fetching top songs: %s", e)
                raise

    def get_unrated_songs(self, user_id: str):
        """
        Get songs that the user has not rated yet.

        Args:
            user (str): User ID of the person whose unrated songs are to be fetched.

        Returns:
            list: List of dictionaries containing song details that the user has not rated.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT s.id, s.title, s.album, s.message_link, GROUP_CONCAT(a.name) AS artists
                    FROM songs s
                    LEFT JOIN song_artists sa ON s.id = sa.song_id
                    LEFT JOIN artists a ON sa.artist_id = a.id
                    WHERE s.id NOT IN (
                        SELECT song_id FROM reactions WHERE user = ?
                    )
                    AND s.user != ?
                    GROUP BY s.id, s.title, s.album
                """,
                    (user_id, user_id),
                )
                rows = cursor.fetchall()
                return [
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "album": row["album"],
                        "artists": row["artists"].split(",") if row["artists"] else [],
                        "message_link": row["message_link"],
                    }
                    for row in rows
                ]
            except sqlite3.Error as e:
                logger.error("Error fetching unrated songs: %s", e)
                raise

    def get_user_statistics(self, user_id: str) -> dict:
        """
        Get comprehensive statistics for a user.

        Args:
            user_id (str): The Slack user ID.

        Returns:
            dict: Dictionary containing user statistics.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                # Get total songs submitted by user
                cursor.execute("SELECT COUNT(*) as count FROM songs WHERE user = ?", (user_id,))
                songs_submitted = cursor.fetchone()["count"]

                # Get total ratings given by user
                cursor.execute("SELECT COUNT(*) as count FROM reactions WHERE user = ?", (user_id,))
                ratings_given = cursor.fetchone()["count"]

                # Get average rating given by user
                cursor.execute("SELECT AVG(reaction) as avg_rating FROM reactions WHERE user = ?", (user_id,))
                avg_rating_given = cursor.fetchone()["avg_rating"] or 0

                # Get average rating received on user's songs
                cursor.execute(
                    """
                    SELECT AVG(r.reaction) as avg_rating 
                    FROM reactions r 
                    JOIN songs s ON r.song_id = s.id 
                    WHERE s.user = ?
                """,
                    (user_id,),
                )
                avg_rating_received = cursor.fetchone()["avg_rating"] or 0

                # Get percentage of songs rated (excluding own songs)
                cursor.execute(
                    """
                    SELECT 
                        COUNT(DISTINCT s.id) as total_rateable_songs,
                        COUNT(DISTINCT r.song_id) as rated_songs
                    FROM songs s
                    LEFT JOIN reactions r ON s.id = r.song_id AND r.user = ?
                    WHERE s.user != ?
                """,
                    (user_id, user_id),
                )
                rating_data = cursor.fetchone()
                total_rateable = rating_data["total_rateable_songs"]
                rated = rating_data["rated_songs"]
                rating_percentage = (rated / total_rateable * 100) if total_rateable > 0 else 0

                return {
                    "songs_submitted": songs_submitted,
                    "ratings_given": ratings_given,
                    "avg_rating_given": avg_rating_given,
                    "avg_rating_received": avg_rating_received,
                    "rating_percentage": rating_percentage,
                    "total_rateable_songs": total_rateable,
                    "songs_rated": rated,
                }

            except sqlite3.Error as e:
                logger.error("Error fetching user statistics: %s", e)
                raise

    def get_user_top_songs(self, user_id: str, limit: int = 3) -> list:
        """
        Get the top-rated songs submitted by a user.

        Args:
            user_id (str): The Slack user ID.
            limit (int): Number of top songs to return.

        Returns:
            list: List of dictionaries containing top song details.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT 
                        s.id,
                        s.title,
                        s.album,
                        COALESCE(AVG(r.reaction), 0) AS average_rating,
                        COUNT(DISTINCT r.id) AS reaction_count,
                        GROUP_CONCAT(DISTINCT a.name) AS artists
                    FROM songs s
                    LEFT JOIN reactions r ON s.id = r.song_id
                    LEFT JOIN song_artists sa ON s.id = sa.song_id
                    LEFT JOIN artists a ON sa.artist_id = a.id
                    WHERE s.user = ?
                    GROUP BY s.id
                    HAVING reaction_count > 0
                    ORDER BY average_rating DESC, reaction_count DESC
                    LIMIT ?
                """,
                    (user_id, limit),
                )

                rows = cursor.fetchall()
                return [
                    {
                        "title": row["title"],
                        "artists": row["artists"].split(",") if row["artists"] else [],
                        "average_rating": row["average_rating"],
                        "reaction_count": row["reaction_count"],
                    }
                    for row in rows
                ]

            except sqlite3.Error as e:
                logger.error("Error fetching user top songs: %s", e)
                raise

    def get_user_top_artists(self, user_id: str, limit: int = 3) -> list:
        """
        Get the top artists based on songs submitted by a user.

        Args:
            user_id (str): The Slack user ID.
            limit (int): Number of top artists to return.

        Returns:
            list: List of dictionaries containing top artist details.
        """
        with sqlite3.connect(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            cursor = connection.cursor()
            try:
                cursor.execute(
                    """
                    SELECT 
                        a.name,
                        COUNT(DISTINCT s.id) AS song_count,
                        COALESCE(AVG(r.reaction), 0) AS average_rating
                    FROM artists a
                    JOIN song_artists sa ON a.id = sa.artist_id
                    JOIN songs s ON sa.song_id = s.id
                    LEFT JOIN reactions r ON s.id = r.song_id
                    WHERE s.user = ?
                    GROUP BY a.id, a.name
                    ORDER BY song_count DESC, average_rating DESC
                    LIMIT ?
                """,
                    (user_id, limit),
                )

                rows = cursor.fetchall()
                return [
                    {"name": row["name"], "song_count": row["song_count"], "average_rating": row["average_rating"]}
                    for row in rows
                ]

            except sqlite3.Error as e:
                logger.error("Error fetching user top artists: %s", e)
                raise
