"""
Professional meta insight analysis for PTCG deck archetypes.

Provides:
- Tier System (S/A/B/C) based on composite power ranking
- Power Rankings with composite scoring
- Meta Health Score (Simpson's Diversity Index)
- Meta Share Trends (archetype share over time)
- Energy Profile analysis per archetype
"""
from collections import Counter, defaultdict
from typing import Optional, List, Dict, Any

from .archetype import ArchetypeAnalyzer
from .winrate import WinRateAnalyzer
from ..utils.date_utils import get_week_key, get_previous_week


# Energy type mapping based on common energy card names
ENERGY_TYPE_MAP = {
    "Fire Energy": "Fire",
    "Water Energy": "Water",
    "Lightning Energy": "Electric",
    "Grass Energy": "Grass",
    "Psychic Energy": "Psychic",
    "Darkness Energy": "Dark",
    "Fighting Energy": "Fighting",
    "Metal Energy": "Metal",
    "Dragon Energy": "Dragon",
    "Double Turbo Energy": "Colorless",
    "Jet Energy": "Colorless",
    "Reversal Energy": "Colorless",
    "Gift Energy": "Colorless",
    "Therapeutic Energy": "Colorless",
    "Luminous Energy": "Colorless",
    "Legacy Energy": "Colorless",
    "Neo Upper Energy": "Colorless",
    "Mist Energy": "Colorless",
    "Multi Energy": "Colorless",
}


class MetaInsightAnalyzer:
    """Professional-grade meta analysis for PTCG City League data."""

    # Power ranking weights
    WEIGHT_USAGE = 0.30
    WEIGHT_WINRATE = 0.40
    WEIGHT_TOP_CUT = 0.30

    def __init__(self, data: dict):
        """
        Initialize with scraped data.

        Args:
            data: Scraped data dictionary from LimitlessScraper
        """
        self.data = data
        self.tournaments = data.get("tournaments", [])
        self._archetype_analyzer = ArchetypeAnalyzer(data)
        self._winrate_analyzer = WinRateAnalyzer(data)
        self._power_rankings: Optional[List[Dict]] = None

    # ------------------------------------------------------------------ #
    #  Power Rankings
    # ------------------------------------------------------------------ #

    @staticmethod
    def _percentile_ranks(values: list) -> list:
        """Convert a list of raw values to percentile ranks (0-100).

        For *n* items sorted ascending the rank of the item at position *i*
        (0-based) is ``i / (n - 1) * 100``.  Ties receive the mean rank of
        the tied positions.
        """
        n = len(values)
        if n <= 1:
            return [50.0] * n

        indexed = sorted(enumerate(values), key=lambda x: x[1])
        ranks = [0.0] * n

        i = 0
        while i < n:
            j = i
            # find end of tie group
            while j < n - 1 and indexed[j + 1][1] == indexed[i][1]:
                j += 1
            # mean percentile for the tie group
            pct = ((i + j) / 2) / (n - 1) * 100
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = round(pct, 1)
            i = j + 1

        return ranks

    def calculate_power_rankings(self, min_entries: int = 3) -> List[Dict[str, Any]]:
        """
        Calculate composite power ranking for every archetype using
        percentile-rank scoring.

        Algorithm
        ---------
        1. For each metric (usage_rate, win_rate, top_cut_rate, consistency)
           compute the percentile rank among all qualifying archetypes (0-100).
        2. Composite = weighted sum of percentile ranks (weights below).
        3. Tier assignment is relative:
           - S  top 8 %  (elite decks)
           - A  top 25 % (strong decks)
           - B  top 55 % (viable decks)
           - C  remainder

        Returns:
            Sorted list of dicts with name, score, tier, and component metrics.
        """
        if self._power_rankings is not None:
            return self._power_rankings

        arch_stats = self._archetype_analyzer.calculate_stats()
        win_rates = self._winrate_analyzer.calculate_win_rates()

        # Collect raw values -- filter by minimum sample size
        entries = []
        for name, stats in arch_stats.items():
            if stats.deck_count < min_entries:
                continue
            wr_data = win_rates.get(name, {})

            # top_cut_rate: combined top-8 rate weighted towards higher placements
            #   1st-place counts triple, top4 counts double, top8 counts single
            top_cut_rate = 0.0
            if stats.deck_count > 0:
                weighted_top = (
                    stats.win_count * 3
                    + stats.top4_count * 2
                    + stats.top8_count * 1
                )
                # Normalize so max theoretical = 3 (every deck wins)
                top_cut_rate = weighted_top / (stats.deck_count * 3)

            entries.append({
                "name": name,
                "usage_rate": stats.usage_rate,            # 0-1
                "win_rate": stats.win_rate,                # 0-1
                "top_cut_rate": top_cut_rate,              # 0-1
                "deck_count": stats.deck_count,
                "win_count": stats.win_count,
                "top4_count": stats.top4_count,
                "top8_count": stats.top8_count,
                "performance_score": wr_data.get("performance_score", 0),
            })

        if not entries:
            self._power_rankings = []
            return []

        # ---- Percentile-rank each dimension ----
        usage_pcts = self._percentile_ranks([e["usage_rate"] for e in entries])
        wr_pcts = self._percentile_ranks([e["win_rate"] for e in entries])
        tc_pcts = self._percentile_ranks([e["top_cut_rate"] for e in entries])

        for i, e in enumerate(entries):
            e["pct_usage"] = usage_pcts[i]
            e["pct_winrate"] = wr_pcts[i]
            e["pct_topcut"] = tc_pcts[i]

            e["power_score"] = round(
                self.WEIGHT_USAGE * usage_pcts[i]
                + self.WEIGHT_WINRATE * wr_pcts[i]
                + self.WEIGHT_TOP_CUT * tc_pcts[i],
                1,
            )

        entries.sort(key=lambda x: x["power_score"], reverse=True)

        # ---- Relative tier boundaries ----
        n = len(entries)
        for rank, e in enumerate(entries, 1):
            e["rank"] = rank
            pct_pos = (rank - 1) / n  # 0.0 = best,  1.0 = worst
            if pct_pos < 0.08:
                e["tier"] = "S"
            elif pct_pos < 0.25:
                e["tier"] = "A"
            elif pct_pos < 0.55:
                e["tier"] = "B"
            else:
                e["tier"] = "C"

        self._power_rankings = entries
        return entries

    # ------------------------------------------------------------------ #
    #  Tier List
    # ------------------------------------------------------------------ #

    def get_tier_list(self) -> Dict[str, List[Dict]]:
        """Return archetypes grouped by tier."""
        rankings = self.calculate_power_rankings()
        tiers: Dict[str, List[Dict]] = {"S": [], "A": [], "B": [], "C": []}
        for e in rankings:
            tier = e.get("tier", "C")
            tiers[tier].append({
                "name": e["name"],
                "power_score": e["power_score"],
                "deck_count": e["deck_count"],
                "win_rate": round(e["win_rate"] * 100, 1),
                "usage_rate": round(e["usage_rate"] * 100, 1),
                "top_cut_rate": round(e["top_cut_rate"] * 100, 1),
                "win_count": e["win_count"],
            })
        return tiers

    # ------------------------------------------------------------------ #
    #  Meta Health
    # ------------------------------------------------------------------ #

    def calculate_meta_health(self) -> Dict[str, Any]:
        """
        Calculate meta health using Simpson's Diversity Index.

        Returns:
            Dictionary with diversity_index, dominance_pct, top3_concentration,
            unique_archetypes, and a qualitative label.
        """
        arch_stats = self._archetype_analyzer.calculate_stats()
        if not arch_stats:
            return {
                "diversity_index": 0,
                "dominance_pct": 0,
                "top3_concentration": 0,
                "unique_archetypes": 0,
                "label": "無資料",
            }

        total = sum(s.deck_count for s in arch_stats.values())
        if total == 0:
            return {
                "diversity_index": 0,
                "dominance_pct": 0,
                "top3_concentration": 0,
                "unique_archetypes": 0,
                "label": "無資料",
            }

        # Simpson's Diversity Index: 1 - Σ(pi²)
        proportions = [s.deck_count / total for s in arch_stats.values()]
        simpson = 1.0 - sum(p * p for p in proportions)

        sorted_counts = sorted(
            [s.deck_count for s in arch_stats.values()], reverse=True
        )
        dominance = (sorted_counts[0] / total) * 100 if sorted_counts else 0
        top3 = (sum(sorted_counts[:3]) / total) * 100 if len(sorted_counts) >= 3 else dominance

        # Qualitative label
        if simpson >= 0.85:
            label = "非常健康"
        elif simpson >= 0.70:
            label = "健康"
        elif simpson >= 0.50:
            label = "略有集中"
        else:
            label = "高度集中"

        return {
            "diversity_index": round(simpson, 3),
            "dominance_pct": round(dominance, 1),
            "top3_concentration": round(top3, 1),
            "unique_archetypes": len(arch_stats),
            "label": label,
        }

    # ------------------------------------------------------------------ #
    #  Meta Share Trend
    # ------------------------------------------------------------------ #

    def get_meta_share_trend(self, top_n: int = 8) -> Dict[str, Any]:
        """
        Compute archetype meta share % per week for stacked area chart.

        Args:
            top_n: Number of top archetypes to track individually.

        Returns:
            {
                "weeks": ["2026-W05", ...],
                "archetypes": [
                    {"name": "X", "shares": [22.1, 19.5, ...]}
                ]
            }
        """
        # Group decks by week
        weekly_counts: Dict[str, Counter] = defaultdict(Counter)
        weekly_totals: Dict[str, int] = defaultdict(int)

        for tournament in self.tournaments:
            week = get_week_key(tournament.get("date", ""))
            for deck in tournament.get("decks", []):
                archetype = deck.get("archetype", "Unknown")
                weekly_counts[week][archetype] += 1
                weekly_totals[week] += 1

        if not weekly_counts:
            return {"weeks": [], "archetypes": []}

        weeks = sorted(weekly_counts.keys())

        # Determine top N archetypes overall
        global_counts: Counter = Counter()
        for wc in weekly_counts.values():
            global_counts.update(wc)
        top_archetypes = [name for name, _ in global_counts.most_common(top_n)]

        result_archetypes = []
        for archetype in top_archetypes:
            shares = []
            for w in weeks:
                total = weekly_totals[w]
                count = weekly_counts[w].get(archetype, 0)
                share = round((count / total) * 100, 1) if total > 0 else 0
                shares.append(share)
            result_archetypes.append({"name": archetype, "shares": shares})

        # "Others" row
        others_shares = []
        for w in weeks:
            total = weekly_totals[w]
            top_sum = sum(weekly_counts[w].get(a, 0) for a in top_archetypes)
            others = total - top_sum
            others_shares.append(round((others / total) * 100, 1) if total > 0 else 0)
        result_archetypes.append({"name": "Others", "shares": others_shares})

        return {"weeks": weeks, "archetypes": result_archetypes}

    # ------------------------------------------------------------------ #
    #  Energy Profile
    # ------------------------------------------------------------------ #

    def get_energy_profile(self, archetype: str) -> Dict[str, Any]:
        """
        Analyze energy type distribution for an archetype.

        Returns:
            {
                "types": {"Fire": 45.2, "Water": 30.1, ...},
                "avg_energy_count": 10.5,
                "deck_count": 20
            }
        """
        decks = self._get_decks_with_cards(archetype)
        if not decks:
            return {"types": {}, "avg_energy_count": 0, "deck_count": 0}

        type_totals: Counter = Counter()
        total_energy_cards = 0
        total_decks = len(decks)

        for deck_cards in decks:
            for card in deck_cards:
                if card.get("card_type") == "Energy":
                    name = card.get("name", "")
                    count = card.get("count", 1)
                    energy_type = self._classify_energy(name)
                    type_totals[energy_type] += count
                    total_energy_cards += count

        # Convert to percentages
        types_pct = {}
        if total_energy_cards > 0:
            for etype, cnt in type_totals.most_common():
                types_pct[etype] = round((cnt / total_energy_cards) * 100, 1)

        return {
            "types": types_pct,
            "avg_energy_count": round(total_energy_cards / total_decks, 1) if total_decks else 0,
            "deck_count": total_decks,
        }

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    def _get_decks_with_cards(self, archetype: str) -> List[List[dict]]:
        """Get list of card-lists for decks matching the archetype."""
        result = []
        for tournament in self.tournaments:
            for deck in tournament.get("decks", []):
                if deck.get("archetype") == archetype and deck.get("cards"):
                    result.append(deck["cards"])
        return result

    @staticmethod
    def _classify_energy(card_name: str) -> str:
        """Classify an energy card into a type."""
        # Exact match first
        if card_name in ENERGY_TYPE_MAP:
            return ENERGY_TYPE_MAP[card_name]
        # Partial match
        name_lower = card_name.lower()
        for key, etype in ENERGY_TYPE_MAP.items():
            if key.lower() in name_lower:
                return etype
        # Default
        return "Colorless"

    # ------------------------------------------------------------------ #
    #  Combined API response
    # ------------------------------------------------------------------ #

    def get_full_insight(self) -> Dict[str, Any]:
        """Return combined insight data for the /api/meta-insight endpoint."""
        return {
            "scoring_method": {
                "description": "百分位排名加權評分",
                "weights": {
                    "win_rate": self.WEIGHT_WINRATE,
                    "top_cut": self.WEIGHT_TOP_CUT,
                    "usage": self.WEIGHT_USAGE,
                },
                "tier_rules": "S=top 8%, A=top 25%, B=top 55%, C=其餘",
            },
            "tier_list": self.get_tier_list(),
            "power_rankings": [
                {
                    "rank": e["rank"],
                    "name": e["name"],
                    "power_score": e["power_score"],
                    "tier": e["tier"],
                    "deck_count": e["deck_count"],
                    "win_rate": round(e["win_rate"] * 100, 1),
                    "usage_rate": round(e["usage_rate"] * 100, 1),
                    "top_cut_rate": round(e["top_cut_rate"] * 100, 1),
                    "win_count": e["win_count"],
                    "pct_usage": e["pct_usage"],
                    "pct_winrate": e["pct_winrate"],
                    "pct_topcut": e["pct_topcut"],
                }
                for e in self.calculate_power_rankings()
            ],
            "meta_health": self.calculate_meta_health(),
        }
