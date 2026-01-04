import logging
import settings

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from bot.service import fetch_with_cache
from utils import convert_to_azerbaijan_time


async def fixtures(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Request Chelsea API and show beautiful fixture list with pagination."""
    logger = logging.getLogger(__name__)

    # Group access check temporarily disabled since ALLOWED_GROUPS is empty
    # if not await check_group_access(update, context):
    #     return START_ROUTES
    
    query = update.callback_query
    await query.answer()
    
    # Get page number from callback data or default to 1
    page = 1
    if '_page_' in query.data:
        page = int(query.data.split('_page_')[1])

    # Fetch data with intelligent caching
    result = await fetch_with_cache(url=settings.CHELSEA_API_URL, cache_key="fixtures", max_age_hours=settings.FIXTURES_CACHE_HOURS)

    if result["success"]:
        try:
            data = result["data"]

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
            
            msg = "<b>Qarşıdakı Oyunlar</b>\n"
            msg += "═" * 25 + "\n\n"
            msg += f"📅 Səhifə {page}/{total_pages}\n\n"
            
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
                
                msg += f"{status_icon} <b>Oyun {i}</b>\n"
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
            msg = f"❌ Oyun məlumatları emal edilə bilmədi."
            if result["source"] == "cache":
                msg += " Keş məlumatları işlənmədi."
            keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="Təqvim")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        # Both API and cache failed
        msg = "❌ **Oyun Təqvimi Əlçatan Deyil**\n\n"
        msg += "⚠️ Hal-hazırda oyun məlumatlarına çatmaq mümkün deyil.\n\n"
        msg += "💡 **Səbəblər:**\n"
        msg += "• Chelsea FC saytında texniki problemlər\n"
        msg += "• Internet əlaqə problemi\n"
        msg += "• Server yüklənməsi\n\n"
        msg += "🔄 Xahiş edirik, bir neçə dəqiqə sonra yenidən cəhd edin."
        
        keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="Təqvim")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
    # START_ROUTES is 0 in the main app (START_ROUTES, END_ROUTES = range(2))
    return 0