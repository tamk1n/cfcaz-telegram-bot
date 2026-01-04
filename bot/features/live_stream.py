from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
import logging

from utils import get_supabase_client




async def live_stream(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show live stream information and links from admin panel."""
    logger = logging.getLogger(__name__)
    query = update.callback_query
    await query.answer()

    # Load active match links from Supabase
    active_links = []

    try:
        supabase_client = get_supabase_client()
        response = supabase_client.table("Matches").select("*").eq("is_active", True).execute()
        active_links = response.data
    except Exception as e:
        logger.error(f"Error loading match links from Supabase: {e}")

    msg = ''
    # Build message
    if active_links:
        msg = "<b>Canlı yayım linkləri</b>\n"
        # Build keyboard with match links
        keyboard = []
        for link in active_links:
            match_title = link.get('match_title', 'Oyun')
            language = link.get('language', 'az')
            stream_url = link.get('stream_url', '')

            language_choices = {
                'az': 'Azərbaycan',
                'en': 'İngilis',
                'ru': 'Rus',
                'tr': 'Türk',
                'other': 'Başqa dil'
            }

            button_text = f"{match_title} || Dil: {language_choices.get(language, 'Başqa dil')}"

            keyboard.append([InlineKeyboardButton(button_text, url=stream_url)])
    else:
        msg += "💡 <b>Məlumat:</b>\n"
        msg += "• Hal-hazırda aktiv canlı yayım linki yoxdur.\n"
        msg += "• Oyun günü yenidən yoxlayın.\n\n"

        # Default button
        keyboard = [
            [InlineKeyboardButton("📺 İdman TV", url="https://yodaplayer.yodacdn.net/idmanpop/index.php")]
        ]

    # Navigation buttons
    keyboard.append([
        InlineKeyboardButton("◀️ Geri", callback_data="back_main"),
        InlineKeyboardButton("🔄 Yenilə", callback_data="live")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
    except Exception:
        # If message cannot be edited (e.g., original was media), delete and send
        try:
            if hasattr(query, 'message') and query.message:
                await query.delete_message()
                await context.bot.send_message(chat_id=query.message.chat.id, text=msg, reply_markup=reply_markup, parse_mode='HTML')
        except Exception:
            logger.exception('Failed to deliver live_stream message')

    return 0
