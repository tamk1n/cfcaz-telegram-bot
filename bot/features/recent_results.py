from bot.service import fetch_with_cache
from utils import convert_to_azerbaijan_time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
import logging
import settings


async def recent_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show recent match results with pagination."""
    logger = logging.getLogger(__name__)
    # Check if bot should respond in this chat
    # if not await check_group_access(update, context):
    #     return END_ROUTES
    

    query = update.callback_query
    await query.answer()
    
    # Get page number from callback data or default to 1
    page = 1
    if '_page_' in query.data:
        page = int(query.data.split('_page_')[1])
    
    # Fetch data with intelligent caching
    result = await fetch_with_cache(url=settings.RESULTS_API_URL, cache_key="recent_results", max_age_hours=settings.RESULTS_CACHE_HOURS)

    if result["success"]:
        try:
            data = result["data"]

            # Get all matches from all months
            all_matches = []
            
            # First, add the latest match if it exists
            if 'latestResult' in data and 'fixture' in data['latestResult']:
                latest_match = data['latestResult']['fixture']
                all_matches.append(latest_match)
            
            # Then add matches from items (but skip duplicates)
            for month_group in data['items']:
                for match in month_group['items']:
                    # Check if this match is already in the list (avoid duplicating latest match)
                    if not any(existing_match['id'] == match['id'] for existing_match in all_matches):
                        all_matches.append(match)
            
            # Pagination settings
            matches_per_page = 5
            total_matches = len(all_matches)
            total_pages = (total_matches + matches_per_page - 1) // matches_per_page
            
            # Get matches for current page
            start_idx = (page - 1) * matches_per_page
            end_idx = start_idx + matches_per_page
            page_matches = all_matches[start_idx:end_idx]
            
            msg = "<b>SON NƏTİCƏLƏR</b>\n"
            msg += "═" * 25 + "\n\n"
            msg += f"📋 Səhifə {page}/{total_pages}\n\n"
            
            for i, match in enumerate(page_matches, start_idx + 1):
                m = match['matchUp']
                home = m['home']['clubShortName']
                away = m['away']['clubShortName']
                home_score = m['home']['score']
                away_score = m['away']['score']
                date = match['kickoffDate']
                time = match['kickoffTime']
                venue = match['venue']
                comp = match['competition']
                
                # Convert to Azerbaijan timezone (+4)
                az_date, az_time = convert_to_azerbaijan_time(date, time)
                
                # Determine result icon
                if m['isHomeFixture']:
                    # Chelsea home
                    if home_score > away_score:
                        result_icon = "🟢"  # Win
                    elif home_score == away_score:
                        result_icon = "🟡"  # Draw
                    else:
                        result_icon = "🔴"  # Loss
                else:
                    # Chelsea away
                    if away_score > home_score:
                        result_icon = "🟢"  # Win
                    elif away_score == home_score:
                        result_icon = "🟡"  # Draw
                    else:
                        result_icon = "🔴"  # Loss
                
                home_icon = "🏠" if m['isHomeFixture'] else "✈️"
                
                msg += f"{result_icon} <b>Oyun {i}</b>\n"
                msg += f"⚽ {home} {home_score} - {away_score} {away}\n"
                msg += f"{home_icon} {venue}\n"
                msg += f"🏆 {comp}\n"
                msg += f"📅 {az_date} - ⏰ {az_time}\n"
                msg += "─" * 20 + "\n\n"
            
            # Create pagination buttons
            keyboard = []
            
            # Navigation row
            nav_row = []
            if page > 1:
                nav_row.append(InlineKeyboardButton("⬅️ Əvvəlki", callback_data=f"results_page_{page-1}"))
            if page < total_pages:
                nav_row.append(InlineKeyboardButton("Növbəti ➡️", callback_data=f"results_page_{page+1}"))
            if nav_row:
                keyboard.append(nav_row)
            
            # Action buttons
            keyboard.extend([
                [
                    InlineKeyboardButton("◀️ Geri", callback_data="back_main"),
                    InlineKeyboardButton("🔄 Yenilə", callback_data="results")
                ]
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
        except Exception as e:
            logger.error("Error parsing results data", exc_info=True)
            msg = f"❌ Nəticə məlumatları tapılmadı. Xəta: {str(e)}"
            keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="results")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        # Both API and cache failed
        msg = "❌ **Oyunların nəticəsi hazırda əlçatan Deyil**\n\n"
        msg += "⚠️ Hal-hazırda oyunların nəticəsi məlumatlarına çatmaq mümkün deyil.\n\n"
        msg += "🔄 Xahiş edirik, bir neçə dəqiqə sonra yenidən cəhd edin."
        msg += "💡 **Səbəblər:**\n"
        msg += "• Chelsea FC saytında texniki problemlər\n"
        msg += "• Internet əlaqə problemi\n"
        msg += "• Server yüklənməsi\n\n"
        msg += "🔄 Xahiş edirik, bir neçə dəqiqə sonra yenidən cəhd edin."

        keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="results")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
    return 0