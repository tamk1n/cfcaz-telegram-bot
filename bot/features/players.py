import logging
import aiohttp
import settings

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from bot.service import fetch_with_cache



async def players(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show Chelsea players with pagination."""
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
    return 0


async def player_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show individual player information with statistics."""
    logger = logging.getLogger(__name__)

    # Check if bot should respond in this chat
    # if not await check_group_access(update, context):
    #     return END_ROUTES
    
    query = update.callback_query
    await query.answer()
    
    # Extract player ID and competition from callback data
    # Format: player_id or player_id_comp_competition_id
    callback_data = query.data
    player_id = callback_data
    competition_id = None
    
    if "_comp_" in callback_data:
        parts = callback_data.split("_comp_")
        player_id = parts[0]
        competition_id = parts[1]
    
    from app import back_to_main
    from .about import about
    from .recent_results import recent_results
    
    # Check if this is a navigation command that should be handled by other handlers
    if player_id == "players":
        return await players(update, context)
    elif player_id == "back_main":
        return await back_to_main(update, context)
    elif player_id.startswith("players_page_"):
        return await players(update, context)
    elif player_id in ["results", "tickets", "live", "about", "stats", "news"]:
        return await about(update, context)
    elif player_id.startswith("results_page_"):
        return await recent_results(update, context)
    
    # Find player by ID to validate this is actually a player callback
    player_data = next((player for player in settings.PLAYERS if player['id'] == player_id), None)
    
    if not player_data:
        # This callback data is not a valid player ID, ignore it
        return 0
    
    player_name = player_data['full_name']
    player_number = player_data['number']
    display_name = f"#{player_number} {player_name}" if player_number else player_name
    
    # If no competition selected, show competition selector first
    if not competition_id:
        # Show loading message - handle both text and photo messages
        loading_msg = f"👤 <b>{display_name}</b>\n\n⏳ Turnir siyahısı yüklənir..."
        
        # Check if current message has a photo
        is_photo_message = bool(query.message.photo)
        chat_id = query.message.chat.id
        
        if is_photo_message:
            # Delete photo message and send new text message
            await query.delete_message()
            await context.bot.send_message(
                chat_id=chat_id,
                text=loading_msg,
                parse_mode='HTML'
            )
        else:
            # Edit existing text message
            await query.edit_message_text(
                text=loading_msg,
                parse_mode='HTML'
            )
        
        try:
            # Fetch player stats to get available competitions
            # Add season filter for 2025/2026
            stats_url = f"{settings.PLAYER_STATS_API_URL}{player_id}/stats?season=2025"
            cache_key = f"player_stats_{player_id}_season_2025"
            
            result = await fetch_with_cache(
                url=stats_url, 
                cache_key=cache_key, 
                max_age_hours=settings.PLAYER_STATS_CACHE_HOURS
            )
            
            if result["success"]:
                stats_data = result["data"]
                
                # Get available competitions from API response
                available_competitions = []
                if 'competitions' in stats_data:
                    for comp in stats_data['competitions']:
                        comp_id = comp.get('value')
                        # Only include competitions we have translations for
                        if comp_id in settings.COMPETITIONS_AZ:
                            comp_name = settings.COMPETITIONS_AZ.get(comp_id)
                            available_competitions.append({
                                'id': comp_id,
                                'name': comp_name,
                                'selected': comp.get('selectedValue', False)
                            })
                
                # Build competition selector message
                msg = f"👤 <b>{display_name}</b>\n\n"
                msg += "🏆 <b>Statistika görmək üçün turnir seçin:</b>\n\n"
                
                # Build keyboard with competition buttons
                keyboard = []
                comp_row = []
                for comp in available_competitions:
                    button_text = comp["name"]
                    # Shorten if too long
                    if len(button_text) > 20:
                        if "Premyer" in button_text:
                            button_text = "Premyer Liqa"
                        elif "Çempionlar" in button_text:
                            button_text = "Çempionlar Liqası"
                        elif "Konfrans" in button_text:
                            button_text = "Konfrans Liqası"
                    
                    comp_row.append(InlineKeyboardButton(
                        button_text, 
                        callback_data=f"{player_id}_comp_{comp['id']}"
                    ))
                    
                    # 2 buttons per row for better readability
                    if len(comp_row) == 2:
                        keyboard.append(comp_row)
                        comp_row = []
                
                # Add remaining competitions
                if comp_row:
                    keyboard.append(comp_row)
                
                # Navigation buttons
                keyboard.append([
                    InlineKeyboardButton("◀️ Oyunçular", callback_data="players"),
                    InlineKeyboardButton("🏠 Ana Menyu", callback_data="back_main")
                ])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                # Check if message has photo and handle accordingly
                if is_photo_message:
                    # Already deleted, just send new message
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=msg,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                else:
                    await query.edit_message_text(
                        text=msg,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                return 0
            else:
                # Failed to load competitions
                msg = f"👤 <b>{display_name}</b>\n\n"
                msg += "❌ Turnir siyahısı yüklənə bilmədi.\n\n"
                keyboard = [
                    [
                        InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data=player_id),
                        InlineKeyboardButton("◀️ Geri", callback_data="players")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    text=msg,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
                return 0
                
        except Exception as e:
            logger.error(f"Error loading competitions: {e}")
            msg = f"👤 <b>{display_name}</b>\n\n"
            msg += "⚠️ Turnir siyahısı yüklənirkən xəta baş verdi.\n\n"
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Yenidən Cəhd Et", callback_data=player_id),
                    InlineKeyboardButton("◀️ Geri", callback_data="players")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text=msg,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return 0
    
    # Competition is selected, show stats
    # Show loading message - this should always be from a text message (competition selector)
    # but let's be safe and check
    loading_msg = f"👤 <b>{display_name}</b>\n\n⏳ Statistika yüklənir..."
    
    stats_is_photo_message = bool(query.message.photo)
    stats_chat_id = query.message.chat.id
    
    if stats_is_photo_message:
        # Shouldn't happen, but handle it just in case
        await query.delete_message()
        await context.bot.send_message(
            chat_id=stats_chat_id,
            text=loading_msg,
            parse_mode='HTML'
        )
    else:
        await query.edit_message_text(
            text=loading_msg,
            parse_mode='HTML'
        )
    
    try:
        # Fetch player stats from API with competition and season filter
        stats_url = f"{settings.PLAYER_STATS_API_URL}{player_id}/stats"
        if competition_id:
            stats_url += f"?playerEntryId={player_id}&competitionId={competition_id}&season=2025"
        else:
            stats_url += f"?season=2025"
        
        cache_key = f"player_stats_{player_id}_season_2025"
        if competition_id:
            cache_key += f"_comp_{competition_id}"
            
        result = await fetch_with_cache(
            url=stats_url, 
            cache_key=cache_key, 
            max_age_hours=settings.PLAYER_STATS_CACHE_HOURS
        )
        photo_url = None

        if result["success"]:
            stats_data = result["data"]
            
            # Get available competitions from API response
            available_competitions = []
            if 'competitions' in stats_data:
                for comp in stats_data['competitions']:
                    comp_id = comp.get('value')
                    comp_name = settings.COMPETITIONS_AZ.get(comp_id, comp.get('displayText', 'Bilinmir'))
                    available_competitions.append({
                        'id': comp_id,
                        'name': comp_name,
                        'selected': comp.get('selectedValue', False)
                    })
            
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
            
            # Show selected competition if any
            if competition_id:
                selected_comp = next((c for c in available_competitions if c['id'] == competition_id), None)
                if selected_comp:
                    msg += f"🏆 <b>{selected_comp['name']}</b>\n\n"
            
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
            
            # Show note about competition if selected
            if competition_id:
                selected_comp = next((c for c in available_competitions if c["id"] == competition_id), None)
                if selected_comp:
                    msg += f"🔍 <b>Bu statistika {selected_comp['name']} üçün nəzərdə tutulub</b>\n\n"
            else:
                msg += "🔍 <b>Bu statistika 2024/2025 Premyer Liqası üçün nəzərdə tutulub</b>\n\n"


            # If no significant stats found, show basic info
            if not any(section in stats_data for section in ['appearances', 'goals', 'goalKeeping', 'passSuccess']):
                msg += "📊 Bu oyunçu üçün ətraflı statistika hələ mövcud deyil.\n\n"
            
        else:
            msg = f"👤 <b>{display_name}</b>\n\n"
            msg += "❌ Statistika məlumatları yüklənə bilmədi.\n\n"
            available_competitions = []
                    
    except Exception as e:
        msg = f"👤 <b>{display_name}</b>\n\n"
        msg += "⚠️ Statistika yüklənirkən xəta baş verdi.\n\n"
        available_competitions = []
    
    # Build simple navigation keyboard
    keyboard = [
        [
            InlineKeyboardButton("🔄 Başqa Turnir", callback_data=player_id),
            InlineKeyboardButton("◀️ Oyunçular", callback_data="players")
        ],
        [
            InlineKeyboardButton("🏠 Ana Menyu", callback_data="back_main")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Try to send photo with caption if photo is available locally
    import os
    
    # Check for local player photo first (much faster)
    photo_path = None
    # Project root is two levels above this file (bot/features -> bot -> project root)
    static_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'players')
    
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
            return 0
            
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
                        return 0
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
            return 0
    
    # Send as text message if no photo or photo failed
    # Check if the current message has a photo (coming from photo message)
    if query.message.photo:
        # Delete the photo message and send a new text message
        await query.delete_message()
        await context.bot.send_message(
            chat_id=query.message.chat.id,
            text=msg,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    else:
        # Edit the existing text message
        try:
            await query.edit_message_text(text=msg, reply_markup=reply_markup, parse_mode='HTML')
        except Exception as edit_error:
            logger.error(f"Error editing message: {edit_error}")
            # If edit fails, delete and send new
            await query.delete_message()
            await context.bot.send_message(
                chat_id=query.message.chat.id,
                text=msg,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
    return 0