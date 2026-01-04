#!/usr/bin/env python
# pylint: disable=unused-argument

import logging
import aiohttp
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import settings
from utils import get_supabase_client, track_user_activity
from bot.features.fixture import fixtures
from bot.features.league_table import league_table
from bot.features.recent_results import recent_results
from bot.features.players import players, player_info
from bot.features.about import about
from bot.features.live_stream import live_stream
from bot.service import *

if not settings.BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

# Create logs directory if it doesn't exist
log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Configure logging to both file and console
log_file = os.path.join(log_dir, 'bot.log')
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # Also log to console
    ]
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Stages
START_ROUTES, END_ROUTES = range(2)

# Allowed groups/channels (replace with your actual group IDs)
ALLOWED_GROUPS = [
    # Add your group/channel IDs here
    # To find your group ID:
    # 1. Add @RawDataBot to your group
    # 2. Send any message in the group
    # 3. Copy the chat.id number from the bot's response
    # 4. Add it to this list (negative numbers for groups/channels)
    # -1001234567890,  # Example group ID
    # -1009876543210,  # Another group ID
    # 
    # For now, bot will work everywhere. Add actual group IDs to restrict.
]

async def check_group_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the bot should respond in this chat"""
    # Handle MockUpdate objects (from command handlers)
    if hasattr(update, 'callback_query') and hasattr(update.callback_query, 'message'):
        # This is a mock update from command handlers, allow it
        return True
    
    # Handle real updates
    if not hasattr(update, 'effective_chat') or not update.effective_chat:
        return False
    
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    
    # If no specific groups are configured, allow all groups
    if not ALLOWED_GROUPS:
        return True
    
    # Check if it's an allowed group/channel
    if chat_id in ALLOWED_GROUPS:
        return True
    
    # If not allowed, ignore silently
    logger.info(f"Access denied for chat {chat_id} ({chat_type})")
    return False


async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle when bot is mentioned"""
    # Check if bot should respond in this chat
    if not await check_group_access(update, context):
        return
    
    if update.message and update.message.text:
        # Check if the bot is mentioned in the message
        if "@cfcaz_bot" in update.message.text.lower():
            # Show the main menu
            await start(update, context)


@track_user_activity
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send message on `/start`."""
    # Group access check temporarily disabled since ALLOWED_GROUPS is empty
    # if not await check_group_access(update, context):
    #     return START_ROUTES
    
    user = update.message.from_user
    logger.info(f"User {user.id} ({user.first_name} {user.last_name or ''}) started the conversation.")
    
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
    
    welcome_msg = f"**Salam, {user.first_name}!**\n\n"
    welcome_msg += "Nə görmək istəyirsiniz?\n\n"
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
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
    
    msg = "CHELSEA-nin ölkəmizdəki azərkeşləri üçün hazırlanmış bot\n\n"
    msg += "Nə görmək istəyirsiniz?"
    
    # Check if the current message has a photo (coming from photo message)
    try:
        # If message has text, try to edit it
        if getattr(query.message, 'text', None):
            await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            # Message has no text (could be photo/animation); delete and send a new text message
            try:
                await query.delete_message()
            except Exception:
                pass
            await context.bot.send_message(text=msg, chat_id=query.message.chat.id, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error updating main menu message: {e}")
        # Fallback: ensure there's a visible text message
        try:
            await query.delete_message()
        except Exception:
            pass
        await context.bot.send_message(text=msg, chat_id=query.message.chat.id, reply_markup=reply_markup, parse_mode='Markdown')
    return START_ROUTES


def main() -> None:
    """Run the bot with webhook for Render deployment."""
    application = Application.builder().token(settings.BOT_TOKEN).build()

    # Command handlers for direct access to services
    async def cmd_calendar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /calendar command"""
        # await update.message.reply_text("⏳ Yüklənir...", reply_markup=None)
        
        # Create a simple mock query that works with reply_text
        class MockQuery:
            def __init__(self, message):
                self.data = 'Təqvim'
                self.message = message
            
            async def answer(self, *args, **kwargs):
                pass
            
            async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
                await self.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        
        mock_update = type('MockUpdate', (), {
            'callback_query': MockQuery(update.message)
        })()
        
        await fixtures(mock_update, context)
        return START_ROUTES

    async def cmd_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /table command"""
        # await update.message.reply_text("⏳ Yüklənir...", reply_markup=None)
        
        class MockQuery:
            def __init__(self, message):
                self.data = 'table'
                self.message = message
            
            async def answer(self, *args, **kwargs):
                pass
            
            async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
                await self.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        
        mock_update = type('MockUpdate', (), {
            'callback_query': MockQuery(update.message)
        })()
        
        await league_table(mock_update, context)
        return START_ROUTES

    async def cmd_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /results command"""
        # await update.message.reply_text("⏳ Yüklənir...", reply_markup=None)
        
        class MockQuery:
            def __init__(self, message):
                self.data = 'results'
                self.message = message
            
            async def answer(self, *args, **kwargs):
                pass
            
            async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
                await self.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        
        mock_update = type('MockUpdate', (), {
            'callback_query': MockQuery(update.message)
        })()
        
        await recent_results(mock_update, context)
        return START_ROUTES

    async def cmd_players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /players command"""
        # await update.message.reply_text("⏳ Yüklənir...", reply_markup=None)
        
        class MockQuery:
            def __init__(self, message):
                self.data = 'players'
                self.message = message
            
            async def answer(self, *args, **kwargs):
                pass
            
            async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
                await self.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        
        mock_update = type('MockUpdate', (), {
            'callback_query': MockQuery(update.message)
        })()
        
        await players(mock_update, context)
        return START_ROUTES

    async def cmd_live(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /live command"""
        # await update.message.reply_text("⏳ Yüklənir...", reply_markup=None)
        
        class MockQuery:
            def __init__(self, message):
                self.data = 'live'
                self.message = message
            
            async def answer(self, *args, **kwargs):
                pass
            
            async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
                await self.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
        
        mock_update = type('MockUpdate', (), {
            'callback_query': MockQuery(update.message)
        })()
        
        await live_stream(mock_update, context)
        return START_ROUTES

    async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /about command"""
        # await update.message.reply_text("⏳ Yüklənir...", reply_markup=None)
        class MockQuery:
            def __init__(self, message):
                self.data = 'about'
                self.message = message

            async def answer(self, *args, **kwargs):
                pass

            async def edit_message_text(self, text, reply_markup=None, parse_mode=None):
                await self.message.reply_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)

        mock_update = type('MockUpdate', (), {
            'callback_query': MockQuery(update.message)
        })()

        await about(mock_update, context)
        return START_ROUTES

    async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handle /help command - show all available commands"""
        # Check if bot should respond in this chat
        if not await check_group_access(update, context):
            return
        
        help_text = (
            "🤖 <b>CFC Azerbaijan Bot</b>\n\n"
            "📋 <b>Özəlliklər</b>\n\n"
            "🏠 /start - Əsas menyu\n"
            "❓ /komek - Özəlliklərin siyahısı\n\n"
            "📅 /teqvim - Oyun təqvimi\n"
            "📊 /cedvel - Turnir cədvəli\n"
            "⚽ /hesablar - Son nəticələr\n"
            "👥 /komanda - Oyunçular\n"
            "📺 /canli - Canlı yayım\n"
            "ℹ️ /haqqinda - Haqqında\n\n"
            "💡 <b>Məsləhət:</b> Əmrləri yazmaq üçün / işarəsindən istifadə edin!"
        )
        
        keyboard = [
            [InlineKeyboardButton("🏠 Ana Menyu", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text=help_text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return START_ROUTES

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
        ],
        states={
            START_ROUTES: [
                CallbackQueryHandler(fixtures, pattern="^Təqvim(_page_\\d+)?$"),
                CallbackQueryHandler(league_table, pattern="^table(_cl)?$"),
                CallbackQueryHandler(recent_results, pattern="^results(_page_\\d+)?$"),
                CallbackQueryHandler(players, pattern="^players(_page_\\d+)?$"),
                CallbackQueryHandler(back_to_main, pattern="^back_main$"),
                CallbackQueryHandler(live_stream, pattern="^live$"),
                CallbackQueryHandler(about, pattern="^(news|tickets|about|stats)$"),
                CallbackQueryHandler(player_info, pattern=".*")  # Catch-all for player IDs
            ]
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    
    # Add command handlers separately to work independently
    application.add_handler(CommandHandler("komek", cmd_help))
    application.add_handler(CommandHandler("teqvim", cmd_calendar))
    application.add_handler(CommandHandler("cedvel", cmd_table))
    application.add_handler(CommandHandler("hesablar", cmd_results))
    application.add_handler(CommandHandler("komanda", cmd_players))
    application.add_handler(CommandHandler("canli", cmd_live))
    application.add_handler(CommandHandler("haqqinda", cmd_about))
    
    # Add inline query handler for channel usage
    # application.add_handler(InlineQueryHandler(inline_query_handler))
    
    # Add mention handler for automatic bot activation
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mention))
    
    # Add callback handlers outside conversation for commands
    application.add_handler(CallbackQueryHandler(fixtures, pattern="^Təqvim(_page_\\d+)?$"))
    application.add_handler(CallbackQueryHandler(league_table, pattern="^table(_cl)?$"))
    application.add_handler(CallbackQueryHandler(recent_results, pattern="^results(_page_\\d+)?$"))
    application.add_handler(CallbackQueryHandler(players, pattern="^players(_page_\\d+)?$"))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_main$"))
    application.add_handler(CallbackQueryHandler(live_stream, pattern="^live$"))
    application.add_handler(CallbackQueryHandler(about, pattern="^(news|tickets|about|stats)$"))
    application.add_handler(CallbackQueryHandler(player_info, pattern=".*"))  # Catch-all for player IDs
    
    application.add_handler(conv_handler)

    webhook_url = os.environ.get("WEBHOOK_URL")
    debug = os.environ.get("DEBUG", "0") == "0"
    if debug:
        # Webhook mode (for Render or production)
        port = int(os.environ.get("PORT", 8080))
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url,
            allowed_updates=Update.ALL_TYPES
        )
    else:
        # Polling mode (for local development)
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()