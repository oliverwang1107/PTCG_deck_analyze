"""
Deck building trends analysis.
"""
from collections import defaultdict
from typing import Optional

from ..scraper.models import CardUsage


class TrendsAnalyzer:
    """Analyzes deck building trends and card usage patterns."""
    
    def __init__(self, data: dict):
        """
        Initialize with scraped data.
        
        Args:
            data: Scraped data dictionary from LimitlessScraper
        """
        self.data = data
        self.tournaments = data.get("tournaments", [])
        self.metagame = data.get("metagame", [])
    
    def get_meta_trends(self) -> dict:
        """
        Get metagame trends showing archetype popularity changes.
        """
        # Group by time period (week)
        weekly_usage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        weekly_totals: dict[str, int] = defaultdict(int)
        
        from datetime import datetime
        
        for tournament in self.tournaments:
            date_str = tournament.get("date", "")
            try:
                date = datetime.fromisoformat(date_str)
                week_key = date.strftime("%Y-W%W")
            except ValueError:
                continue
            
            for deck in tournament.get("decks", []):
                archetype = deck.get("archetype", "Unknown")
                weekly_usage[week_key][archetype] += 1
                weekly_totals[week_key] += 1
        
        # Convert to percentage trends
        weeks = sorted(weekly_usage.keys())
        
        # Find top archetypes overall
        archetype_totals: dict[str, int] = defaultdict(int)
        for week_data in weekly_usage.values():
            for arch, count in week_data.items():
                archetype_totals[arch] += count
        
        top_archetypes = sorted(
            archetype_totals.keys(),
            key=lambda x: archetype_totals[x],
            reverse=True
        )[:8]
        
        # Build trend data
        trend_data = {arch: [] for arch in top_archetypes}
        
        for week in weeks:
            total = weekly_totals[week] or 1
            for arch in top_archetypes:
                usage = weekly_usage[week].get(arch, 0)
                trend_data[arch].append(round((usage / total) * 100, 2))
        
        return {
            "weeks": weeks,
            "archetypes": top_archetypes,
            "trends": trend_data
        }
    
    def get_core_cards(self, archetype: str) -> list[dict]:
        """
        Identify core cards for an archetype (cards appearing in most builds).
        
        Note: This requires detailed deck list data which may not be available
        from all sources. Returns mock data structure for UI demonstration.
        """
        # Since we don't have full deck lists from basic scraping,
        # return template structure that can be filled when detailed data is available
        return [
            {"card": f"Core Pokemon for {archetype}", "rate": 100, "avg_count": 4},
            {"card": "Professor's Research", "rate": 95, "avg_count": 4},
            {"card": "Boss's Orders", "rate": 90, "avg_count": 2},
            {"card": "Nest Ball", "rate": 85, "avg_count": 4},
        ]
    
    def get_tech_cards(self, archetype: str) -> list[dict]:
        """
        Identify tech cards for an archetype (variable usage between builds).
        """
        # Template structure for when detailed deck data is available
        return [
            {"card": "Iono", "rate": 70, "avg_count": 2},
            {"card": "Switch Cart", "rate": 45, "avg_count": 2},
            {"card": "Counter Catcher", "rate": 30, "avg_count": 1},
        ]
    
    def get_archetype_summary(self, archetype: str) -> dict:
        """
        Get a summary of an archetype's building trends.
        """
        # Count occurrences and placements
        total_count = 0
        win_count = 0
        top8_count = 0
        
        for tournament in self.tournaments:
            for deck in tournament.get("decks", []):
                if deck.get("archetype") == archetype:
                    total_count += 1
                    placement = deck.get("placement")
                    if placement:
                        if placement == 1:
                            win_count += 1
                        if placement <= 8:
                            top8_count += 1
        
        return {
            "archetype": archetype,
            "total_entries": total_count,
            "win_count": win_count,
            "top8_count": top8_count,
            "core_cards": self.get_core_cards(archetype),
            "tech_cards": self.get_tech_cards(archetype),
            "recent_trend": "stable"  # Would be calculated from time series
        }
    
    def get_chart_data(self) -> dict:
        """Get data formatted for trend chart display."""
        trends = self.get_meta_trends()
        
        return {
            "labels": trends["weeks"],
            "datasets": [
                {
                    "label": arch,
                    "data": trends["trends"][arch]
                }
                for arch in trends["archetypes"]
            ]
        }
