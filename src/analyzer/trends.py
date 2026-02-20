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
                dt = datetime.fromisoformat(date_str.split("T")[0])
                iso = dt.isocalendar()
                week_key = f"{iso[0]}-W{iso[1]:02d}"
            except (ValueError, AttributeError):
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
    
    def get_card_trends(self, archetype: str, card_type_filter: Optional[str] = None, card_names: Optional[list[str]] = None) -> dict:
        """
        Get card usage trends over time for a specific archetype.
        
        Args:
            archetype: Archetype name
            card_type_filter: Optional filter by card type (Pokemon, Trainer, Energy)
            card_names: Optional list of specific card names to track
            
        Returns:
            Dictionary with weeks and card trend data
        """
        weekly_usage = defaultdict(lambda: defaultdict(int))
        weekly_decks = defaultdict(int)
        
        from datetime import datetime
        
        # 1. Collect Data Grouped by Week
        for tournament in self.tournaments:
            date_str = tournament.get("date", "")
            try:
                date = datetime.fromisoformat(date_str)
                week_key = date.strftime("%Y-W%W")
            except ValueError:
                continue
                
            for deck in tournament.get("decks", []):
                if deck.get("archetype") != archetype:
                    continue
                
                weekly_decks[week_key] += 1
                
                if not deck.get("cards"):
                    continue
                    
                seen_cards = set()
                for card in deck["cards"]:
                    name = card["name"]
                    ctype = card.get("card_type")
                    
                    if card_type_filter and ctype != card_type_filter:
                        continue
                        
                    if card_names and name not in card_names:
                        continue
                        
                    # Count each card once per deck (usage rate, not count avg for now)
                    if name not in seen_cards:
                        weekly_usage[week_key][name] += 1
                        seen_cards.add(name)
        
        weeks = sorted(weekly_decks.keys())
        if not weeks:
            return {"weeks": [], "datasets": []}
            
        # 2. Identify Top Cards to Track (if not specified)
        if not card_names:
            card_totals = defaultdict(int)
            for week_data in weekly_usage.values():
                for card, count in week_data.items():
                    card_totals[card] += count
            
            # Filter for "Trending" cards
            # We want cards that are NOT in 100% of decks (Core) but have significant presence
            total_archetype_decks = sum(weekly_decks.values())
            trending_candidates = []
            
            for card, count in card_totals.items():
                rate = count / total_archetype_decks
                # Tech cards usually between 10% and 90%
                if 0.1 <= rate <= 0.9:
                    trending_candidates.append(card)
            
            # Sort by total count and take top 10
            card_names = sorted(trending_candidates, key=lambda x: card_totals[x], reverse=True)[:10]
        
        # 3. Build Chart Data
        datasets = []
        for card in card_names:
            data_points = []
            for week in weeks:
                total = weekly_decks[week]
                if total == 0:
                    data_points.append(0)
                else:
                    count = weekly_usage[week].get(card, 0)
                    data_points.append(round((count / total) * 100, 1))
            
            datasets.append({
                "label": card,
                "data": data_points
            })
            
        return {
            "weeks": weeks,
            "datasets": datasets
        }

    def get_ace_spec_trends(self, archetype: str) -> dict:
        """Get trends specifically for ACE SPEC cards."""
        # Hardcoded list of known ACE SPECS for now, or detect via scraper if possible
        # For now, we'll try to detect them by name if scraper doesn't tag them
        # Note: Scraper should ideally tag 'ACE SPEC' in card type or subtype
        # We will assume user asks scraper to do this, or we rely on known list
        
        known_ace_specs = [
            "Prime Catcher", "Master Ball", "Unfair Stamp", "Maximum Belt", 
            "Hero's Cape", "Neo Upper Energy", "Hyper Aroma", "Secret Box",
            "Legacy Energy", "Neutral Center", "Poké Vital A", "Dangerous Laser",
            "Scoop Up Cyclone", "Grand Tree", "Brilliant Blender",
            "極限腰帶", "英雄斗篷", "新上位能量", "偉大之樹", "中立中心",
            "強力捕捉器", "大師球", "不公印章", "秘密箱", "遺產能量",
            "活力藥劑A", "危險光線", "回收旋風", "晶粹混合器"
        ]
        
        return self.get_card_trends(archetype, card_names=known_ace_specs)

    def get_tech_trends(self, archetype: str) -> dict:
        """Get trends for tech cards (automatically identified)."""
        # We reuse get_card_trends without specific names, it has logic to find techs
        return self.get_card_trends(archetype)

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
