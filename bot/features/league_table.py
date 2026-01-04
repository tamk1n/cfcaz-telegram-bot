import logging
import aiohttp
import settings

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes


async def league_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show league table with toggle between Premier League and Champions League."""
    logger = logging.getLogger(__name__)

    query = update.callback_query
    await query.answer()
    
    # Determine which competition to show
    # Callback data format: "table" (default to PL) or "table_cl" (Champions League)
    show_champions_league = "_cl" in query.data
    
    # Select appropriate API URL
    api_url = settings.CHAMPIONS_LEAGUE_TABLE_URL if show_champions_league else settings.LEAGUE_TABLE_API_URL

    try:
        # Fetch data directly from API without caching
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Get the Premier League table
                    items = data.get('items', [])
                    if not items:
                        raise ValueError("No table data found")
                    
                    standings = items[0]['standings']['tables'][0]['rows']
                    competition_name = items[0]['competitionDetails']['title']
                    if show_champions_league:
                        msg = "<b>ÇEMPİONLAR LİQASI CƏDVƏLİ</b>\n"
                    else:
                        msg = "<b>PREMYER LİQA CƏDVƏLİ</b>\n"
                    msg += "═" * 30 + "\n\n"
                    
                    # Table header
                    msg += "<pre>\n"
                    msg += " #   Klub         O  Q  H  M  X\n"
                    msg += "───────────────────────────────────\n"
                    
                    for team in standings:
                        pos = team['position']
                        name = team['clubShortName']
                        played = team['played']
                        won = team['won']
                        drawn = team['drawn'] 
                        lost = team['lost']
                        gf = team['goalsFor']
                        ga = team['goalsAgainst']
                        gd = team['goalDifference']
                        points = team['points']
                        is_chelsea = team['featuredTeam']
                        
                        # Truncate name if too long
                        if len(name) > 12:
                            name = name[:12]
                        
                        # Highlight Chelsea
                        if is_chelsea:
                            line = f"►{pos:2} {name:<12} {played:2} {won:2} {drawn:2} {lost:2} {points:2}◄"
                        else:
                            line = f" {pos:2} {name:<12} {played:2} {won:2} {drawn:2} {lost:2} {points:2}"
                        
                        msg += line + "\n"
                        
                        # Add separation lines for qualification zones
                        if team.get('cutLine'):
                            msg += "───────────────────────────────────\n"
                    
                    msg += "</pre>\n\n"
                    
                    # Build keyboard with toggle button
                    keyboard = []
                    
                    # Toggle button
                    if show_champions_league:
                        keyboard.append([
                            InlineKeyboardButton("Premyer Liqa Cədvəli", callback_data="table")
                        ])
                    else:
                        keyboard.append([
                            InlineKeyboardButton("Çempionlar Liqası Cədvəli", callback_data="table_cl")
                        ])
                    
                    # Navigation buttons
                    keyboard.append([
                        InlineKeyboardButton("◀️ Geri", callback_data="back_main"),
                        InlineKeyboardButton("🔄 Yenilə", callback_data=query.data)
                    ])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                else:
                    # API request failed
                    raise Exception(f"API request failed with status {response.status}")
                    
    except Exception as e:
        logger.error("Error fetching table data", exc_info=True)
        msg = "❌ **Turnir Cədvəli Əlçatan Deyil**\n\n"
        msg += "⚠️ Hal-hazırda turnir cədvəli məlumatlarına çatmaq mümkün deyil.\n\n"
        msg += "💡 **Səbəblər:**\n"
        msg += "• Chelsea FC saytında texniki problemlər\n"
        msg += "• Internet əlaqə problemi\n"
        msg += "• Server yüklənməsi\n\n"
        msg += "🔄 Xahiş edirik, bir neçə dəqiqə sonra yenidən cəhd edin."
        
        keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="table")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
    # START_ROUTES is 0 in the main app (START_ROUTES, END_ROUTES = range(2))
    return 0