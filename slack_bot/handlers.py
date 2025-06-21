import re
import logging
from slack_bolt import App
from slack_bot.utils import extract_spotify_track_id, convert_emoji_to_number, format_leaderboard_table, format_unrated_songs_table, get_name_from_id
from spotify.api import fetch_track_details
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from database.database import SpotifyBotDatabase

logger = logging.getLogger(__name__)


def register_handlers(app: App, db: "SpotifyBotDatabase"):
    @app.message(re.compile(r"https://open\.spotify\.com/track/"))
    def handle_spotify_track_message(message, say):
        track_id = extract_spotify_track_id(message['text'])
        if not track_id:
            logger.warning("No valid Spotify track ID found in the message.")
            app.client.chat_postEphemeral(
                channel=message['channel'],
                text="No valid Spotify track ID found in the message.",
                user=message['user']
            )
            return

        # Fetch track details from Spotify API
        track_details = fetch_track_details(track_id)
        if not track_details:
            logger.error(f"Failed to fetch details for track ID: {track_id}")
            app.client.chat_postEphemeral(
                channel=message['channel'],
                text="Could not fetch track details. Please try again later.",
                user=message['user']
            )
            return

        # Generate a permalink for the current message
        try:
            permalink_response = app.client.chat_getPermalink(
                channel=message['channel'],
                message_ts=message['ts']
            )
            message_link = permalink_response.get('permalink', None)
        except Exception as e:
            logger.error(f"Failed to generate permalink for message: {e}")
            message_link = None

        # Check if the song already exists in the database
        existing_song = db.fetch_songs(song_id=track_details['id'])
        if existing_song:
            # If the song exists, check if the original message link is missing or needs updating
            original_message_link = existing_song.get('message_link')
            if not original_message_link and message_link:
                logger.info(f"Updating original message link for track ID: {track_id}")
                db.update_song_message_link(
                    song_id=track_details['id'],
                    message_link=message_link
                )
            app.client.chat_postEphemeral(
                channel=message['channel'],
                text="Track already exists in the database! 🎵\n"
                     f"{f'<{original_message_link or message_link}|View/rate the original message!>' if message_link else ''}",
                user=message['user']
            )
            return

        # Insert the song and its artists into the database
        db.insert_song_with_artists(
            song_id=track_details['id'],
            title=track_details['name'],
            album=track_details['album'],
            artists=track_details['artists'],
            user=message['user'],
            message_link=message_link
        )
        app.client.chat_postEphemeral(
            channel=message['channel'],
            text="Track details saved successfully! 🎶\n"
                 f"*Title:* {track_details['name']}\n"
                 f"*Album:* {track_details['album']}\n"
                 f"*Artists:* {', '.join(track_details['artists'])}\n"
                 f"*Release Date:* {track_details['release_date']}\n",
            user=message['user']
        )

    @app.event("reaction_added")
    def handle_reaction_added(event, say):
        """
        Handle emoji reactions to song messages.
        """
        reaction = event["reaction"]
        item = event["item"]
        user = event["user"]

        if reaction not in ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "keycap_ten"]:
            return

        if "ts" not in item or "channel" not in item:
            logger.warning("Invalid item structure in reaction event.")
            return

        channel = item["channel"]
        message_ts = item["ts"]

        # Fetch the message to which the reaction was added
        response = app.client.conversations_history(
            channel=channel,
            latest=message_ts,
            limit=1,
            inclusive=True
        )

        if not response["messages"]:
            logger.warning("No messages found in the conversation history.")
            return

        message = response["messages"][0]

        # Check if the message is a Spotify track message
        track_id = extract_spotify_track_id(message["text"])
        if not track_id:
            logger.warning("No valid Spotify track ID found in the message.")
            return

        # Fetch the track details from the database
        existing_song = db.fetch_songs(song_id=track_id)
        if not existing_song:
            logger.error(f"Track ID {track_id} not found in the database.")
            app.client.chat_postEphemeral(
                channel=channel,
                text="This song is not in the database. Please add it first.",
                user=user
            )
            return

        # Get the original message link from the database or create a permalink if not available
        # We care about the original message link as we only want to count reactions on the original message
        # and not on any subsequent messages which would cause conflicting scores.
        # If the original message link is not available, treat the current message as the original.
        original_message_link = existing_song.get('message_link')

        if not original_message_link:
            # Should not happen, but just in case
            logger.error(f"No original message link found for track ID {track_id}. This should not happen.")
            app.client.chat_postEphemeral(
                channel=channel,
                text="No original message link found for this song. Please add the song first.",
                user=user
            )
            return

        original_message_ts = original_message_link.split("/")[-1].replace("p", "")

        # Slack format is in seconds not milliseconds, so we need to normalise it.
        normalised_message_ts = message_ts.replace(".", "")
        if normalised_message_ts != original_message_ts:
            logger.warning(f"Reaction added to a different message than the original for track ID {track_id}.")
            app.client.chat_postEphemeral(
                channel=channel,
                text="Reactions can only be added to the original song message."
                f" Please react to the original message here: <{original_message_link}|View original message>.",
                user=user
            )
            return

        # Check if the user has already reacted to this song
        existing_reaction = db.fetch_reaction(
            song_id=track_id,
            user=user
        )
        if existing_reaction:
            logger.warning(f"User <@{user}> has already reacted to this song.")
            app.client.chat_postEphemeral(
                channel=channel,
                text=f"You have already reacted to this song. Please remove your previous reaction first.",
                user=user
            )
            return

        # Convert the emoji reaction to a numeric value
        numeric_value = convert_emoji_to_number(reaction)

        if not numeric_value > 0:
            logger.warning(f"Invalid reaction emoji: {reaction}")
            return

        db.insert_reaction(
            song_id=track_id,
            user=user,
            reaction=numeric_value
        )

    @app.event("reaction_removed")
    def handle_reaction_removed(event, say):
        """
        Handle removal of emoji reactions to song messages.
        """
        reaction = event["reaction"]
        item = event["item"]
        user = event["user"]

        if reaction not in ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "keycap_ten"]:
            return

        if "ts" not in item or "channel" not in item:
            logger.warning("Invalid item structure in reaction event.")
            return

        channel = item["channel"]
        message_ts = item["ts"]

        # Fetch the message to which the reaction was removed
        response = app.client.conversations_history(
            channel=channel,
            latest=message_ts,
            limit=1,
            inclusive=True
        )

        if not response["messages"]:
            logger.warning("No messages found in the conversation history.")
            return

        message = response["messages"][0]

        # Check if the message is a Spotify track message
        track_id = extract_spotify_track_id(message["text"])
        if not track_id:
            logger.warning("No valid Spotify track ID found in the message.")
            return

        # Fetch the track details from the database
        existing_song = db.fetch_songs(song_id=track_id)
        if not existing_song:
            logger.error(f"Track ID {track_id} not found in the database.")
            say("This song is not in the database. Please add it first.")
            return

        # Get the original message link from the database
        original_message_link = existing_song.get('message_link')
        if not original_message_link:
            logger.error(f"No original message link found for track ID {track_id}. This should not happen.")
            say("No original message link found for this song. Please add the song first.")
            return

        # Extract and normalize the timestamp from the original message link
        original_message_ts = original_message_link.split("/")[-1].replace("p", "")
        # Convert to floating-point format
        normalized_original_ts = f"{original_message_ts[:10]}.{original_message_ts[10:]}"

        # Compare the normalized timestamps
        if message_ts != normalized_original_ts:
            logger.warning(f"Reaction removed from a different message than the original for track ID {track_id}.")
            app.client.chat_postEphemeral(
                channel=channel,
                text="Reactions can only be removed from the original song message."
                f" Please remove your reaction from the original message here: <{original_message_link}|View original message>.",
                user=user
            )
            return

        # Convert the emoji reaction to a numeric value
        numeric_value = convert_emoji_to_number(reaction)
        if not numeric_value > 0:
            logger.warning(f"Invalid reaction emoji: {reaction}")
            return

        # Remove the reaction from the database
        db.remove_reaction(
            song_id=track_id,
            user=user,
        )

        song_title = existing_song.get('title', 'Unknown Song')
        app.client.chat_postEphemeral(
            channel=channel,
            text=f"Your reaction (:{reaction}:) has been removed from {song_title}.",
            user=user
        )

    @app.command("/ping")
    def handle_ping_command(ack, respond):
        logger.info("Ping command received")
        ack()
        respond("Pong!")

    @app.command("/leaderboard")
    def handle_leaderboard_command(ack, respond, command):
        """
        Handle the /leaderboard command to display the top-rated songs.
        """
        logger.info("Leaderboard command received")
        ack()

        args = command.get('text', '').strip().split()

        limit = args[0] if args and args[0].isdigit() else 10

        try:
            top_songs = db.get_top_songs(limit=int(limit))
            if not top_songs:
                respond("No songs found in the database.")
                return

            leaderboard_text = format_leaderboard_table(top_songs)

            respond(leaderboard_text)
        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}")
            respond("An error occurred while fetching the leaderboard. Please try again later.")

    @app.command("/unrated")
    def handle_unrated_command(ack, respond, command, say):
        """
        Handle the /unrated command to display songs that have not been rated by a user.
        """
        logger.info("Unrated command received")
        ack()

        # Get user specified in command text
        user = command.get('text', '').strip()
        if user:
            # Need just the UID part of the mention
            user_id = re.search(r"<@([A-Z0-9]+)\|", user)
            if user_id:
                user = user_id.group(1)
        else:
            # Default to the user who invoked the command
            user = command['user_id']

        user_name = get_name_from_id(user, app)
        try:
            unrated_songs = db.get_unrated_songs(user_id=user)
            if not unrated_songs:
                say(f"No unrated songs found for {user_name}.")
                return

            logger.info(f"Unrated songs for user {user_name}: {unrated_songs}")
            unrated_text = format_unrated_songs_table(unrated_songs, user_name)

            say(unrated_text)
        except Exception as e:
            logger.error(f"Error fetching unrated songs: {e}")
            respond("An error occurred while fetching your unrated songs. Please try again later.")

    @app.error
    def custom_error_handler(error, body, logger):
        logger.exception(f"Error: {error}")
        logger.info(f"Request body: {body}")
