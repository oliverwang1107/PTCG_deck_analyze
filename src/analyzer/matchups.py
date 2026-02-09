"""
Matchup analysis between archetypes.
"""
from collections import defaultdict
from itertools import combinations
from typing import Optional

from ..scraper.models import MatchupData


class MatchupAnalyzer:
    """Analyzes matchups between deck archetypes."""
    
    def __init__(self, data: dict):
        """
        Initialize with scraped data.
        
        Args:
            data: Scraped data dictionary from LimitlessScraper
        """
        self.data = data
        self.tournaments = data.get("tournaments", [])
        self._matchup_matrix: Optional[dict] = None
    
    def calculate_matchups(self) -> dict[tuple[str, str], MatchupData]:
        """
        Calculate matchup data between archetypes.
        
        This is an estimation based on tournament standings:
        When archetype A finishes above archetype B in the same tournament,
        we count it as a favorable result for A.
        """
        matchups: dict[tuple[str, str], MatchupData] = {}
        
        for tournament in self.tournaments:
            decks = tournament.get("decks", [])
            
            # Compare all pairs of different archetypes
            for i, deck1 in enumerate(decks):
                for deck2 in decks[i+1:]:
                    arch1 = deck1.get("archetype", "Unknown")
                    arch2 = deck2.get("archetype", "Unknown")
                    
                    if arch1 == arch2:
                        continue
                    
                    place1 = deck1.get("placement") or 999
                    place2 = deck2.get("placement") or 999
                    
                    # Normalize key order
                    if arch1 > arch2:
                        arch1, arch2 = arch2, arch1
                        place1, place2 = place2, place1
                    
                    key = (arch1, arch2)
                    if key not in matchups:
                        matchups[key] = MatchupData(
                            archetype1=arch1,
                            archetype2=arch2
                        )
                    
                    matchups[key].total_matches += 1
                    if place1 < place2:
                        matchups[key].archetype1_wins += 1
                    else:
                        matchups[key].archetype2_wins += 1
        
        return matchups
    
    def get_matchup_matrix(self, top_n: int = 10) -> dict:
        """
        Get matchup matrix for top N archetypes.
        
        Args:
            top_n: Number of top archetypes to include
        
        Returns:
            Matrix data for visualization
        """
        if self._matchup_matrix:
            return self._matchup_matrix
        
        matchups = self.calculate_matchups()
        
        # Find top archetypes by total appearances
        archetype_counts: dict[str, int] = defaultdict(int)
        for tournament in self.tournaments:
            for deck in tournament.get("decks", []):
                archetype_counts[deck.get("archetype", "Unknown")] += 1
        
        top_archetypes = sorted(
            archetype_counts.keys(),
            key=lambda x: archetype_counts[x],
            reverse=True
        )[:top_n]
        
        # Build matrix
        matrix = {}
        for arch1 in top_archetypes:
            matrix[arch1] = {}
            for arch2 in top_archetypes:
                if arch1 == arch2:
                    matrix[arch1][arch2] = {"winrate": 50, "matches": 0}
                else:
                    # Find matchup data
                    key = tuple(sorted([arch1, arch2]))
                    if key in matchups:
                        m = matchups[key]
                        if m.total_matches > 0:
                            if key[0] == arch1:
                                winrate = m.archetype1_winrate * 100
                            else:
                                winrate = (1 - m.archetype1_winrate) * 100
                            matrix[arch1][arch2] = {
                                "winrate": round(winrate, 1),
                                "matches": m.total_matches
                            }
                        else:
                            matrix[arch1][arch2] = {"winrate": 50, "matches": 0}
                    else:
                        matrix[arch1][arch2] = {"winrate": 50, "matches": 0}
        
        self._matchup_matrix = {
            "archetypes": top_archetypes,
            "matrix": matrix
        }
        
        return self._matchup_matrix
    
    def get_archetype_matchups(self, archetype: str) -> dict:
        """
        Get matchup data for a specific archetype.
        
        Args:
            archetype: Archetype name to analyze
        
        Returns:
            Dictionary with favorable, unfavorable, and even matchups
        """
        matchups = self.calculate_matchups()
        
        favorable = []
        unfavorable = []
        even = []
        
        for key, data in matchups.items():
            if archetype not in key:
                continue
            
            opponent = key[1] if key[0] == archetype else key[0]
            
            if key[0] == archetype:
                winrate = data.archetype1_winrate
            else:
                winrate = 1 - data.archetype1_winrate
            
            matchup_info = {
                "opponent": opponent,
                "winrate": round(winrate * 100, 1),
                "matches": data.total_matches
            }
            
            if data.total_matches < 3:
                even.append(matchup_info)
            elif winrate > 0.55:
                favorable.append(matchup_info)
            elif winrate < 0.45:
                unfavorable.append(matchup_info)
            else:
                even.append(matchup_info)
        
        # Sort by winrate
        favorable.sort(key=lambda x: x["winrate"], reverse=True)
        unfavorable.sort(key=lambda x: x["winrate"])
        
        return {
            "archetype": archetype,
            "favorable": favorable,
            "unfavorable": unfavorable,
            "even": even
        }
    
    def get_heatmap_data(self, top_n: int = 10) -> dict:
        """Get data formatted for heatmap visualization."""
        matrix_data = self.get_matchup_matrix(top_n)
        archetypes = matrix_data["archetypes"]
        matrix = matrix_data["matrix"]
        
        # Convert to 2D array for heatmap
        values = []
        for arch1 in archetypes:
            row = []
            for arch2 in archetypes:
                row.append(matrix[arch1][arch2]["winrate"])
            values.append(row)
        
        return {
            "labels": archetypes,
            "values": values
        }
