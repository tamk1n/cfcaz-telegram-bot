#!/usr/bin/env python
# pylint: disable=unused-argument

import logging
import aiohttp
import os

import settings
from utils import convert_to_azerbaijan_time

if not settings.BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
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
    # if not ALLOWED_GROUPS:
    #     return True
    
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send message on `/start`."""
    # Group access check temporarily disabled since ALLOWED_GROUPS is empty
    # if not await check_group_access(update, context):
    #     return START_ROUTES
    
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
    
    welcome_msg = f"**Salam, {user.first_name}!**\n\n"
    welcome_msg += "Nə görmək istəyirsiniz?\n\n"
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode='Markdown')
    return START_ROUTES


async def fixtures(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Request Chelsea API and show beautiful fixture list with pagination."""
    # Group access check temporarily disabled since ALLOWED_GROUPS is empty
    # if not await check_group_access(update, context):
    #     return START_ROUTES
    
    query = update.callback_query
    await query.answer()
    
    # Get page number from callback data or default to 1
    page = 1
    if '_page_' in query.data:
        page = int(query.data.split('_page_')[1])
    
    async with aiohttp.ClientSession() as session:
        async with session.get(settings.CHELSEA_API_URL) as resp:
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
    
    # Check if the current message has a photo (coming from photo message)
    if query.message.photo:
        # Delete the photo message and send a new text message
        await query.delete_message()
        await query.message.reply_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        # Edit the existing text message
        await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
    return START_ROUTES

async def league_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show Premier League table with Chelsea highlighted."""
    # Group access check temporarily disabled since ALLOWED_GROUPS is empty
    # if not await check_group_access(update, context):
    #     return START_ROUTES
    
    query = update.callback_query
    await query.answer()
    
    async with aiohttp.ClientSession() as session:
        async with session.get(settings.LEAGUE_TABLE_API_URL) as resp:
            if resp.status == 200:
                data = await resp.json()
                try:
                    # Get the Premier League table
                    items = data.get('items', [])
                    if not items:
                        raise ValueError("No table data found")
                    
                    standings = items[0]['standings']['tables'][0]['rows']
                    competition_name = items[0]['competitionDetails']['title']
                    
                    msg = "🏆 <b>PREMIER LEAGUE CƏDVƏLİ</b> 🏆\n"
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
                    
                    keyboard = [
                        [
                            InlineKeyboardButton("◀️ Geri", callback_data="back_main"),
                            InlineKeyboardButton("🔄 Yenilə", callback_data="table")
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                except Exception as e:
                    logger.error("Error parsing table data", exc_info=True)
                    msg = f"❌ Cədvəl məlumatları tapılmadı. Xəta: {str(e)}"
                    keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="table")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
            else:
                msg = f"❌ Chelsea API xətası: {resp.status}"
                keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="table")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
    return START_ROUTES


async def recent_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show recent match results with pagination."""
    # Check if bot should respond in this chat
    if not await check_group_access(update, context):
        return END_ROUTES
    
    query = update.callback_query
    await query.answer()
    
    # Get page number from callback data or default to 1
    page = 1
    if '_page_' in query.data:
        page = int(query.data.split('_page_')[1])
    
    async with aiohttp.ClientSession() as session:
        async with session.get(settings.RESULTS_API_URL) as resp:
            if resp.status == 200:
                data = await resp.json()
                try:
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
                    
                    msg = "⚽ <b>SON NƏTİCƏLƏR</b> ⚽\n"
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
                msg = f"❌ Chelsea API xətası: {resp.status}"
                keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="results")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
    return START_ROUTES


async def players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show Chelsea players with pagination."""

    # Check if bot should respond in this chat
    if not await check_group_access(update, context):
        return END_ROUTES
    
    query = update.callback_query
    await query.answer()
    
    # Get page number from callback data or default to 1
    page = 1
    if '_page_' in query.data:
        page = int(query.data.split('_page_')[1])
    
    try:
        # Create display list for buttons
        players = [f"{p['number']} {p['full_name']}" if p['number'] else p['full_name'] for p in settings.PLAYERS]
        
        # Pagination
        players_per_page = 10
        total_players = len(players)
        total_pages = (total_players + players_per_page - 1) // players_per_page
        
        start_idx = (page - 1) * players_per_page
        end_idx = start_idx + players_per_page
        page_players = players[start_idx:end_idx]
        
        msg = "👥 <b>CHELSEA OYUNÇULARI</b> 👥\n"
        msg += "═" * 25 + "\n\n"
        msg += f"📋 Səhifə {page}/{total_pages}\n\n"
        
        # Create player buttons
        keyboard = []
        for i in range(0, len(page_players), 2):  # 2 players per row
            row = []
            for j in range(2):
                if i + j < len(page_players):
                    player_name = page_players[i + j]
                    # Extract just the name part (remove number if present)
                    if player_name.split()[0].isdigit():
                        # Has number, extract name part
                        name_only = ' '.join(player_name.split()[1:])
                    else:
                        name_only = player_name
                    
                    # Find player by name
                    player_data = next((player for player in settings.PLAYERS if player['full_name'] == name_only), None)
                    callback_data = player_data['id']  
                    
                    row.append(InlineKeyboardButton(player_name, callback_data=callback_data))
            keyboard.append(row)
        
        # Navigation buttons
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton("⬅️ Əvvəlki", callback_data=f"players_page_{page-1}"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton("Növbəti ➡️", callback_data=f"players_page_{page+1}"))
        if nav_row:
            keyboard.append(nav_row)
        
        # Action buttons
        keyboard.extend([
            [
                InlineKeyboardButton("◀️ Geri", callback_data="back_main"),
                InlineKeyboardButton("🔄 Yenilə", callback_data="players")
            ]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
                    
    except Exception as e:
        logger.error("Error loading players data", exc_info=True)
        msg = f"❌ Oyunçu məlumatları tapılmadı. Xəta: {str(e)}"
        keyboard = [[InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data="players")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Check if the current message has a photo (coming from photo message)
    if query.message.photo:
        # Delete the photo message and send a new text message
        await query.delete_message()
        await query.message.reply_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
    else:
        # Edit the existing text message
        await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
    return START_ROUTES


async def player_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show individual player information with statistics."""

    # Check if bot should respond in this chat
    if not await check_group_access(update, context):
        return END_ROUTES
    
    query = update.callback_query
    await query.answer()
    
    # Extract player ID from callback data
    player_id = query.data
    
    # Check if this is a navigation command that should be handled by other handlers
    if player_id == "players":
        return await players(update, context)
    elif player_id == "back_main":
        return await back_to_main(update, context)
    elif player_id.startswith("players_page_"):
        return await players(update, context)
    elif player_id in ["results", "tickets", "live", "about", "stats", "news"]:
        return await coming_soon(update, context)
    elif player_id.startswith("results_page_"):
        return await recent_results(update, context)
    
    # Find player by ID to validate this is actually a player callback
    player_data = next((player for player in settings.PLAYERS if player['id'] == player_id), None)
    
    if not player_data:
        # This callback data is not a valid player ID, ignore it
        return START_ROUTES
    
    player_name = player_data['full_name']
    player_number = player_data['number']
    display_name = f"#{player_number} {player_name}" if player_number else player_name
    
    # Show loading message
    await query.edit_message_text(
        text=f"👤 <b>{display_name}</b>\n\n⏳ Statistika yüklənir...",
        parse_mode='HTML'
    )
    
    try:
        # Fetch player stats from API
        stats_url = f"{settings.PLAYER_STATS_API_URL}{player_id}/stats"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(stats_url) as response:
                if response.status == 200:
                    stats_data = await response.json()
                    
                    # Extract player photo URL from response
                    photo_url = None
                    
                    # Try to get photo from different sections in the API response
                    for section in ['goalKeeping', 'goals', 'passSuccess']:
                        if (section in stats_data and 
                            'playerAvatar' in stats_data[section] and
                            'image' in stats_data[section]['playerAvatar'] and
                            'file' in stats_data[section]['playerAvatar']['image'] and
                            'url' in stats_data[section]['playerAvatar']['image']['file']):
                            photo_url = stats_data[section]['playerAvatar']['image']['file']['url']
                            break
                    
                    # Build message with statistics
                    msg = f"👤 <b>{display_name}</b>\n\n"
                    
                    # Appearances section
                    if 'appearances' in stats_data and 'stats' in stats_data['appearances']:
                        msg += "📊 <b>Oyunlar</b>\n"
                        appearances = stats_data['appearances']['stats']
                        for stat in appearances:
                            title = stat.get('title', '')
                            value = stat.get('value', '0')
                            if 'Appearances' in title:
                                msg += f"• Oyun sayı: {value} oyun\n"
                            elif 'Minutes' in title:
                                msg += f"• Oynadığı dəqiqə: {value} dəqiqə\n"
                            elif 'Starts' in title:
                                msg += f"• İlk 11: {value} oyun\n"
                        msg += "\n"
                    
                    # Goals section (if player has goals)
                    if 'goals' in stats_data and 'stats' in stats_data['goals']:
                        msg += "⚽ <b>Qollar</b>\n"
                        goals = stats_data['goals']['stats']
                        for stat in goals:
                            title = stat.get('title', '')
                            value = stat.get('value', '0')
                            if 'Total Goals' in title:
                                msg += f"• Ümumi qol sayı: {value}\n"
                            elif 'Goals Per Match' in title:
                                msg += f"• Hər oyuna qol nisbət: {value}\n"
                        msg += "\n"
                    
                    # Scored With section (how goals were scored)
                    if 'scoredWith' in stats_data:
                        scored_with = stats_data['scoredWith']
                        has_goals = any(
                            scored_with.get(key, {}).get('value', '0') != '0' 
                            for key in ['head', 'leftFoot', 'rightFoot', 'penalties', 'freeKicks']
                        )
                        if has_goals:
                            msg += "🎯 <b>Qol vurub:</b>\n"
                            if scored_with.get('head', {}).get('value', '0') != '0':
                                msg += f"• Başla: {scored_with['head']['value']}\n"
                            if scored_with.get('leftFoot', {}).get('value', '0') != '0':
                                msg += f"• Sol ayaqla: {scored_with['leftFoot']['value']}\n"
                            if scored_with.get('rightFoot', {}).get('value', '0') != '0':
                                msg += f"• Sağ ayaqla: {scored_with['rightFoot']['value']}\n"
                            if scored_with.get('penalties', {}).get('value', '0') != '0':
                                msg += f"• Penaltı: {scored_with['penalties']['value']}\n"
                            if scored_with.get('freeKicks', {}).get('value', '0') != '0':
                                msg += f"• Cərimə zərbəsi: {scored_with['freeKicks']['value']}\n"
                            msg += "\n"
                    
                    # Goalkeeping section (if goalkeeper)
                    if 'goalKeeping' in stats_data and 'stats' in stats_data['goalKeeping']:
                        msg += "🥅 <b>Qapıçı Statistikası</b>\n"
                        gk_stats = stats_data['goalKeeping']['stats']
                        for stat in gk_stats:
                            title = stat.get('title', '')
                            value = stat.get('value', '0')
                            if 'Total Saves' in title:
                                msg += f"• Xilasetmələr: {value}\n"
                            elif 'Clean Sheets' in title:
                                msg += f"• Qapısında qol görmədiyi oyunlar: {value}\n"
                        msg += "\n"
                    
                    # Pass Success section
                    if 'passSuccess' in stats_data and 'stats' in stats_data['passSuccess']:
                        msg += "🎯 <b>Ötürmə sayı</b>\n"
                        pass_stats = stats_data['passSuccess']['stats']
                        for stat in pass_stats:
                            title = stat.get('title', '')
                            value = stat.get('value', '0')
                            if 'Total Passes' in title:
                                msg += f"• Ümumi ötürmə sayı: {value}\n"
                            elif 'Key Passes' in title:
                                msg += f"• Açar ötürmə sayı: {value}\n"
                            elif 'Assists' in title:
                                msg += f"• Asist sayı: {value}\n"

                        # Pass success rate
                        if 'playerRankingPercent' in stats_data['passSuccess']:
                            success_rate = stats_data['passSuccess']['playerRankingPercent']
                            msg += f"• Dəqiqlik: {success_rate}%\n"
                        msg += "\n"
                    
                    # Fouls section
                    if 'fouls' in stats_data:
                        fouls = stats_data['fouls']
                        if any(fouls.values()):
                            msg += "🟨 <b>Qayda pozuntuları</b>\n"
                            if 'yellowCards' in fouls and fouls['yellowCards'].get('value', '0') != '0':
                                msg += f"• Sarı kart sayı: {fouls['yellowCards']['value']}\n"
                            if 'redCards' in fouls and fouls['redCards'].get('value', '0') != '0':
                                msg += f"• Qırmızı kart sayı: {fouls['redCards']['value']}\n"
                            if 'foulsDrawn' in fouls and fouls['foulsDrawn'].get('value', '0') != '0':
                                msg += f"• Məruz qaldığı pozuntular: {fouls['foulsDrawn']['value']}\n"
                            msg += "\n"
                    
                    # Shots section
                    if 'shots' in stats_data:
                        shots = stats_data['shots']
                        if (shots.get('playerShotsOnTarget', '0') != '0' or 
                            shots.get('playerShotsOffTarget', '0') != '0'):
                            msg += "🎯 <b>Zərbələr</b>\n"
                            if shots.get('playerShotsOnTarget', '0') != '0':
                                msg += f"• Dəqiq zərbə sayı: {shots['playerShotsOnTarget']}\n"
                            if shots.get('playerShotsOffTarget', '0') != '0':
                                msg += f"• Dəqiq olmayan zərbə sayı: {shots['playerShotsOffTarget']}\n"
                            msg += "\n"
                    
                    # Touches section
                    if 'touches' in stats_data and 'stats' in stats_data['touches']:
                        msg += "⚽ <b>Oyun Fəaliyyəti</b>\n"
                        touches = stats_data['touches']['stats']
                        for stat in touches:
                            title = stat.get('title', '')
                            value = stat.get('value', '0')
                            if 'Total Touches' in title:
                                msg += f"• Topa toxunmalar: {value}\n"
                            elif 'Tackles Won' in title and '/' in value:
                                won, lost = value.split('/')
                                if won != '0':
                                    msg += f"• Qazanılan əks hücumlar: {won}\n"
                            elif 'Clearances' in title and value != '0':
                                msg += f"• Müdafiə sayı: {value}\n"
                        msg += "\n"
                        msg += "🔍 <b>Bu statistika 2024/2025 Premyer Liqası üçün nəzərdə tutulub</b>\n\n"

                    # If no significant stats found, show basic info
                    if not any(section in stats_data for section in ['appearances', 'goals', 'goalKeeping', 'passSuccess']):
                        msg += "📊 Bu oyunçu üçün ətraflı statistika hələ mövcud deyil.\n\n"
                    
                else:
                    msg = f"👤 <b>{display_name}</b>\n\n"
                    msg += "❌ Statistika məlumatları yüklənə bilmədi.\n\n"
                    
    except Exception as e:
        msg = f"� <b>{display_name}</b>\n\n"
        msg += "⚠️ Statistika yüklənirkən xəta baş verdi.\n\n"
    
    keyboard = [
        [
            InlineKeyboardButton("◀️ Oyunçular", callback_data="players"),
            InlineKeyboardButton("🏠 Ana Menyu", callback_data="back_main")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Try to send photo with caption if photo is available locally
    import os
    
    # Check for local player photo first (much faster)
    photo_path = None
    static_folder = os.path.join(os.path.dirname(__file__), 'static', 'players')
    
    # Try different file extensions and naming conventions
    possible_filenames = [
        f"{player_id}.jpg",
        f"{player_id}.jpeg", 
        f"{player_id}.png",
        f"{player_id}.webp",
        f"{player_name.lower().replace(' ', '-')}.jpg",
        f"{player_name.lower().replace(' ', '-')}.jpeg",
        f"{player_name.lower().replace(' ', '-')}.png",
        f"{player_name.lower().replace(' ', '-')}.webp"
    ]
    
    for filename in possible_filenames:
        full_path = os.path.join(static_folder, filename)
        if os.path.exists(full_path):
            photo_path = full_path
            break
    
    # If local photo exists, use it (much faster)
    if photo_path:
        try:
            with open(photo_path, 'rb') as photo_file:
                photo_data = photo_file.read()
                
            await query.delete_message()  # Delete the loading message
            try:
                await context.bot.send_photo(
                    chat_id=query.message.chat.id,
                    photo=photo_data,
                    caption=msg,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            except Exception as local_photo_send_error:
                logger.error(f"Error sending local photo to group: {local_photo_send_error}")
                # Fallback to text message
                await context.bot.send_message(
                    chat_id=query.message.chat.id,
                    text=msg,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            return START_ROUTES
            
        except Exception as local_photo_error:
            logger.error(f"Error sending local photo: {local_photo_error}")
            # Continue to try downloading from URL as fallback
    
    # Fallback: Try to download from API (slower)
    if 'photo_url' in locals() and photo_url:
        try:
            # Convert HTTP to HTTPS if needed for better compatibility
            if photo_url.startswith('http://'):
                photo_url = photo_url.replace('http://', 'https://')
                photo_url = photo_url.replace('png', 'webp')
            
            # Try to download and send the image
            async with aiohttp.ClientSession() as session:
                async with session.get(photo_url) as img_response:
                    if img_response.status == 200 and img_response.content_type.startswith('image/'):
                        image_data = await img_response.read()
                        
                        # Check if image is too large for Telegram (10MB limit)
                        max_size = 10 * 1024 * 1024  # 10MB in bytes
                        if len(image_data) > max_size:
                            logger.warning(f"Image too large: {len(image_data)} bytes (max {max_size})")
                            raise Exception(f"Image too large: {len(image_data)} bytes")
                        
                        # Optionally save the downloaded image for future use
                        try:
                            save_path = os.path.join(static_folder, f"{player_id}.jpg")
                            with open(save_path, 'wb') as f:
                                f.write(image_data)
                            logger.info(f"Saved player photo to {save_path}")
                        except Exception as save_error:
                            logger.warning(f"Could not save photo: {save_error}")
                        
                        await query.delete_message()  # Delete the loading message
                        try:
                            await context.bot.send_photo(
                                chat_id=query.message.chat.id,
                                photo=image_data,
                                caption=msg,
                                reply_markup=reply_markup,
                                parse_mode='HTML'
                            )
                        except Exception as photo_send_error:
                            logger.error(f"Error sending photo to group: {photo_send_error}")
                            # Fallback to text message
                            await context.bot.send_message(
                                chat_id=query.message.chat.id,
                                text=msg,
                                reply_markup=reply_markup,
                                parse_mode='HTML'
                            )
                        return START_ROUTES
                    else:
                        # Image not accessible, fall back to text
                        raise Exception(f"Image not accessible: {img_response.status}")
                        
        except Exception as photo_error:
            logger.error(f"Error sending photo: {photo_error}")
            # If photo failed and message was deleted, handle properly for groups
            try:
                await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
            except Exception as edit_error:
                logger.error(f"Error editing message: {edit_error}")
                # For inline messages in groups, try to send a new message
                try:
                    await context.bot.send_message(
                        chat_id=query.message.chat.id,
                        text=msg,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                except Exception as send_error:
                    logger.error(f"Error sending new message: {send_error}")
            return START_ROUTES
    
    # Send as text message if no photo or photo failed
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
    return START_ROUTES


async def live_stream(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show live stream information and link"""

    # Check if bot should respond in this chat
    if not await check_group_access(update, context):
        return END_ROUTES

    query = update.callback_query
    await query.answer()
    
    msg = "📺 <b>CANLI YAYIM</b>\n\n"
    msg += "⚽ Chelsea FC oyunlarını canlı izləyin!\n\n"
    msg += "🔗 Aşağıdakı düyməyə basaraq canlı yayıma keçin:\n\n"
    msg += "💡 <b>Məlumat:</b>\n"
    msg += "• Bildiyiniz kimi, bu mövsümdən etibarən Azərbaycanda İdman TV kanalında Chelseanin bir çox oyunları canlı yayımlanacaq.\n\n"
    msg += "<b>\"Canlı yayıma keç düyməsinə\" </b> basaraq oyuna öz vaxtında baxa bilərsiniz. Bəzi hallarda kanal başqa Premyer Liqa oyununu verə bilər!"
    
    keyboard = [
        [InlineKeyboardButton("📺 Canlı Yayıma Keç", url="https://yodaplayer.yodacdn.net/idmanpop/index.php")],
        [
            InlineKeyboardButton("◀️ Geri", callback_data="back_main"),
            InlineKeyboardButton("🔄 Yenilə", callback_data="live")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
    return START_ROUTES

async def coming_soon(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Placeholder for features coming soon"""

    # Check if bot should respond in this chat
    if not await check_group_access(update, context):
        return END_ROUTES
    
    query = update.callback_query
    await query.answer()
    
    msg = "🚧 **Tezliklə** 🚧\n\n"
    msg += "Bu xüsusiyyət hazırda inkişaf mərhələsindədir.\n"
    msg += "Tezliklə əlavə olunacaq! 🔄"
    
    keyboard = [[InlineKeyboardButton("◀️ Geri", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='Markdown')
    return START_ROUTES


async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle channel posts to provide bot interaction"""

    # Check if bot should respond in this chat
    if not await check_group_access(update, context):
        return END_ROUTES
    
    if update.channel_post:
        # Bot was added to channel - you can add welcome message here
        pass


async def create_channel_post(post_type: str) -> dict:
    """Create a channel-ready post with bot integration"""
    posts = {
        "daily_fixtures": {
            "text": "📅 <b>BUGÜNKÜ OYUNLAR</b>\n\n"
                   "🔵 Chelsea FC oyun təqvimi və detalları üçün aşağıdakı düymələrə basın.\n\n"
                   "⚽ Oyun saatları Azerbaijan vaxtı ilə göstərilir.",
            "buttons": [
                [InlineKeyboardButton("📅 Təqvimi Aç", url="https://t.me/cfcaz_bot?start=fixtures")],
                [InlineKeyboardButton("🤖 Botu Aç", url="https://t.me/cfcaz_bot")]
            ]
        },
        "match_reminder": {
            "text": "🚨 <b>OYUN XATIRLATMASI</b>\n\n"
                   "⚽ Chelsea FC oyunu tezliklə başlayır!\n\n"
                   "📺 Canlı yayım və detallar üçün:",
            "buttons": [
                [InlineKeyboardButton("📺 Canlı Yayım", url="https://yodaplayer.yodacdn.net/idmanpop/index.php")],
                [InlineKeyboardButton("📊 Statistika", url="https://t.me/cfcaz_bot?start=stats")]
            ]
        },
        "weekly_summary": {
            "text": "📊 <b>HƏFTƏLİK XÜLASƏ</b>\n\n"
                   "🔵 Chelsea FC-nin həftəlik performansı və gələn oyunlar.\n\n"
                   "📈 Detallı statistika və analiz:",
            "buttons": [
                [InlineKeyboardButton("📊 Cədvəl", url="https://t.me/cfcaz_bot?start=table")],
                [InlineKeyboardButton("👥 Oyunçular", url="https://t.me/cfcaz_bot?start=players")],
                [InlineKeyboardButton("🤖 Botu Aç", url="https://t.me/cfcaz_bot")]
            ]
        }
    }
    
    return posts.get(post_type, posts["daily_fixtures"])


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
        
        await coming_soon(mock_update, context)
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
                CallbackQueryHandler(league_table, pattern="^table$"),
                CallbackQueryHandler(recent_results, pattern="^results(_page_\\d+)?$"),
                CallbackQueryHandler(players, pattern="^players(_page_\\d+)?$"),
                CallbackQueryHandler(back_to_main, pattern="^back_main$"),
                CallbackQueryHandler(live_stream, pattern="^live$"),
                CallbackQueryHandler(coming_soon, pattern="^(news|tickets|about|stats)$"),
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
    application.add_handler(CallbackQueryHandler(league_table, pattern="^table$"))
    application.add_handler(CallbackQueryHandler(recent_results, pattern="^results(_page_\\d+)?$"))
    application.add_handler(CallbackQueryHandler(players, pattern="^players(_page_\\d+)?$"))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_main$"))
    application.add_handler(CallbackQueryHandler(live_stream, pattern="^live$"))
    application.add_handler(CallbackQueryHandler(coming_soon, pattern="^(news|tickets|about|stats)$"))
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