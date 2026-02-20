"""
Data manager for caching and efficient data access.
"""
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from ..scraper.limitless import LimitlessScraper
from ..utils.card_db import CardDB
from ..utils.date_utils import get_week_key, get_previous_week


class DataManager:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DataManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, data_dir: Optional[Path] = None):
        if self._initialized:
            return
            
        self.data_dir = data_dir or Path("data")
        self._data: Optional[Dict[str, Any]] = None
        self._last_loaded: float = 0
        self._card_db: Optional[CardDB] = None
        self._cache_ttl = 300  # 5 minutes
        
        # Pre-calculated indexes
        self._tournaments_by_week: Dict[str, List[Dict]] = {}
        self._weeks: List[str] = []
        
        self._initialized = True
    
    def get_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get cached data, reloading if necessary."""
        current_time = time.time()
        
        if self._data is None or force_refresh or (current_time - self._last_loaded > self._cache_ttl):
            print(f"Loading data from disk... (Force: {force_refresh})")
            scraper = LimitlessScraper(cache_dir=str(self.data_dir))
            loaded_data = scraper.load_cached_data()
            
            if loaded_data:
                self._data = loaded_data
                self._last_loaded = current_time
                self._build_indexes()
            else:
                self._data = {"tournaments": [], "metagame": [], "scraped_at": None}
                
        return self._data
    
    def _build_indexes(self):
        """Pre-calculate common lookup structures."""
        self._tournaments_by_week = {}
        weeks_set = set()
        
        for t in self._data.get("tournaments", []):
            week = get_week_key(t.get("date", ""))
            if week not in self._tournaments_by_week:
                self._tournaments_by_week[week] = []
            self._tournaments_by_week[week].append(t)
            weeks_set.add(week)
            
        self._weeks = sorted(list(weeks_set))
        print("Data indexes built.")

    def get_card_db(self) -> CardDB:
        """Get or create singleton CardDB connection."""
        if self._card_db is None:
            db_path = self.data_dir / "ptcg_hij.sqlite"
            self._card_db = CardDB(db_path=str(db_path))
        return self._card_db

    def get_window_data(self, target_week: str = None, window_size: int = 2) -> Dict[str, Any]:
        """
        Get data filtered by window directly from indexes if possible.
        Refactored version of filter_data_window.
        """
        data = self.get_data()
        tournaments = data.get("tournaments", [])
        
        if not tournaments:
            return data
            
        # 1. Determine Target Week
        if target_week is None:
            if self._weeks:
                target_week = self._weeks[-1]
            else:
                return data
        
        # 2. Determine Allowed Weeks
        allowed_weeks = {target_week}
        current = target_week
        for _ in range(window_size - 1):
            prev = get_previous_week(current)
            allowed_weeks.add(prev)
            current = prev
            
        # 3. Collect tournaments from index
        filtered_tournaments = []
        for week in allowed_weeks:
            if week in self._tournaments_by_week:
                filtered_tournaments.extend(self._tournaments_by_week[week])
                
        # Shallow copy is significantly faster than deep copy
        new_data = {
            k: v for k, v in data.items() if k != "tournaments"
        }
        new_data["tournaments"] = filtered_tournaments
        return new_data

    def get_history_data(self, target_week: str = None) -> Dict[str, Any]:
        """
        Get data filtered by history (up to target week).
        """
        data = self.get_data()
        
        if target_week is None:
            if self._weeks:
                # If target is latest, return everything
                return data
            return data
            
        # Filter tournaments using week comparison string
        filtered_tournaments = []
        # We can iterate over weeks since we have them sorted in self._weeks (if we relied on it)
        # But safest to iterate all or optimized if self._weeks is reliable.
        # self._weeks is sorted.
        
        valid_weeks = [w for w in self._weeks if w <= target_week]
        for week in valid_weeks:
             if week in self._tournaments_by_week:
                filtered_tournaments.extend(self._tournaments_by_week[week])
                
        new_data = {
            k: v for k, v in data.items() if k != "tournaments"
        }
        new_data["tournaments"] = filtered_tournaments
        return new_data

    def get_all_weeks(self) -> List[str]:
        self.get_data() # Ensure loaded
        return self._weeks
