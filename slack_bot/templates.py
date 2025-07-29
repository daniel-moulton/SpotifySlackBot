"""Template strings for Slack bot messages."""

SONG_STATS_TEMPLATE = """
*Song Details:*
🎵 {title} by {artists}
💿 {album} | 👤 {user_name} | 🕒 {message_time}
🔗 {message_link}

*Rating Stats:*
⭐ Average Rating: {average_rating} ({reaction_count} reactions)
👥 User Ratings:
{user_ratings}
"""

USER_STATS_TEMPLATE = """
*📊 Statistics for {user_name}*

*📈 Overview:*
• Songs submitted: {songs_submitted}
• Ratings given: {ratings_given}
• Songs rated: {songs_rated}/{total_rateable_songs} ({rating_percentage:.1f}%)
• Average rating given: {avg_rating_given:.1f}
• Average rating received: {avg_rating_received:.1f}

{top_songs_section}

{top_artists_section}"""