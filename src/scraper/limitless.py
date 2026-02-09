"""
Limitless TCG Scraper for Japan City League data.
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import Card, Deck, Tournament


class LimitlessScraper:
    """Scraper for Limitless TCG Japan City League data."""
    
    BASE_URL = "https://limitlesstcg.com"
    TOURNAMENTS_URL = f"{BASE_URL}/tournaments/jp"
    DECKS_URL = f"{BASE_URL}/decks"
    
    def __init__(self, cache_dir: str = "data", delay: float = 1.0):
        """
        Initialize the scraper.
        
        Args:
            cache_dir: Directory to store cached data
            delay: Delay between requests in seconds
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PTCG-Analyzer/1.0 (Educational Research)"
        })
    
    def _get(self, url: str) -> BeautifulSoup:
        """Fetch a URL and return parsed HTML."""
        time.sleep(self.delay)
        response = self.session.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")
    
    def get_tournament_list(self, page: int = 1, limit: Optional[int] = None) -> list[dict]:
        """
        Get list of tournaments from the City League page.
        
        Args:
            page: Page number to fetch
            limit: Maximum number of tournaments to fetch (across all pages)
        
        Returns:
            List of tournament info dictionaries
        """
        tournaments = []
        current_page = page
        seen_ids = set()
        
        while True:
            url = f"{self.TOURNAMENTS_URL}?page={current_page}"
            print(f"Fetching tournament list page {current_page}...")
            
            soup = self._get(url)
            
            # Find tournament links directly - they contain /tournaments/jp/ pattern
            tournament_links = soup.select("a[href*='/tournaments/jp/']")
            
            page_tournaments = 0
            for link in tournament_links:
                href = link.get("href", "")
                match = re.search(r"/tournaments/jp/(\d+)", href)
                if match:
                    tournament_id = match.group(1)
                    
                    # Skip if already seen (links may appear multiple times)
                    if tournament_id in seen_ids:
                        continue
                    seen_ids.add(tournament_id)
                    
                    # Get text content (usually date)
                    date_text = link.get_text(strip=True)
                    
                    # Try to find location and shop from sibling/parent elements
                    location = ""
                    shop = ""
                    
                    # Look for siblings in the same row
                    parent = link.find_parent("tr")
                    if parent:
                        sibling_links = parent.select("a")
                        for i, sib in enumerate(sibling_links):
                            sib_href = sib.get("href", "")
                            if f"/tournaments/jp/{tournament_id}" in sib_href:
                                # This is the tournament link, get siblings
                                if i + 1 < len(sibling_links):
                                    location = sibling_links[i + 1].get_text(strip=True)
                                if i + 2 < len(sibling_links):
                                    shop = sibling_links[i + 2].get_text(strip=True)
                                break
                    
                    tournament = {
                        "id": tournament_id,
                        "date_text": date_text,
                        "location": location,
                        "shop": shop,
                        "url": urljoin(self.BASE_URL, href)
                    }
                    tournaments.append(tournament)
                    page_tournaments += 1
                    
                    if limit and len(tournaments) >= limit:
                        return tournaments
            
            # If no new tournaments found on this page, stop
            if page_tournaments == 0:
                break
            
            # Check for next page link
            next_link = soup.select_one("a[rel='next'], .pagination a:contains('»')")
            if not next_link or (limit and len(tournaments) >= limit):
                break
            
            current_page += 1
            
            # Safety limit
            if current_page > 200:
                break
        
        return tournaments
    
    def get_tournament_details(self, tournament_id: str) -> Optional[Tournament]:
        """
        Get detailed tournament data including deck placements.
        
        Args:
            tournament_id: Tournament ID from Limitless TCG
        
        Returns:
            Tournament object with deck data
        """
        url = f"{self.TOURNAMENTS_URL}/{tournament_id}"
        print(f"Fetching tournament {tournament_id} details...")
        
        soup = self._get(url)
        
        # Extract tournament info from page title or header
        title = soup.select_one("h1, .tournament-title")
        title_text = title.get_text(strip=True) if title else f"Tournament {tournament_id}"
        
        # Parse date and location from title or page info
        location = ""
        shop = ""
        tournament_date = datetime.now().date()
        
        # Look for tournament info in the page
        info_elements = soup.select(".tournament-info span, .info-line")
        for elem in info_elements:
            text = elem.get_text(strip=True)
            if "Prefecture" in text or any(p in text for p in ["Tokyo", "Osaka", "Aichi"]):
                location = text
        
        # Extract deck placements - use direct tr selection (some pages don't have tbody)
        decks = []
        standings_rows = soup.select("table tr")
        
        for row in standings_rows:
            # Skip header rows
            if row.select("th"):
                continue
            
            cells = row.select("td")
            if len(cells) >= 2:
                # First cell usually has placement
                placement_text = cells[0].get_text(strip=True)
                placement_match = re.match(r"(\d+)", placement_text)
                placement = int(placement_match.group(1)) if placement_match else None
                
                # Skip rows without valid placement
                if placement is None:
                    continue
                
                # Find player link and archetype info
                player_link = row.select_one("a[href*='/players/']")
                player_name = player_link.get_text(strip=True) if player_link else ""
                player_id = ""
                if player_link:
                    player_match = re.search(r"/players/(?:jp/)?(\S+)", player_link.get("href", ""))
                    player_id = player_match.group(1) if player_match else ""
                
                # Try to find deck URL (link to deck list page)
                deck_url = None
                deck_link = row.select_one("a[href*='/decks/']")
                if deck_link:
                    href = deck_link.get("href", "")
                    if href.startswith("http"):
                        deck_url = href
                    else:
                        deck_url = f"{self.BASE_URL}{href}"
                
                # Try to find deck archetype from icons or text
                archetype = self._extract_archetype(row)
                
                deck = Deck(
                    archetype=archetype,
                    player_name=player_name,
                    player_id=player_id,
                    placement=placement,
                    tournament_id=tournament_id,
                    deck_url=deck_url
                )
                decks.append(deck)
        
        return Tournament(
            tournament_id=tournament_id,
            name=title_text,
            date=tournament_date,
            location=location,
            shop=shop,
            decks=decks
        )
    
    def _extract_archetype(self, row) -> str:
        """Extract archetype name from a tournament standings row."""
        # Look for archetype link first
        archetype_link = row.select_one("a[href*='/decks/']")
        if archetype_link:
            text = archetype_link.get_text(strip=True)
            if text:
                return text
        
        # Look for Pokemon card images - get all img tags
        images = row.select("img")
        pokemon_names = []
        for img in images:
            alt = img.get("alt")
            if alt and alt.strip():
                pokemon_names.append(alt.strip())
        
        if pokemon_names:
            # Join first two Pokemon names to create archetype
            return " / ".join(pokemon_names[:2])
        
        return "Unknown"
    
    def get_deck_cards(self, deck_url: str) -> list[Card]:
        """
        Fetch card list from a deck URL.
        
        Args:
            deck_url: URL to the Limitless deck page
        
        Returns:
            List of Card objects
        """
        try:
            soup = self._get(deck_url)
            cards = []
            
            # Find all card entries in the decklist
            card_entries = soup.select('.decklist-card')
            
            # Track current section for card type
            current_type = "Pokemon"
            
            # Also check container text for section detection
            decklist_text = soup.select_one('.decklist')
            if decklist_text:
                full_text = decklist_text.get_text()
            else:
                full_text = ""
            
            for entry in card_entries:
                # Get the card link for name
                card_link = entry.select_one('a.card-link')
                if not card_link:
                    continue
                
                # Extract card name and count from text (format: "4CardName")
                card_text = card_link.get_text(strip=True)
                count_match = re.match(r'(\d+)(.+)', card_text)
                
                if count_match:
                    count = int(count_match.group(1))
                    name = count_match.group(2).strip()
                else:
                    name = card_text
                    count = 1
                
                # Get card identifiers from data attributes
                set_code = entry.get('data-set', '')
                card_number = entry.get('data-number', '')
                card_id = f"{set_code}-{card_number}" if set_code and card_number else ""
                
                # Determine card type based on common patterns
                card_type = self._determine_card_type(name)
                
                card = Card(
                    name=name,
                    count=count,
                    card_id=card_id,
                    set_code=set_code,
                    card_type=card_type
                )
                cards.append(card)
            
            return cards
            
        except Exception as e:
            print(f"Error fetching deck cards from {deck_url}: {e}")
            return []
    
    def _determine_card_type(self, card_name: str) -> str:
        """Determine card type (Pokemon/Trainer/Energy) from card name."""
        # Energy patterns
        energy_patterns = ['Energy', 'エネルギー']
        for pattern in energy_patterns:
            if pattern.lower() in card_name.lower():
                return "Energy"
        
        # Trainer card patterns (Items, Supporters, Tools, Stadiums)
        trainer_patterns = [
            'Professor', 'Boss', 'Judge', 'Iono', 'Catcher', 'Ball', 'Rare Candy',
            'Switch', 'Nest Ball', 'Ultra Ball', 'Stadium', 'Tool', 'Supporter',
            'Trekking Shoes', 'Research', 'Roxanne', 'Arven', 'Irida', 'Cynthia',
            'N', 'Guzma', 'Marnie', 'Colress', 'Raihan', 'Belt', 'Scope', 'Rod',
            'Rescue Board', 'Energy Retrieval', 'Super Rod', 'Buddy-Buddy', 'Pal Pad',
            'Night Stretcher', 'Technical Machine', 'Counter Gain', 'Unfair Stamp',
            'Prime Catcher', 'Energy Search', 'Potion', 'Full Heal', 'Revive',
            'Max Elixir', 'Vs Seeker', 'Double Turbo', 'Jet', 'Gift', 'ACE SPEC',
            '博士', '老闆', '裁判', 'ボス', 'ナンジャモ', 'エリカ'
        ]
        for pattern in trainer_patterns:
            if pattern.lower() in card_name.lower():
                return "Trainer"
        
        # Default to Pokemon for most other cards
        return "Pokemon"
    
    def get_metagame_data(self, time_range: str = "1month", region: str = "JP") -> list[dict]:
        """
        Get metagame archetype statistics.
        
        Args:
            time_range: Time range (1week, 1month, 3months, etc.)
            region: Region filter (JP for Japan)
        
        Returns:
            List of archetype statistics
        """
        url = f"{self.DECKS_URL}?game=PTCG&format=standard&time={time_range}&region={region}"
        print(f"Fetching metagame data...")
        
        soup = self._get(url)
        
        archetypes = []
        deck_rows = soup.select(".deck-row, table tbody tr")
        
        for row in deck_rows:
            name_elem = row.select_one("a[href*='/decks/']")
            if not name_elem:
                continue
            
            name = name_elem.get_text(strip=True)
            
            # Extract statistics from row
            stats_cells = row.select("td, .stat")
            
            archetype_data = {
                "name": name,
                "deck_count": 0,
                "usage_rate": 0.0,
                "top8_count": 0,
                "win_count": 0
            }
            
            # Parse numerical values from cells
            for cell in stats_cells:
                text = cell.get_text(strip=True)
                if "%" in text:
                    try:
                        archetype_data["usage_rate"] = float(text.replace("%", "")) / 100
                    except ValueError:
                        pass
                elif text.isdigit():
                    if archetype_data["deck_count"] == 0:
                        archetype_data["deck_count"] = int(text)
            
            archetypes.append(archetype_data)
        
        return archetypes
    
    def scrape_all(self, tournament_limit: Optional[int] = None, fetch_cards: bool = False) -> dict:
        """
        Scrape all available data.
        
        Args:
            tournament_limit: Maximum number of tournaments to scrape
            fetch_cards: If True, fetch detailed card lists for each deck (slower)
        
        Returns:
            Dictionary containing all scraped data
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        print("Starting full scrape...")
        if fetch_cards:
            print("Card list fetching is ENABLED - this will take longer")
        
        # Get tournament list (keep sequential as it's just pages)
        tournaments_info = self.get_tournament_list(limit=tournament_limit)
        print(f"Found {len(tournaments_info)} tournaments")
        
        # Get details for each tournament (Parallel)
        tournaments = []
        total_decks = 0
        print(f"Fetching {len(tournaments_info)} tournaments details (Parallel)...")
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_tid = {
                executor.submit(self.get_tournament_details, info["id"]): info["id"] 
                for info in tournaments_info
            }
            
            for future in as_completed(future_to_tid):
                tid = future_to_tid[future]
                try:
                    tournament = future.result()
                    if tournament:
                        tournaments.append(tournament)
                        total_decks += len(tournament.decks)
                except Exception as e:
                    print(f"Error fetching tournament {tid}: {e}")
        
        # Sort tournaments by date (since parallel fetching messes up order)
        tournaments.sort(key=lambda x: x.date, reverse=True)
        print(f"Found {total_decks} decks across {len(tournaments)} tournaments")
        
        # Optionally fetch card lists for each deck (Parallel)
        if fetch_cards:
            decks_to_fetch = []
            for t in tournaments:
                for d in t.decks:
                    if d.deck_url:
                        decks_to_fetch.append(d)
            
            total_fetches = len(decks_to_fetch)
            print(f"Fetching card lists for {total_fetches} decks (Parallel)...")
            
            fetched_count = 0
            with ThreadPoolExecutor(max_workers=8) as executor:
                # Map future to deck object so we can assign result back
                future_to_deck = {
                    executor.submit(self.get_deck_cards, d.deck_url): d 
                    for d in decks_to_fetch
                }
                
                for future in as_completed(future_to_deck):
                    deck = future_to_deck[future]
                    try:
                        cards = future.result()
                        deck.cards = cards
                        fetched_count += 1
                        if fetched_count % 10 == 0:
                            print(f"  [{fetched_count}/{total_fetches}] Fetched cards for {deck.archetype}...")
                    except Exception as e:
                        print(f"Error fetching cards for deck {deck.deck_url}: {e}")
            
            print(f"Fetched card lists for {fetched_count} decks")
        
        # Get metagame data
        metagame = self.get_metagame_data()
        
        # Prepare data for saving - now includes cards if fetched
        def deck_to_dict(d):
            deck_dict = {
                "archetype": d.archetype,
                "player_name": d.player_name,
                "player_id": d.player_id,
                "placement": d.placement,
                "deck_url": d.deck_url
            }
            # Include cards if available
            if d.cards:
                deck_dict["cards"] = [
                    {
                        "name": c.name,
                        "count": c.count,
                        "card_id": c.card_id,
                        "set_code": c.set_code,
                        "card_type": c.card_type
                    }
                    for c in d.cards
                ]
            return deck_dict
        
        data = {
            "scraped_at": datetime.now().isoformat(),
            "tournament_count": len(tournaments),
            "has_card_data": fetch_cards,
            "tournaments": [
                {
                    "id": t.tournament_id,
                    "name": t.name,
                    "date": t.date.isoformat(),
                    "location": t.location,
                    "shop": t.shop,
                    "decks": [deck_to_dict(d) for d in t.decks]
                }
                for t in tournaments
            ],
            "metagame": metagame
        }
        
        # Save to cache
        cache_file = self.cache_dir / "scraped_data.json"
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"Data saved to {cache_file}")
        return data
    
    def load_cached_data(self) -> Optional[dict]:
        """Load previously scraped data from cache."""
        cache_file = self.cache_dir / "scraped_data.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
