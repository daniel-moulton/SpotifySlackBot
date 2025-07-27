"""Handlers for Slack bot events and commands related to Spotify tracks."""

import re
import logging
from typing import TYPE_CHECKING
from slack_bolt import App
from slack_bot.utils import (
    extract_spotify_track_id,
    convert_emoji_to_number,
    format_leaderboard_table,
    format_unrated_songs_table,
    get_name_from_id,
    get_user_id,
    handle_song_stats,
    is_valid_spotify_id,
    parse_command_arguments,
    send_response,
    verify_user_exists,
)
from spotify.api import fetch_track_details

if TYPE_CHECKING:
    from database.database import SpotifyBotDatabase

logger = logging.getLogger(__name__)


def register_handlers(app: App, db: "SpotifyBotDatabase"):
    """Register event handlers for the Slack app."""

    @app.message(re.compile(r"https://open\.spotify\.com/track/"))
    def handle_spotify_track_message(message) -> None:
        track_id = extract_spotify_track_id(message["text"])
        if not track_id:
            logger.warning("No valid Spotify track ID found in the message.")
            app.client.chat_postEphemeral(
                channel=message["channel"],
                text="No valid Spotify track ID found in the message.",
                user=message["user"],
            )
            return

        # Fetch track details from Spotify API
        track_details = fetch_track_details(track_id)
        if not track_details:
            logger.error("Failed to fetch details for track ID: %s", track_id)
            app.client.chat_postEphemeral(
                channel=message["channel"],
                text="Could not fetch track details. Please try again later.",
                user=message["user"],
            )
            return

        # Generate a permalink for the current message
        try:
            permalink_response = app.client.chat_getPermalink(channel=message["channel"], message_ts=message["ts"])
            message_link = permalink_response.get("permalink", None)
        except Exception as e:
            logger.error("Failed to generate permalink for message: %s", e)
            message_link = None

        # Check if the song already exists in the database
        existing_song = db.fetch_songs(song_id=track_details["id"])
        if existing_song:
            # If the song exists, check if the original message link is missing or needs updating
            original_message_link = existing_song.get("message_link")
            if not original_message_link and message_link:
                logger.info("Updating original message link for track ID: %s", track_id)
                db.update_song_message_link(song_id=track_details["id"], message_link=message_link)
            link_text = ""
            if message_link:
                link_url = original_message_link or message_link
                link_text = f"<{link_url}|View/rate the original message!>"

            app.client.chat_postEphemeral(
                channel=message["channel"],
                text="Track already exists in the database! 🎵\n" + link_text,
                user=message["user"],
            )

        # Insert the song and its artists into the database
        db.insert_song_with_artists(
            song_id=track_details["id"],
            title=track_details["name"],
            album=track_details["album"],
            artists=track_details["artists"],
            user=message["user"],
            message_link=message_link,
        )
        app.client.chat_postEphemeral(
            channel=message["channel"],
            text="Track details saved successfully! 🎶\n"
            f"*Title:* {track_details['name']}\n"
            f"*Album:* {track_details['album']}\n"
            f"*Artists:* {', '.join(artist['name'] for artist in track_details['artists'])}\n"
            f"*Release Date:* {track_details['release_date']}\n",
            user=message["user"],
        )

    @app.event("message")
    def handle_message() -> None:
        """Ignore any messages that don't contain a Spotify track link, reduce log spam"""

    @app.event("reaction_added")
    def handle_reaction_added(event) -> None:
        """
        Handle emoji reactions to song messages.
        """
        reaction = event["reaction"]
        item = event["item"]
        user = event["user"]

        if reaction not in [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "keycap_ten",
        ]:
            return

        if "ts" not in item or "channel" not in item:
            logger.warning("Invalid item structure in reaction event.")
            return

        channel = item["channel"]
        message_ts = item["ts"]

        # Fetch the message to which the reaction was added
        response = app.client.conversations_history(channel=channel, latest=message_ts, limit=1, inclusive=True)

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
            logger.error("Track ID %s not found in the database.", track_id)
            app.client.chat_postEphemeral(
                channel=channel,
                text="This song is not in the database. Please add it first.",
                user=user,
            )
            return

        # Get the original message link from the database or create a permalink if not available
        # We care about the original message link as we only want to count reactions on the original message
        # and not on any subsequent messages which would cause conflicting scores.
        # If the original message link is not available, treat the current message as the original.
        original_message_link = existing_song.get("message_link")

        if not original_message_link:
            # Should not happen, but just in case
            logger.error("No original message link found for track ID %s. This should not happen.", track_id)
            app.client.chat_postEphemeral(
                channel=channel,
                text="No original message link found for this song. Please add the song first.",
                user=user,
            )
            return

        original_message_ts = original_message_link.split("/")[-1].replace("p", "")

        # Slack format is in seconds not milliseconds, so we need to normalise it.
        normalised_message_ts = message_ts.replace(".", "")
        if normalised_message_ts != original_message_ts:
            logger.warning("Reaction added to a different message than the original for track ID %s.", track_id)
            app.client.chat_postEphemeral(
                channel=channel,
                text="Reactions can only be added to the original song message."
                f" Please react to the original message here: <{original_message_link}|View original message>.",
                user=user,
            )
            return

        # Check if the user has already reacted to this song
        existing_reaction = db.fetch_reaction(song_id=track_id, user=user)
        if existing_reaction:
            logger.warning("User <@%s> has already reacted to this song.", user)
            app.client.chat_postEphemeral(
                channel=channel,
                text="You have already reacted to this song. Please remove your previous reaction first.",
                user=user,
            )
            return

        # Convert the emoji reaction to a numeric value
        numeric_value = convert_emoji_to_number(reaction)

        if not numeric_value > 0:
            logger.warning("Invalid reaction emoji: %s", reaction)
            return

        db.insert_reaction(song_id=track_id, user=user, reaction=numeric_value)

    @app.event("reaction_removed")
    def handle_reaction_removed(event, say) -> None:
        """
        Handle removal of emoji reactions to song messages.
        """
        reaction = event["reaction"]
        item = event["item"]
        user = event["user"]

        if reaction not in [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "keycap_ten",
        ]:
            return

        if "ts" not in item or "channel" not in item:
            logger.warning("Invalid item structure in reaction event.")
            return

        channel = item["channel"]
        message_ts = item["ts"]

        # Fetch the message to which the reaction was removed
        response = app.client.conversations_history(channel=channel, latest=message_ts, limit=1, inclusive=True)

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
            logger.error("Track ID %s not found in the database.", track_id)
            say("This song is not in the database. Please add it first.")
            return

        # Get the original message link from the database
        original_message_link = existing_song.get("message_link")
        if not original_message_link:
            logger.error("No original message link found for track ID %s. This should not happen.", track_id)
            say("No original message link found for this song. Please add the song first.")
            return

        # Extract and normalize the timestamp from the original message link
        original_message_ts = original_message_link.split("/")[-1].replace("p", "")
        # Convert to floating-point format
        normalized_original_ts = f"{original_message_ts[:10]}.{original_message_ts[10:]}"

        # Compare the normalized timestamps
        if message_ts != normalized_original_ts:
            logger.warning("Reaction removed from a different message than the original for track ID %s.", track_id)
            app.client.chat_postEphemeral(
                channel=channel,
                text="Reactions can only be removed from the original song message."
                f" Please remove your reaction from the original message here: "
                f"<{original_message_link}|View original message>.",
                user=user,
            )
            return

        # Convert the emoji reaction to a numeric value
        numeric_value = convert_emoji_to_number(reaction)
        if not numeric_value > 0:
            logger.warning("Invalid reaction emoji: %s", reaction)
            return

        # Fetch the existing reaction from the database
        existing_reaction = db.fetch_reaction(song_id=track_id, user=user)
        if not existing_reaction:
            logger.warning("No reaction found for user <@{user}> on song ID %s.", track_id)
            app.client.chat_postEphemeral(
                channel=channel,
                text="You have not reacted to this song yet.",
                user=user,
            )
            return

        # Check if the reaction matches the one being removed
        if existing_reaction != numeric_value:
            logger.warning(
                "Reaction mismatch for user <@%s> on song ID %s. Expected %s, got %s.",
                user,
                track_id,
                existing_reaction,
                numeric_value,
            )
            return

        # If the reaction matches, proceed to remove it
        db.remove_reaction(
            song_id=track_id,
            user=user,
        )

    @app.command("/ping")
    def handle_ping_command(ack, respond) -> None:
        """
        Handle the /ping command to respond with a Pong message.

        Quick health check command to ensure the bot is responsive.
        """
        logger.info("Ping command received")
        ack()
        respond("Pong!")

    @app.command("/leaderboard")
    def handle_leaderboard_command(ack, respond, command, say) -> None:
        """
        Handle the /leaderboard command to display the top-rated songs.

        Possible arguments:
        - `--public`: If set, the response will be visible to all users in the channel.
        - `--count <number>`: Specify the number of top songs to display (default is 10).
        """
        logger.info("Leaderboard command received")
        ack()

        command_text = command.get("text", "").strip()
        args = parse_command_arguments(command_text)

        is_public = args.get("public", False)
        count = args.get("count", "10")

        if not count.isdigit() or int(count) <= 0:
            respond("Invalid count specified. Please provide a positive integer.")
            return

        try:
            top_songs = db.get_top_songs(limit=int(count))
            if not top_songs:
                respond("No songs found in the database.")
                return

            leaderboard_text = format_leaderboard_table(top_songs)

            send_response(respond, say, leaderboard_text, is_public)
        except Exception as e:
            logger.error("Error fetching leaderboard: %s", e)
            respond("An error occurred while fetching the leaderboard. Please try again later.")

    @app.command("/unrated")
    def handle_unrated_command(ack, respond, command, say) -> None:
        """
        Handle the /unrated command to display songs that have not been rated by a user, excludes songs that user sent.

        Possible arguments:
        - `--public`: If set, the response will be visible to all users in the channel.
        - `--user <@U12345678>`: Specify a user to check for unrated songs.
            If not specified, defaults to the user who invoked the command.
        """
        logger.info("Unrated command received")
        ack()

        command_text = command.get("text", "").strip()
        args = parse_command_arguments(command_text)

        is_public = args.get("public", False)
        user = args.get("user", None)

        if user:
            # Need just the UID part of the mention
            user_id = get_user_id(user)
            if not user_id:
                respond("Invalid user mention format. Please use @username format.")
                return
            if not verify_user_exists(user_id, app):
                respond(f"User `{user_id}` does not exist or is not accessible.")
                return
        else:
            # Default to the user who invoked the command
            user_id = command["user_id"]

        # Get the user's display name
        user_name = get_name_from_id(user_id, app)
        if not user_name:
            respond("Could not find user information. Please try again later.")
            return

        try:
            unrated_songs = db.get_unrated_songs(user_id=user_id)
            if not unrated_songs:
                send_response(respond, say, f"No unrated songs found for {user_name}.", is_public)
                return

            logger.info("Unrated songs for user {user_name}: %s", unrated_songs)
            unrated_text = format_unrated_songs_table(unrated_songs, user_name)

            send_response(respond, say, unrated_text, is_public)
        except Exception as e:
            logger.error("Error fetching unrated songs: %s", e)
            respond("An error occurred while fetching your unrated songs. Please try again later.")

    @app.command("/stats")
    def handle_stats_command(ack, respond, command, say) -> None:
        """
        Handle the /stats command to display statistics about a song/user/artist.

        Possible arguments:
        - `--public`: If set, the response will be visible to all users in the channel.
        - `--user <@U12345678>`: Specify a user to check for statistics.
        - `--song <spotify_track_id | song_name>`: Specify a song to check for statistics.
        - `--artist <spotify_artist_id | artist_name>`: Specify an artist to check for statistics.
        """
        logger.info("Stats command received")
        ack()

        command_text = command.get("text", "").strip()
        args = parse_command_arguments(command_text)

        is_public = args.get("public", False)
        user = args.get("user", None)
        song = args.get("song", None)
        artist = args.get("artist", None)

        # Must be either song, artist, or user specified can't be more than one
        if sum([bool(user), bool(song), bool(artist)]) != 1:
            respond("Please specify exactly one of the following: --user, --song, or --artist.")
            return

        returned_text = ""

        if user:
            user_id = get_user_id(user)
            if not user_id:
                respond("Invalid user mention format. Please use @username format.")
                return
            if not verify_user_exists(user_id, app):
                respond(f"User `{user_id}` does not exist or is not accessible.")
                return

            # returned_text = handle_user_stats(user_id, app)

        elif song:
            # Check if the song argument is provided
            # TODO: Maybe needs refactoring (if we're here then we know the --song argument
            # is provided, but `--song --public` would still be valid)
            # If an actual song is provided, song will be a string, otherwise if it's another argument it will be True
            # Perhaps should have a whitelist in parse_command_arguments to decipher
            # between flags (--public) and actual arguments (--song, --user etc.)
            if song is True:
                respond("Please specify a song using the --song argument.")
                return
            # Check if the song is a Spotify track ID or a name
            track_id = extract_spotify_track_id(song)

            if not track_id and is_valid_spotify_id(song):
                # If it's a valid Spotify ID, use it directly
                track_id = song

            if not track_id:
                # If it's not a valid track ID, assume it's a song name
                matches = db.fetch_song_by_name(song)

                if not matches:
                    respond(f"No songs found with the name '{song}'.")
                    return

                # Only one match, can assume it's the song they want stats for
                if len(matches) == 1:
                    track_id = matches[0]["id"]

                # If multiple matches, ask for clarification
                else:
                    # Multiple matches, display the list of matching songs
                    match_list = "\n".join(
                        f"*{match['title']}* (Album: {match['album']}, ID: `{match['id']}`)" for match in matches
                    )
                    respond(
                        f"Multiple songs found matching '{song}'. "
                        f"Please refine your query or use one of the track IDs below:\n{match_list}"
                    )
                    return

            if not track_id:
                respond(f"No valid Spotify track ID or song name found for '{song}'.")
                return

            song_details = db.fetch_songs(song_id=track_id)
            reaction_details = db.fetch_reactions_for_track(song_id=track_id)

            if not song_details:
                respond(f"No song found with the ID '{track_id}'.")
                return

            returned_text = handle_song_stats(song_details, reaction_details, app)

        elif artist:
            # Check if the artist is a Spotify artist ID or a name
            artist_id = db.fetch_artist_id_by_name(artist)
            if not artist_id:
                respond(f"No artist found with the name '{artist}'.")
                return

            # returned_text = handle_artist_stats(artist_id, db)

        if returned_text:
            send_response(respond, say, returned_text, is_public)

    @app.error
    def custom_error_handler(error, body):
        logger.exception("Error: %s", error)
        logger.info("Request body: %s", body)
