"""
Card usage analysis for PTCG deck archetypes.
Provides core card, tech card, and ACE SPEC analysis.
"""
from collections import defaultdict
from typing import Optional


class CardAnalyzer:
    """Analyzes card usage patterns within deck archetypes."""
    
    # Known ACE SPEC cards
    ACE_SPEC_CARDS = [
        "Prime Catcher", "Master Ball", "Unfair Stamp", "Maximum Belt",
        "Hero's Cape", "Deluxe Bomb", "Survival Brace", "Reboot Pod",
        "Energy Recycler", "Hyper Aroma", "Secret Box", "Sparkling Crystal",
        "Dangerous Laser", "Legacy Energy", "Miracle Headset", "Luminous Energy",
        "Giant Cape", "Grand Tree", "Amulet of Hope", "Brilliant Blender",
        # Japanese names
        "プライムキャッチャー", "マスターボール", "アンフェアスタンプ"
    ]
    
    def __init__(self, data: dict, card_db=None):
        """
        Initialize with scraped data.
        
        Args:
            data: Dictionary containing scraped tournament and deck data
            card_db: Optional CardDB instance for fetching card images/translations
        """
        self.data = data
        self.tournaments = data.get("tournaments", [])
        self._card_cache = {}
        self.card_db = card_db
    
    def _get_decks_for_archetype(self, archetype: str) -> list[dict]:
        """Get all decks matching an archetype that have card data."""
        decks = []
        archetype_lower = archetype.lower()
        
        for tournament in self.tournaments:
            for deck in tournament.get("decks", []):
                deck_archetype = deck.get("archetype", "").lower()
                if deck_archetype == archetype_lower and deck.get("cards"):
                    decks.append(deck)
        
        return decks
    
    def _is_ace_spec(self, card_name: str) -> bool:
        """Check if a card is an ACE SPEC."""
        for ace in self.ACE_SPEC_CARDS:
            if ace.lower() in card_name.lower():
                return True
        return False
    
    def get_card_usage(self, archetype: str) -> dict:
        """
        Get card usage statistics for an archetype.
        
        Args:
            archetype: Name of the archetype
        
        Returns:
            Dictionary with card usage data including core cards, tech cards, ACE SPECs
        """
        decks = self._get_decks_for_archetype(archetype)
        
        if not decks:
            return {
                "archetype": archetype,
                "deck_count": 0,
                "core_cards": [],
                "tech_cards": [],
                "ace_specs": [],
                "pokemon": [],
                "trainers": [],
                "energy": []
            }
        
        # Count card occurrences and quantities
        card_stats = defaultdict(lambda: {
            "count": 0,  # Number of decks using this card
            "total_copies": 0,  # Total copies across all decks
            "min_copies": float('inf'),
            "max_copies": 0,
            "card_type": "Pokemon",
            "representative_set": None,
            "representative_number": None
        })
        
        for deck in decks:
            seen_cards = set()
            for card in deck.get("cards", []):
                name = card.get("name", "")
                count = card.get("count", 1)
                card_type = card.get("card_type", "Pokemon")
                
                if name not in seen_cards:
                    card_stats[name]["count"] += 1
                    seen_cards.add(name)
                
                card_stats[name]["total_copies"] += count
                card_stats[name]["min_copies"] = min(card_stats[name]["min_copies"], count)
                card_stats[name]["max_copies"] = max(card_stats[name]["max_copies"], count)
                card_stats[name]["card_type"] = card_type
                
                # Capture representative set/number for mapping
                if not card_stats[name]["representative_set"] and "set_code" in card:
                    card_stats[name]["representative_set"] = card.get("set_code")
                    # Handle card_id sometimes usually being "SET-NUMBER"
                    card_id_parts = card.get("card_id", "").split("-")
                    if len(card_id_parts) > 1:
                        card_stats[name]["representative_number"] = card_id_parts[-1]
        
        deck_count = len(decks)
        
        # Process cards into categories
        core_cards = []
        tech_cards = []
        ace_specs = []
        pokemon = []
        trainers = []
        energy = []
        
        for card_name, stats in card_stats.items():
            usage_rate = (stats["count"] / deck_count) * 100
            avg_copies = stats["total_copies"] / stats["count"] if stats["count"] > 0 else 0
            
            card_info = {
                "name": card_name,
                "usage_rate": round(usage_rate, 1),
                "avg_copies": round(avg_copies, 1),
                "min_copies": stats["min_copies"] if stats["min_copies"] != float('inf') else 0,
                "max_copies": stats["max_copies"],
                "deck_count": stats["count"],
                "card_type": stats["card_type"]
            }
            
            # Enrich with DB info
            if self.card_db and stats["representative_set"] and stats["representative_number"]:
                db_info = self.card_db.get_card_info(
                    stats["representative_set"], 
                    stats["representative_number"],
                    english_name=card_name
                )
                if db_info:
                    card_info["name_zh"] = db_info.get("name_zh")
                    card_info["image_url"] = db_info.get("image_url")
            
            # Categorize by type
            if stats["card_type"] == "Pokemon":
                pokemon.append(card_info)
            elif stats["card_type"] == "Trainer":
                trainers.append(card_info)
            elif stats["card_type"] == "Energy":
                energy.append(card_info)
            
            # Check if ACE SPEC
            if self._is_ace_spec(card_name):
                ace_specs.append(card_info)
            # Core cards: high usage rate (>= 80%)
            elif usage_rate >= 80:
                core_cards.append(card_info)
            # Tech cards: moderate usage rate (20-80%)
            elif 20 <= usage_rate < 80:
                tech_cards.append(card_info)
        
        # Sort by usage rate
        for lst in [core_cards, tech_cards, ace_specs, pokemon, trainers, energy]:
            lst.sort(key=lambda x: (-x["usage_rate"], -x["avg_copies"]))
        
        return {
            "archetype": archetype,
            "deck_count": deck_count,
            "core_cards": core_cards[:20],  # Top 20 core cards
            "tech_cards": tech_cards[:20],  # Top 20 tech cards
            "ace_specs": ace_specs,
            "pokemon": pokemon[:15],
            "trainers": trainers[:20],
            "energy": energy[:10]
        }
    
    def get_core_cards(self, archetype: str, min_usage: float = 80.0) -> list[dict]:
        """
        Get core (staple) cards for an archetype.
        
        Args:
            archetype: Name of the archetype
            min_usage: Minimum usage rate to be considered core (default 80%)
        
        Returns:
            List of core card dictionaries
        """
        usage = self.get_card_usage(archetype)
        return [c for c in usage["core_cards"] if c["usage_rate"] >= min_usage]
    
    def get_tech_cards(self, archetype: str, min_usage: float = 20.0, max_usage: float = 80.0) -> list[dict]:
        """
        Get tech (optional) cards for an archetype.
        
        Args:
            archetype: Name of the archetype
            min_usage: Minimum usage rate (default 20%)
            max_usage: Maximum usage rate (default 80%)
        
        Returns:
            List of tech card dictionaries
        """
        usage = self.get_card_usage(archetype)
        return [c for c in usage["tech_cards"] if min_usage <= c["usage_rate"] < max_usage]
    
    def get_ace_spec_usage(self, archetype: str) -> list[dict]:
        """
        Get ACE SPEC card usage for an archetype.
        
        Args:
            archetype: Name of the archetype
        
        Returns:
            List of ACE SPEC card dictionaries with usage stats
        """
        usage = self.get_card_usage(archetype)
        return usage["ace_specs"]
    
    def get_building_trends(self, archetype: str) -> dict:
        """
        Get deck building trends for an archetype.
        
        Args:
            archetype: Name of the archetype
        
        Returns:
            Dictionary with building trend data
        """
        usage = self.get_card_usage(archetype)
        
        if usage["deck_count"] == 0:
            return {
                "archetype": archetype,
                "deck_count": 0,
                "avg_pokemon": 0,
                "avg_trainers": 0,
                "avg_energy": 0,
                "popular_pokemon": [],
                "popular_trainers": [],
                "popular_energy": [],
                "ace_spec_preference": []
            }
        
        # Calculate averages from card type distribution
        pokemon_total = sum(c["avg_copies"] * c["deck_count"] for c in usage["pokemon"]) / usage["deck_count"] if usage["pokemon"] else 0
        trainer_total = sum(c["avg_copies"] * c["deck_count"] for c in usage["trainers"]) / usage["deck_count"] if usage["trainers"] else 0
        energy_total = sum(c["avg_copies"] * c["deck_count"] for c in usage["energy"]) / usage["deck_count"] if usage["energy"] else 0
        
        return {
            "archetype": archetype,
            "deck_count": usage["deck_count"],
            "avg_pokemon": round(pokemon_total, 1),
            "avg_trainers": round(trainer_total, 1),
            "avg_energy": round(energy_total, 1),
            "popular_pokemon": usage["pokemon"][:10],
            "popular_trainers": usage["trainers"][:15],
            "popular_energy": usage["energy"][:8],
            "ace_spec_preference": usage["ace_specs"]
        }
    
    def get_all_archetypes_ace_specs(self) -> list[dict]:
        """
        Get ACE SPEC preferences for all archetypes.
        
        Returns:
            List of archetypes with their ACE SPEC preferences
        """
        # Get unique archetypes
        archetypes = set()
        for tournament in self.tournaments:
            for deck in tournament.get("decks", []):
                if deck.get("cards"):  # Only count decks with card data
                    archetypes.add(deck.get("archetype", ""))
        
        results = []
        for archetype in archetypes:
            if not archetype:
                continue
            ace_specs = self.get_ace_spec_usage(archetype)
            if ace_specs:
                results.append({
                    "archetype": archetype,
                    "ace_specs": ace_specs
                })
        
        # Sort by deck count
        results.sort(key=lambda x: -sum(a["deck_count"] for a in x["ace_specs"]))
        
        return results[:20]
