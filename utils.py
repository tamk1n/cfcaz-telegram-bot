from datetime import datetime, timedelta
import pytz
import settings

def convert_to_azerbaijan_time(date_str, time_str):
    """Convert match date and time to Azerbaijan timezone (UTC+4)"""
    try:
        # Parse the date string (e.g., "Sun 17 Aug 2025")
        parts = date_str.split()
        day_name = parts[0]
        day = int(parts[1])
        month = parts[2]
        year = int(parts[3])
        
        # Parse time (e.g., "14:00")
        hour, minute = map(int, time_str.split(':'))
        
        # Create datetime object assuming London (or the source timezone)
        dt = datetime(year, list(settings.MONTHS.keys()).index(month) + 1, day, hour, minute)
        # Define timezones
        london_tz = pytz.timezone('Europe/London')
        azerbaijan_tz = pytz.timezone('Asia/Baku')
        
        # Assume source time is London and localize it
        london_dt = london_tz.localize(dt)
        
        # Convert to Azerbaijan timezone
        az_dt = london_dt.astimezone(azerbaijan_tz)
        # Format in Azerbaijani
        az_day_name = settings.WEEKDAYS.get(day_name, day_name)
        az_month = settings.MONTHS.get(month, month)
        
        formatted_date = f"{az_day_name} {az_dt.day} {az_month} {az_dt.year}"
        formatted_time = f"{az_dt.hour:02d}:{az_dt.minute:02d}"
        
        return formatted_date, formatted_time
    except Exception:
        # Fallback to original if parsing fails
        return date_str, time_str