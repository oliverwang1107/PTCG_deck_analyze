from datetime import datetime, timedelta

def get_previous_week(week_key: str) -> str:
    """Get the key for the previous week."""
    try:
        year, week_num = map(int, week_key.split("-W"))
        
        if week_num > 1:
            return f"{year}-W{week_num-1:02d}"
        else:
            # Previous year's last week
            dt = datetime.fromisocalendar(year, 1, 1) - timedelta(days=7)
            iso = dt.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
    except Exception as e:
        return f"Error: {e}"

# Test cases
print(f"2026-W07 -> {get_previous_week('2026-W07')}")
print(f"2026-W01 -> {get_previous_week('2026-W01')}")
print(f"2025-W01 -> {get_previous_week('2025-W01')}")
print(f"2027-W01 -> {get_previous_week('2027-W01')}")
