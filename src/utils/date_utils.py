from datetime import datetime, timedelta

def get_week_key(date_str: str) -> str:
    """Get week identifier from date string (YYYY-WXX format)."""
    try:
        dt = datetime.fromisoformat(date_str.split("T")[0])
        iso_calendar = dt.isocalendar()
        return f"{iso_calendar[0]}-W{iso_calendar[1]:02d}"
    except (ValueError, AttributeError):
        return "Unknown"

def get_previous_week(week_key: str) -> str:
    """Get the key for the previous week."""
    try:
        year, week_num = map(int, week_key.split("-W"))
        
        if week_num > 1:
            return f"{year}-W{week_num-1:02d}"
        else:
            dt = datetime.fromisocalendar(year, 1, 1) - timedelta(days=7)
            iso = dt.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
    except (ValueError, AttributeError):
        return week_key
