"""
Archetype distribution analysis.
"""
from collections import Counter
from typing import Optional

from ..scraper.models import ArchetypeStats


class ArchetypeAnalyzer:
    """Analyzes deck archetype distribution and statistics."""
    
    def __init__(self, data: dict):
        """
        Initialize with scraped data.
        
        Args:
            data: Scraped data dictionary from LimitlessScraper
        """
        self.data = data
        self.tournaments = data.get("tournaments", [])
        self._archetype_stats: Optional[dict[str, ArchetypeStats]] = None
    
    def calculate_stats(self) -> dict[str, ArchetypeStats]:
        """Calculate statistics for all archetypes."""
        if self._archetype_stats:
            return self._archetype_stats
        
        stats: dict[str, ArchetypeStats] = {}
        total_decks = 0
        
        for tournament in self.tournaments:
            for deck in tournament.get("decks", []):
                archetype = deck.get("archetype", "Unknown")
                placement = deck.get("placement")
                
                if archetype not in stats:
                    stats[archetype] = ArchetypeStats(name=archetype)
                
                stats[archetype].deck_count += 1
                total_decks += 1
                
                if placement:
                    if placement <= 8:
                        stats[archetype].top8_count += 1
                    if placement <= 4:
                        stats[archetype].top4_count += 1
                    if placement == 1:
                        stats[archetype].win_count += 1
        
        # Calculate rates
        for archetype_name, archetype_stats in stats.items():
            if total_decks > 0:
                archetype_stats.usage_rate = archetype_stats.deck_count / total_decks
            if archetype_stats.deck_count > 0:
                archetype_stats.top8_rate = archetype_stats.top8_count / archetype_stats.deck_count
                # Win rate approximation based on tournament performance
                archetype_stats.win_rate = (
                    (archetype_stats.win_count * 3 + 
                     archetype_stats.top4_count * 2 + 
                     archetype_stats.top8_count) / 
                    (archetype_stats.deck_count * 6)
                )
        
        self._archetype_stats = stats
        return stats
    
    def get_top_archetypes(self, n: int = 10, by: str = "usage") -> list[ArchetypeStats]:
        """
        Get top N archetypes sorted by specified metric.
        
        Args:
            n: Number of archetypes to return
            by: Sort metric (usage, wins, top8)
        """
        stats = self.calculate_stats()
        
        sort_key = {
            "usage": lambda x: x.usage_rate,
            "wins": lambda x: x.win_count,
            "top8": lambda x: x.top8_count,
            "winrate": lambda x: x.win_rate
        }.get(by, lambda x: x.usage_rate)
        
        sorted_stats = sorted(stats.values(), key=sort_key, reverse=True)
        return sorted_stats[:n]
    
    def get_distribution_data(self) -> dict:
        """Get data formatted for chart display."""
        stats = self.calculate_stats()
        sorted_stats = sorted(stats.values(), key=lambda x: x.deck_count, reverse=True)
        
        # Get top 10 and group others
        top_archetypes = sorted_stats[:10]
        others_count = sum(s.deck_count for s in sorted_stats[10:])
        
        labels = [s.name for s in top_archetypes]
        values = [s.deck_count for s in top_archetypes]
        
        if others_count > 0:
            labels.append("Others")
            values.append(others_count)
        
        return {
            "labels": labels,
            "values": values,
            "total": sum(s.deck_count for s in stats.values())
        }
    
    def get_archetype_detail(self, archetype_name: str) -> dict:
        """Get detailed statistics for a specific archetype."""
        stats = self.calculate_stats()
        
        if archetype_name not in stats:
            return {"error": "Archetype not found"}
        
        s = stats[archetype_name]
        
        return {
            "name": s.name,
            "deck_count": s.deck_count,
            "top8_count": s.top8_count,
            "top4_count": s.top4_count,
            "win_count": s.win_count,
            "usage_rate": round(s.usage_rate * 100, 2),
            "win_rate": round(s.win_rate * 100, 2),
            "top8_rate": round(s.top8_rate * 100, 2)
        }
    
    def get_recent_decks(self, archetype_name: str, limit: int = 5) -> list[dict]:
        """
        Get recent decks for a specific archetype.
        
        Args:
            archetype_name: Name of the archetype
            limit: Maximum number of decks to return
            
        Returns:
            List of deck dictionaries sorted by date (newest first)
        """
        recent_decks = []
        
        for tournament in self.tournaments:
            t_date = tournament.get("date", "")
            t_name = tournament.get("name", "")
            
            for deck in tournament.get("decks", []):
                if deck.get("archetype") == archetype_name:
                    deck_info = {
                        "player_name": deck.get("player_name", "Unknown"),
                        "placement": deck.get("placement"),
                        "date": t_date,
                        "tournament": t_name,
                        "deck_url": deck.get("deck_url")
                    }
                    recent_decks.append(deck_info)
        
        # Sort by date (descending) and then placement (ascending)
        recent_decks.sort(key=lambda x: (x["date"], -x["placement"] if x["placement"] else -999), reverse=True)
        
        return recent_decks[:limit]
