"""
Win rate analysis module.
"""
from collections import defaultdict
from datetime import datetime
from typing import Optional


class WinRateAnalyzer:
    """Analyzes deck win rates and performance trends."""
    
    def __init__(self, data: dict):
        """
        Initialize with scraped data.
        
        Args:
            data: Scraped data dictionary from LimitlessScraper
        """
        self.data = data
        self.tournaments = data.get("tournaments", [])
    
    def calculate_win_rates(self) -> dict[str, dict]:
        """
        Calculate win rates for all archetypes.
        
        Win rate is estimated based on tournament placements:
        - 1st place: Full win credit
        - 2nd-4th: Partial win credit
        - 5th-8th: Minor credit
        """
        archetype_data: dict[str, dict] = defaultdict(lambda: {
            "total_entries": 0,
            "wins": 0,
            "top4": 0,
            "top8": 0,
            "points": 0
        })
        
        for tournament in self.tournaments:
            for deck in tournament.get("decks", []):
                archetype = deck.get("archetype", "Unknown")
                placement = deck.get("placement")
                
                archetype_data[archetype]["total_entries"] += 1
                
                if placement:
                    if placement == 1:
                        archetype_data[archetype]["wins"] += 1
                        archetype_data[archetype]["points"] += 100
                    elif placement <= 4:
                        archetype_data[archetype]["top4"] += 1
                        archetype_data[archetype]["points"] += 50
                    elif placement <= 8:
                        archetype_data[archetype]["top8"] += 1
                        archetype_data[archetype]["points"] += 25
        
        # Calculate rates
        results = {}
        for archetype, data in archetype_data.items():
            entries = data["total_entries"]
            if entries > 0:
                results[archetype] = {
                    "total_entries": entries,
                    "wins": data["wins"],
                    "top4": data["top4"],
                    "top8": data["top8"],
                    "win_rate": round((data["wins"] / entries) * 100, 2),
                    "top4_rate": round(((data["wins"] + data["top4"]) / entries) * 100, 2),
                    "top8_rate": round(((data["wins"] + data["top4"] + data["top8"]) / entries) * 100, 2),
                    "performance_score": round(data["points"] / entries, 2)
                }
        
        return results
    
    def get_performance_ranking(self, min_entries: int = 5) -> list[dict]:
        """
        Get archetypes ranked by performance score.
        
        Args:
            min_entries: Minimum entries to be included in ranking
        """
        win_rates = self.calculate_win_rates()
        
        # Filter by minimum entries
        filtered = {
            k: v for k, v in win_rates.items() 
            if v["total_entries"] >= min_entries
        }
        
        # Sort by performance score
        ranked = sorted(
            [{"name": k, **v} for k, v in filtered.items()],
            key=lambda x: x["performance_score"],
            reverse=True
        )
        
        return ranked
    
    def get_trend_data(self, archetype: Optional[str] = None) -> dict:
        """
        Get performance trend over time.
        
        Args:
            archetype: Specific archetype to get trend for, or None for all
        """
        # Group tournaments by week/month
        weekly_data: dict[str, dict] = defaultdict(lambda: defaultdict(int))
        
        for tournament in self.tournaments:
            date_str = tournament.get("date", "")
            try:
                date = datetime.fromisoformat(date_str)
                week_key = date.strftime("%Y-W%W")
            except ValueError:
                continue
            
            for deck in tournament.get("decks", []):
                deck_archetype = deck.get("archetype", "Unknown")
                
                if archetype and deck_archetype != archetype:
                    continue
                
                placement = deck.get("placement")
                weekly_data[week_key][deck_archetype] += 1
                
                if placement == 1:
                    weekly_data[week_key][f"{deck_archetype}_wins"] += 1
        
        return dict(weekly_data)
    
    def get_chart_data(self) -> dict:
        """Get data formatted for win rate chart display."""
        rankings = self.get_performance_ranking(min_entries=3)[:15]
        
        return {
            "labels": [r["name"] for r in rankings],
            "win_rates": [r["win_rate"] for r in rankings],
            "top8_rates": [r["top8_rate"] for r in rankings],
            "entries": [r["total_entries"] for r in rankings]
        }
