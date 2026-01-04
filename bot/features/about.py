from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Placeholder for features coming soon (moved from app.py)."""
    try:
        query = update.callback_query
        await query.answer()

        msg = "Bu bot Təmkin Təmrazlı tərəfindən hazırlanmışdır.\n\nƏlaqə üçün: @tamkin_tamrazli.\n\n"
        msg += "UP THE CHELS!"

        keyboard = [[InlineKeyboardButton("◀️ Geri", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send an animated GIF as the about content. Delete the original inline message first when possible.
        gif_url = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExNnYzeDd0OWcyanQ3a2YwbW8xM21jdmQ5ZDVpNzkzdWgxeGRwcWhvMyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/rD7muVnfEQXKm3rvqN/giphy.gif"
        try:
            if hasattr(query, 'message') and query.message:
                # remove the inline message and send a new animation message to the chat
                chat_id = query.message.chat.id
                try:
                    await query.delete_message()
                except Exception:
                    # ignore deletion errors and continue
                    pass

                try:
                    await context.bot.send_animation(
                        chat_id=chat_id,
                        animation=gif_url,
                        caption=msg,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                except Exception:
                    # fallback to editing text if sending animation fails
                    await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=reply_markup, parse_mode='HTML')
            else:
                # No message object (inline message) - fall back to editing
                await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
        except Exception:
            logger.exception("Failed to send about animation, falling back to text")
    except Exception as e:
        logger.error("Error in about feature", exc_info=True)
    finally:
        return 0 