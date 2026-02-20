"""
Archetype distribution analysis.
"""
from collections import Counter, defaultdict
from typing import Optional, List, Dict

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
        self._decks_by_archetype: Optional[Dict[str, List[dict]]] = None
        
    def _build_index(self):
        """Build index of decks by archetype."""
        if self._decks_by_archetype is not None:
            return

        self._decks_by_archetype = defaultdict(list)
        for tournament in self.tournaments:
            t_date = tournament.get("date", "")
            t_name = tournament.get("name", "")
            
            for deck in tournament.get("decks", []):
                archetype = deck.get("archetype", "Unknown")
                # Store enriched deck info for easy access
                # We store a reference to the deck + tournament metadata needed often
                deck_entry = {
                    "deck": deck,
                    "date": t_date,
                    "tournament": t_name,
                    "placement": deck.get("placement")
                }
                self._decks_by_archetype[archetype].append(deck_entry)

    def calculate_stats(self) -> dict[str, ArchetypeStats]:
        """Calculate statistics for all archetypes."""
        if self._archetype_stats:
            return self._archetype_stats
        
        self._build_index()
        
        stats: dict[str, ArchetypeStats] = {}
        total_decks = 0
        
        for archetype, entries in self._decks_by_archetype.items():
            s = ArchetypeStats(name=archetype)
            s.deck_count = len(entries)
            total_decks += s.deck_count
            
            for entry in entries:
                placement = entry["placement"]
                if placement:
                    if placement <= 8:
                        s.top8_count += 1
                    if placement <= 4:
                        s.top4_count += 1
                    if placement == 1:
                        s.win_count += 1
            stats[archetype] = s
        
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
        
        # Sort values directly
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
            return {"error": "Archetype not found", "name": archetype_name}
        
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
        Uses cached index for O(1) lookup + sort.
        """
        self._build_index()
        entries = self._decks_by_archetype.get(archetype_name, [])
        
        recent_decks = []
        for entry in entries:
            deck = entry["deck"]
            recent_decks.append({
                "player_name": deck.get("player_name", "Unknown"),
                "placement": entry["placement"],
                "date": entry["date"],
                "tournament": entry["tournament"],
                "deck_url": deck.get("deck_url")
            })
            
        # Sort by date (descending) and then placement (ascending)
        recent_decks.sort(key=lambda x: (x["date"], -x["placement"] if x["placement"] else -999), reverse=True)
        
        return recent_decks[:limit]

    def calculate_consensus_score(self, archetype_name: str) -> float:
        """
        Calculate Consensus Score for an archetype.
        """
        self._build_index()
        entries = self._decks_by_archetype.get(archetype_name, [])
        
        decks = []
        for entry in entries:
            deck = entry["deck"]
            if deck.get("cards"):
                decks.append(deck["cards"])
        
        if not decks:
            return 0.0
        
        # 1. Build Master List
        card_counts = Counter()
        for deck_cards in decks:
            unique_cards = set(c["name"] for c in deck_cards)
            card_counts.update(unique_cards)
            
        total_decks = len(decks)
        master_list = {
            card for card, count in card_counts.items() 
            if count > (total_decks * 0.5)
        }
        
        if not master_list:
            return 0.0
            
        # 2. Calculate Similarity
        similarity_scores = []
        for deck_cards in decks:
            deck_set = set(c["name"] for c in deck_cards)
            overlap = len(deck_set.intersection(master_list))
            score = overlap / len(master_list)
            similarity_scores.append(score)
            
        # 3. Average Score
        return sum(similarity_scores) / len(similarity_scores)
