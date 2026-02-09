"""
Data models for PTCG deck analysis.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Card:
    """Represents a single card in a deck."""
    name: str
    count: int
    card_id: Optional[str] = None
    set_code: Optional[str] = None
    card_type: Optional[str] = None  # Pokemon, Trainer, Energy


@dataclass
class Deck:
    """Represents a complete deck list."""
    archetype: str
    cards: list[Card] = field(default_factory=list)
    player_name: Optional[str] = None
    player_id: Optional[str] = None
    placement: Optional[int] = None
    tournament_id: Optional[str] = None
    deck_url: Optional[str] = None  # URL to the deck list page
    
    @property
    def pokemon_cards(self) -> list[Card]:
        return [c for c in self.cards if c.card_type == "Pokemon"]
    
    @property
    def trainer_cards(self) -> list[Card]:
        return [c for c in self.cards if c.card_type == "Trainer"]
    
    @property
    def energy_cards(self) -> list[Card]:
        return [c for c in self.cards if c.card_type == "Energy"]


@dataclass
class Tournament:
    """Represents a City League tournament."""
    tournament_id: str
    name: str
    date: date
    location: str  # Prefecture
    shop: str
    decks: list[Deck] = field(default_factory=list)
    
    @property
    def winner_deck(self) -> Optional[Deck]:
        for deck in self.decks:
            if deck.placement == 1:
                return deck
        return None


@dataclass
class ArchetypeStats:
    """Statistics for a deck archetype."""
    name: str
    deck_count: int = 0
    top8_count: int = 0
    top4_count: int = 0
    win_count: int = 0
    usage_rate: float = 0.0
    win_rate: float = 0.0
    top8_rate: float = 0.0


@dataclass
class CardUsage:
    """Card usage statistics within an archetype."""
    card_name: str
    appearance_rate: float  # % of decks that include this card
    avg_count: float  # Average copies per deck
    min_count: int
    max_count: int


@dataclass
class MatchupData:
    """Matchup data between two archetypes."""
    archetype1: str
    archetype2: str
    archetype1_wins: int = 0
    archetype2_wins: int = 0
    total_matches: int = 0
    
    @property
    def archetype1_winrate(self) -> float:
        if self.total_matches == 0:
            return 0.5
        return self.archetype1_wins / self.total_matches
