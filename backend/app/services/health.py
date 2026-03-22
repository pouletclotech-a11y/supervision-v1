from datetime import datetime
import pytz

def calculate_expected_today(expected_per_day: int, interval_min: int) -> int:
    """
    Calculates how many emails/files should have been received so far today (Paris time)
    based on the daily target and the expected interval.
    """
    if expected_per_day <= 0:
        return 0
        
    paris_tz = pytz.timezone("Europe/Paris")
    now_paris = datetime.now(paris_tz)
    
    minutes_passed = now_paris.hour * 60 + now_paris.minute
    slots_passed = minutes_passed // interval_min
    
    # We cap it at the daily expected amount
    return min(slots_passed, expected_per_day)
