
import sys
import json
import requests
from datetime import datetime

BASE_URL = "http://127.0.0.1:5002/api"

def test_timeline():
    print("Fetching weeks...")
    try:
        res = requests.get(f"{BASE_URL}/tournaments/weekly")
        data = res.json()
        if not data.get("weeks"):
            print("No weeks found. Cannot test.")
            return
            
        weeks = data["weeks"]
        print(f"Found {len(weeks)} weeks.")
        
        latest_week = weeks[0]["week"]
        print(f"Latest week: {latest_week}")
        
        if len(weeks) < 2:
            print("Not enough weeks to test filtering fully, but will test with latest.")
            target_week = latest_week
        else:
            target_week = weeks[1]["week"]
            print(f"Target testing week (2nd latest): {target_week}")
            
        # 1. Test Overview Filtering
        print(f"\n[1] Testing Overview for {target_week}...")
        res_over = requests.get(f"{BASE_URL}/overview?week={target_week}")
        over_data = res_over.json()
        
        print(f"Total Tournaments (Window): {over_data['total_tournaments']}")
        print(f"Current Week ({over_data.get('current_week')}): {over_data.get('current_week_decks')} decks")
        print(f"Prev Week ({over_data.get('prev_week')}): {over_data.get('prev_week_decks')} decks")
        
        if over_data.get('current_week') == target_week:
            print("✅ Current week matches target.")
        else:
            print(f"❌ Current week mismatch in overview: {over_data.get('current_week')}")
            
        # 2. Test Trends Cutoff
        print(f"\n[2] Testing Trends for {target_week}...")
        res_trends = requests.get(f"{BASE_URL}/trends?week={target_week}")
        trends_data = res_trends.json()
        
        meta_trends = trends_data.get("meta_trends", {})
        trend_weeks = meta_trends.get("weeks", [])
        
        if trend_weeks:
            last_trend_week = trend_weeks[-1]
            print(f"Last week in trends: {last_trend_week}")
            if last_trend_week <= target_week:
                print("✅ Trends correctly cut off at target week.")
            else:
                print(f"❌ Trends include future data: {last_trend_week} > {target_week}")
        else:
            print("⚠️ No trend data found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_timeline()
