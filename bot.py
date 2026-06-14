
# Let's create the complete fixed bot.py file

fixed_code = '''import os
import sys
import uuid
import asyncio


def ensure_project_python():
    venv_python = os.path.join(os.path.dirname(__file__), '.venv', 'Scripts', 'python.exe')

    if os.name != 'nt' or not os.path.exists(venv_python):
        return

    current_python = os.path.normcase(os.path.abspath(sys.executable))
    target_python = os.path.normcase(os.path.abspath(venv_python))

    if current_python != target_python:
        print('Switching to the project virtual environment...')
        os.execv(venv_python, [venv_python, __file__, *sys.argv[1:]])


ensure_project_python()

if "--check-env" in sys.argv:
    print(sys.executable)
    raise SystemExit(0)

import httpx
import requests
from requests import RequestException
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, Conflict, NetworkError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

BOT_TOKEN = "8827992749:AAHDaTfg4j3YYl2tLKlY3UtzCAeApMq7ing"
TMDB_API_KEY = "e866bf0ee2ed248272cd10e04ce40bbc"
CHANNEL_ID = "@calamares12"

movies = {}
file_id_map = {}
NETWORK_WARNING_SHOWN = False


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    update_obj = update if isinstance(update, Update) else None

    print(f"=== ERROR DETAILS ===")
    print(f"Error type: {type(error).__name__}")
    print(f"Error message: {error}")
    print(f"Update type: {type(update).__name__}")
    if update_obj and update_obj.effective_chat:
        print(f"Chat ID: {update_obj.effective_chat.id}")
    print(f"=====================")

    if isinstance(error, Conflict):
        print("Telegram polling conflict: another bot instance is already running.")
        raise SystemExit(1)

    if isinstance(error, BadRequest):
        print(f"Telegram API BadRequest: {error}")
        return

    if isinstance(error, (NetworkError, httpx.ConnectError, httpx.RequestError)):
        global NETWORK_WARNING_SHOWN
        message = "Telegram/network error: unable to reach Telegram or the movie service right now. Check your internet connection and try again."

        if not NETWORK_WARNING_SHOWN:
            print(f"Network error details: {error}")
            NETWORK_WARNING_SHOWN = True

        chat = update_obj.effective_chat if update_obj is not None else None
        if chat is not None:
            try:
                await context.bot.send_message(chat_id=chat.id, text=message)
            except Exception:
                pass
        return

    print(f"An error occurred while handling an update: {error}")


def search_movie(title):
    url = "https://api.themoviedb.org/3/search/movie"

    try:
        response = requests.get(
            url,
            params={
                "api_key": TMDB_API_KEY,
                "query": title,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except RequestException as exc:
        print(f"TMDB request failed: {exc}")
        return None

    if data.get("results"):
        return data["results"][0]

    return None


def search_movies(title, limit=5):
    """Search multiple movies from TMDB."""
    url = "https://api.themoviedb.org/3/search/movie"

    try:
        response = requests.get(
            url,
            params={
                "api_key": TMDB_API_KEY,
                "query": title,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except RequestException as exc:
        print(f"TMDB request failed: {exc}")
        return []

    return data.get("results", [])[:limit]


def get_movie_details(movie_id):
    """Get full movie details including genres, runtime, countries, etc."""
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"

    try:
        response = requests.get(
            url,
            params={
                "api_key": TMDB_API_KEY,
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except RequestException as exc:
        print(f"TMDB movie details request failed: {exc}")
        return None


def format_movie_caption(movie, detailed=False):
    """Format rich movie caption with all available details."""
    title = movie.get('title', 'Unknown')
    original_title = movie.get('original_title')
    year = movie.get('release_date', 'N/A')[:4] if movie.get('release_date') else 'N/A'
    rating = movie.get('vote_average', 'N/A')
    votes = movie.get('vote_count', 0)
    overview = movie.get('overview', 'No description available.')
    
    # Get runtime (in minutes)
    runtime = movie.get('runtime')
    if runtime:
        hours = runtime // 60
        mins = runtime % 60
        duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    else:
        duration_str = None
    
    # Get genres
    genres = movie.get('genres', [])
    if genres:
        genre_names = [g['name'] for g in genres]
        genre_str = ', '.join(genre_names)
    else:
        genre_str = None
    
    # Get production countries
    countries = movie.get('production_countries', [])
    if countries:
        country_names = [c['name'] for c in countries]
        country_str = ', '.join(country_names)
    else:
        country_str = None
    
    # Get spoken languages
    languages = movie.get('spoken_languages', [])
    if languages:
        lang_names = [l['english_name'] for l in languages if l.get('english_name')]
        if not lang_names:
            lang_names = [l['name'] for l in languages if l.get('name')]
        language_str = ', '.join(lang_names) if lang_names else None
    else:
        language_str = None
    
    # Get additional details
    status = movie.get('status')
    tagline = movie.get('tagline')
    budget = movie.get('budget')
    revenue = movie.get('revenue')
    original_language = movie.get('original_language', '').upper()
    popularity = movie.get('popularity')
    adult = movie.get('adult', False)
    imdb_id = movie.get('imdb_id')
    homepage = movie.get('homepage')
    
    # Build caption
    lines = [f"🎬 <b>{title}</b>"]
    
    if original_title and original_title != title:
        lines.append(f"📝 <i>{original_title}</i>")
    
    if tagline:
        lines.append(f"💬 {tagline}")
    
    lines.append("")  # spacer
    
    # Rating and votes
    if rating != 'N/A':
        stars = '⭐' * int(round(rating / 2)) if rating else '⭐'
        lines.append(f"{stars} <b>{rating}</b>/10 ({votes:,} votes)")
    
    # Year, duration, status
    info_parts = []
    if year != 'N/A':
        info_parts.append(f"📅 {year}")
    if duration_str:
        info_parts.append(f"⏱️ {duration_str}")
    if status:
        info_parts.append(f"📊 {status}")
    
    if info_parts:
        lines.append(" | ".join(info_parts))
    
    # Countries
    if country_str:
        lines.append(f"🌍 <b>Country:</b> {country_str}")
    
    # Languages
    if language_str:
        lines.append(f"🗣️ <b>Languages:</b> {language_str}")
    elif original_language:
        lines.append(f"🌐 <b>Original Language:</b> {original_language}")
    
    # Genres
    if genre_str:
        lines.append(f"🎭 <b>Genres:</b> {genre_str}")
    
    # Adult flag
    if adult:
        lines.append("🔞 <b>Adult Content</b>")
    
    # Popularity
    if popularity:
        lines.append(f"📈 Popularity: {popularity:.1f}")
    
    # Budget/Revenue (only for detailed)
    if detailed and budget and budget > 0:
        lines.append(f"💰 Budget: ${budget:,}")
    if detailed and revenue and revenue > 0:
        lines.append(f"💵 Revenue: ${revenue:,}")
    
    # IMDb ID
    if imdb_id:
        lines.append(f"🎞️ IMDb: <code>{imdb_id}</code>")
    
    # Homepage
    if homepage:
        lines.append(f"🔗 <a href='{homepage}'>Official Website</a>")
    
    lines.append("")  # spacer
    lines.append(f"{overview[:500]}{'...' if len(overview) > 500 else ''}")
    
    return "\\n".join(lines)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "🎬 <b>Movie Bot</b>\\n\\n"
        "Send me a video file and I'll look up the movie info on TMDB.\\n\\n"
        "<b>Commands:</b>\\n"
        "/search &lt;movie name&gt; - Search for a movie\\n"
        "/help - Show help",
        parse_mode="HTML"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "🎬 <b>Movie Bot Help</b>\\n\\n"
        "<b>Send a video</b> - I'll detect the movie and show info + send button.\\n\\n"
        "<b>Commands:</b>\\n"
        "/search &lt;movie name&gt; - Search TMDB for movies\\n"
        "/start - Start the bot\\n"
        "/help - Show this help\\n\\n"
        "Example: <code>/search Inception</code>",
        parse_mode="HTML"
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command."""
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a movie name.\\n\\n"
            "Example: <code>/search Inception</code>\\n"
            "Example: <code>/search The Matrix</code>",
            parse_mode="HTML"
        )
        return

    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 Searching for: <b>{query}</b>...", parse_mode="HTML")

    results = search_movies(query, limit=5)

    if not results:
        await update.message.reply_text("❌ No movies found.")
        return

    for movie in results:
        detailed = get_movie_details(movie.get('id'))
        if detailed:
            movie.update(detailed)
        
        poster_path = movie.get("poster_path")
        poster = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

        caption = format_movie_caption(movie, detailed=True)

        try:
            if poster:
                await update.message.reply_photo(
                    poster,
                    caption=caption,
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(caption, parse_mode="HTML")
        except Exception as e:
            print(f"Failed to send search result: {type(e).__name__}: {e}")
            await update.message.reply_text(caption, parse_mode="HTML")


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message is None:
        return

    video = message.video or message.document
    if video is None or video.file_name is None:
        await message.reply_text("Please send a video file.")
        return

    filename = video.file_name
    title = os.path.splitext(filename)[0]
    print(f"Processing video: {filename}, searching TMDB for: {title}")

    movie = search_movie(title)
    print(f"TMDB result: {movie is not None}")

    if not movie:
        await message.reply_text("Movie not found.")
        return

    file_id = video.file_id
    print(f"File ID length: {len(file_id)} chars")

    if file_id is None:
        await message.reply_text("This video cannot be sent right now.")
        return

    short_id = str(uuid.uuid4())[:8]
    movies[short_id] = movie
    file_id_map[short_id] = file_id
    print(f"Short ID: {short_id}")

    detailed = get_movie_details(movie.get('id'))
    if detailed:
        movie.update(detailed)

    poster_path = movie.get("poster_path")
    print(f"Poster path: {poster_path}")

    poster = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
    print(f"Poster URL: {poster}")

    caption = format_movie_caption(movie, detailed=True)

    keyboard = [
        [InlineKeyboardButton("📤 Send To Channel", callback_data=short_id)]
    ]

    try:
        if poster:
            await message.reply_photo(
                poster,
                caption=caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
        else:
            await message.reply_text(
                caption,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"Failed to send reply: {type(e).__name__}: {e}")
        await message.reply_text("Error sending movie info. Please try again.")


async def send_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return

    await query.answer()

    short_id = query.data
    if not short_id:
        return

    print(f"Callback received, short_id: {short_id}")

    movie = movies.get(short_id)
    file_id = file_id_map.get(short_id)

    if movie is None or file_id is None:
        await query.edit_message_caption("This movie is no longer available.")
        return

    poster_path = movie.get("poster_path")
    poster = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None

    caption = format_movie_caption(movie, detailed=True)

    try:
        if poster:
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=poster,
                caption=caption,
                parse_mode="HTML",
            )
        else:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=caption,
                parse_mode="HTML",
            )

        await context.bot.send_video(
            chat_id=CHANNEL_ID,
            video=file_id,
            caption=f"🎥 {movie.get('title', 'Unknown')}",
        )
    except (NetworkError, httpx.RequestError, httpx.ConnectError) as exc:
        print(f"Telegram send failed: {exc}")
        await query.edit_message_caption(
            "Failed to send the movie to the channel. Please check your Telegram connection and try again."
        )
        return

    movies.pop(short_id, None)
    file_id_map.pop(short_id, None)

    await query.edit_message_caption("Movie sent successfully.")


# FIX: Removed HTTPXRequest import and custom request - use default for v21+
app = (
    Application.builder()
    .token(BOT_TOKEN)
    .build()
)

app.add_handler(CommandHandler("start", start_command))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("search", search_command))

app.add_handler(
    MessageHandler(
        filters.VIDEO | filters.Document.VIDEO,
        handle_video
    )
)

app.add_handler(
    CallbackQueryHandler(send_to_channel)
)

app.add_error_handler(error_handler)

print("Bot running...")
print("The bot is now listening for video uploads and channel-send actions.")


async def run_bot():
    """Run the bot with manual async lifecycle management for Python 3.14 compatibility."""
    await app.initialize()
    await app.start()
    
    # Start polling
    await app.updater.start_polling(
        poll_interval=1.0,
        timeout=30,
        bootstrap_retries=1,
        drop_pending_updates=True,
    )
    
    # Keep the bot running until interrupted
    print("Bot is running. Press Ctrl+C to stop.")
    while True:
        await asyncio.sleep(3600)


def main():
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\\nStopping bot...")
        raise SystemExit(0)
    except Conflict:
        print("Telegram polling conflict: another bot instance is already running.")
        raise SystemExit(1)
    except NetworkError as exc:
        print(f"Telegram connection failed: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
'''

# Save to output
with open('/mnt/agents/output/bot.py', 'w') as f:
    f.write(fixed_code)

print("File saved successfully!")
print(f"File size: {len(fixed_code)} characters")
