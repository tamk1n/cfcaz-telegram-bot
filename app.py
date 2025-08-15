#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""Simple inline keyboard bot with multiple CallbackQueryHandlers.

This Bot uses the Application class to handle the bot.
First, a few callback functions are defined as callback query handler. Then, those functions are
passed to the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.
Usage:
Example of a bot that uses inline keyboard that has multiple CallbackQueryHandlers arranged in a
ConversationHandler.
Send /start to initiate the conversation.
Press Ctrl-C on the command line to stop the bot.
"""
import logging
import aiohttp
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHELSEA_API_URL = os.getenv('CHELSEA_API_URL', 'https://www.chelseafc.com/en/api/fixtures/upcoming?pageId=30EGwHPO9uwBCc75RQY6kg')

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Stages
START_ROUTES, END_ROUTES = range(2)
# Callback data
ONE, TWO, THREE, FOUR = range(4)

WEEKDAYS = {
    "Sun": "Bazar",
    "Mon": "Bazar e.",
    "Tue": "Çərşənbə a.",
    "Wed": "Çərşənbə",
    "Thu": "Cümə a.",
    "Fri": "Cümə",
    "Sat": "Şənbə"
}

MONTHS = {
    "Jan": "Yanvar",
    "Feb": "Fevral",
    "Mar": "Mart",
    "Apr": "Aprel",
    "May": "May",
    "Jun": "İyun",
    "Jul": "İyul",
    "Aug": "Avqust",
    "Sep": "Sentyabr",
    "Oct": "Oktyabr",
    "Nov": "Noyabr",
    "Dec": "Dekabr"
}

def convert_to_azerbaijan_time(date_str, time_str):
    """Convert match date and time to Azerbaijan timezone (+4)"""
    try:
        # Parse the date string (e.g., "Sun 17 Aug 2025")
        parts = date_str.split()
        day_name = parts[0]
        day = int(parts[1])
        month = parts[2]
        year = int(parts[3])
        
        # Parse time (e.g., "14:00")
        hour, minute = map(int, time_str.split(':'))
        
        # Create datetime object (assuming UTC)
        dt = datetime(year, list(MONTHS.keys()).index(month) + 1, day, hour, minute)
        
        # Add 4 hours for Azerbaijan timezone
        az_dt = dt + timedelta(hours=4)
        
        # Format in Azerbaijani
        az_day_name = WEEKDAYS.get(day_name, day_name)
        az_month = MONTHS.get(month, month)
        
        formatted_date = f"{az_day_name} {az_dt.day} {az_month} {az_dt.year}"
        formatted_time = f"{az_dt.hour:02d}:{az_dt.minute:02d}"
        
        return formatted_date, formatted_time
    except Exception:
        # Fallback to original if parsing fails
        return date_str, time_str



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send message on `/start`."""
    user = update.message.from_user
    logger.info("User %s started the conversation.", user.first_name)
    
    # Beautiful main menu with multiple options
    keyboard = [
        [
            InlineKeyboardButton("📅 Təqvim", callback_data="Təqvim"),
            InlineKeyboardButton("📊 Cədvəl", callback_data="table")
        ],
        [
            InlineKeyboardButton("⚽ Son Nəticələr", callback_data="results"),
            InlineKeyboardButton("👥 Oyunçular", callback_data="players")
        ],
        [
            InlineKeyboardButton("📺 Canlı Yayım", callback_data="live"),
            InlineKeyboardButton("ℹ️ Haqqında", callback_data="about")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_msg = f"🔵 **Xoş gəlmisiniz {user.first_name}!** 🔵\n\n"
    welcome_msg += "Nə görmək istəyirsiniz?\n\n"
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
    return START_ROUTES


async def fixtures(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Request Chelsea API and show beautiful fixture list with pagination."""
    query = update.callback_query
    await query.answer()
    
    # Get page number from callback data or default to 1
    page = 1
    if '_page_' in query.data:
        page = int(query.data.split('_page_')[1])
    
    async with aiohttp.ClientSession() as session:
        async with session.get(CHELSEA_API_URL) as resp:
            if resp.status == 200:
                data = await resp.json()
                try:
                    # Get all matches
                    all_matches = []
                    for item in data['items']:
                        for match in item['items']:
                            all_matches.append(match)
                    
                    # Pagination settings
                    matches_per_page = 3
                    total_matches = len(all_matches)
                    total_pages = (total_matches + matches_per_page - 1) // matches_per_page
                    
                    # Get matches for current page
                    start_idx = (page - 1) * matches_per_page
                    end_idx = start_idx + matches_per_page
                    page_matches = all_matches[start_idx:end_idx]
                    
                    msg = "🔵 **CHELSEA FC** 🔵\n"
                    msg += "═" * 25 + "\n"
                    msg += f"📅 **Qarşıdakı Oyunlar** (Səhifə {page}/{total_pages})\n\n"
                    
                    for i, match in enumerate(page_matches, start_idx + 1):
                        m = match['matchUp']
                        home = m['home']['clubShortName']
                        away = m['away']['clubShortName']
                        date = match['kickoffDate']
                        time = match['kickoffTime']
                        venue = match['venue']
                        comp = match['competition']
                        
                        # Convert to Azerbaijan timezone (+4)
                        az_date, az_time = convert_to_azerbaijan_time(date, time)
                        
                        # Add match status indicators
                        status_icon = "🟢" if not match.get('tbc', False) else "🟡"
                        home_icon = "🏠" if m['isHomeFixture'] else "✈️"
                        
                        msg += f"{status_icon} **Oyun {i}**\n"
                        msg += f"⚽ {home} vs {away}\n"
                        msg += f"{home_icon} {venue}\n"
                        msg += f"🏆 {comp}\n"
                        msg += f"📅 {az_date} - ⏰ {az_time}\n"
                        msg += "─" * 20 + "\n\n"
                    
                    # Create pagination buttons
                    keyboard = []
                    
                    # Navigation row
                    nav_row = []
                    if page > 1:
                        nav_row.append(InlineKeyboardButton("⬅️ Əvvəlki", callback_data=f"Təqvim_page_{page-1}"))
                    if page < total_pages:
                        nav_row.append(InlineKeyboardButton("Növbəti ➡️", callback_data=f"Təqvim_page_{page+1}"))
                    if nav_row:
                        keyboard.append(nav_row)
                    
                    # Page indicator row
                    # if total_pages > 1:
                    #     page_indicators = []
                    #     for p in range(1, min(total_pages + 1, 6)):  # Show max 5 page numbers
                    #         if p == page:
                    #             page_indicators.append(InlineKeyboardButton(f"• {p} •", callback_data=f"Təqvim_page_{p}"))
                    #         else:
                    #             page_indicators.append(InlineKeyboardButton(str(p), callback_data=f"Təqvim_page_{p}"))
                    #     keyboard.append(page_indicators)
                    
                    # Action buttons
                    keyboard.extend([
                        [
                            InlineKeyboardButton("◀️ Geri", callback_data="back_main"),
                            InlineKeyboardButton("🔄 Yenilə", callback_data="Təqvim")
                        ]
                    ])
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                except Exception as e:
                    logger.error("Error parsing match data", exc_info=True)
                    msg = f"❌ Oyun məlumatları tapılmadı. Xəta: {str(e)}"
                    keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="Təqvim")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                msg = f"❌ Chelsea API xətası: {resp.status}"
                keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="Təqvim")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
    return START_ROUTES


async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to main menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [
            InlineKeyboardButton("📅 Təqvim", callback_data="Təqvim"),
            InlineKeyboardButton("📊 Cədvəl", callback_data="table")
        ],
        [
            InlineKeyboardButton("⚽ Son Nəticələr", callback_data="results"),
            InlineKeyboardButton("👥 Oyunçular", callback_data="players")
        ],
        [
            InlineKeyboardButton("📺 Canlı Yayım", callback_data="live"),
            InlineKeyboardButton("ℹ️ Haqqında", callback_data="about")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = "🔵 **CHELSEA FC** 🔵\n\n"
    msg += "Ana menyu - Nə görmək istəyirsiniz?"
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
    return START_ROUTES


async def coming_soon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Placeholder for features coming soon"""
    query = update.callback_query
    await query.answer()
    
    msg = "🚧 **Tezliklə** 🚧\n\n"
    msg += "Bu xüsusiyyət hazırda inkişaf mərhələsindədir.\n"
    msg += "Tezliklə əlavə olunacaq! 🔄"
    
    keyboard = [[InlineKeyboardButton("◀️ Geri", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
    return START_ROUTES



def main() -> None:
    """Run the bot with webhook for Render deployment."""
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            START_ROUTES: [
                CallbackQueryHandler(fixtures, pattern="^Təqvim(_page_\\d+)?$"),
                CallbackQueryHandler(back_to_main, pattern="^back_main$"),
                CallbackQueryHandler(coming_soon, pattern="^(table|results|players|news|tickets|live|about|stats)$")
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )
    application.add_handler(conv_handler)

    # Webhook settings for Render
    port = int(os.environ.get("PORT", 8080))
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("WEBHOOK_URL environment variable is required for webhook deployment.")

    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        webhook_url=webhook_url,
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()