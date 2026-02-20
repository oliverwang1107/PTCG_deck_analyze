"""
Advanced statistical analysis for PTCG meta data.

Provides scientific-grade statistical methods:
- Bayesian Win Rate (Beta-Binomial posterior)
- Binomial Exact Test for matchup significance
- Meta Stability (Coefficient of Variation)
- Chi-Square Meta Shift Detection
- Concentration Indices (HHI, Shannon Entropy, Simpson's)
- Expected Value (EV) Analysis
- Wilson Score Confidence Intervals

All implementations use pure Python (math / collections only, no scipy).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from .archetype import ArchetypeAnalyzer
from .matchups import MatchupAnalyzer
from ..utils.date_utils import get_week_key

__all__ = ["StatisticalAnalyzer"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _log_comb(n: int, k: int) -> float:
    """Log of binomial coefficient C(n, k) using lgamma — O(1)."""
    if k < 0 or k > n:
        return -math.inf
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def _binom_pmf_log(n: int, k: int) -> float:
    """Log of Binomial(n, 0.5) PMF at k: C(n,k) * 0.5^n."""
    return _log_comb(n, k) - n * math.log(2)


def _chi2_sf(chi2: float, df: int) -> float:
    """
    Survival function 1 − CDF for chi-square distribution.

    Uses the regularised incomplete gamma function via series / continued
    fraction expansion.  Accurate to ~10 significant digits for all
    practical chi-square / df values encountered in meta analysis.
    """
    if chi2 <= 0 or df <= 0:
        return 1.0

    a = df / 2.0
    x = chi2 / 2.0

    if x < a + 1:
        # Series expansion for the regularised *lower* incomplete gamma
        ap, s, delta = a, 1.0 / a, 1.0 / a
        for _ in range(300):
            ap += 1
            delta *= x / ap
            s += delta
            if abs(delta) < abs(s) * 1e-12:
                break
        gamma_p = s * math.exp(-x + a * math.log(x) - math.lgamma(a))
        return max(0.0, min(1.0, 1.0 - gamma_p))

    # Continued-fraction (Lentz's method) for the *upper* incomplete gamma
    b = x + 1.0 - a
    c = 1e30
    d = 1.0 / b if b != 0 else 1e30
    f = d
    for i in range(1, 300):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-30:
            d = 1e-30
        c = b + an / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        f *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    gamma_q = f * math.exp(-x + a * math.log(x) - math.lgamma(a))
    return max(0.0, min(1.0, gamma_q))


def _wilson_interval(
    successes: int, n: int, z: float = 1.96,
) -> tuple[float, float, float]:
    """
    Wilson score interval for a proportion.

    Returns (point_estimate, ci_low, ci_high) — all as fractions in [0, 1].
    """
    p_hat = min(successes / n, 1.0)
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denom
    inner = max(0.0, (p_hat * (1.0 - p_hat) + z2 / (4 * n)) / n)
    margin = z * math.sqrt(inner) / denom
    return p_hat, max(0.0, center - margin), min(1.0, center + margin)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main class
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class StatisticalAnalyzer:
    """Scientific statistical analysis for PTCG tournament data."""

    # Bayesian prior: Beta(2, 2) — weakly informative, centred on 50 %
    PRIOR_ALPHA = 2.0
    PRIOR_BETA = 2.0

    def __init__(self, data: dict) -> None:
        self.data = data
        self.tournaments: list[dict] = data.get("tournaments", [])
        self._arch = ArchetypeAnalyzer(data)
        self._matchup = MatchupAnalyzer(data)

    # ── helpers ──────────────────────────────────────────────────────────

    def _weekly_breakdown(self) -> tuple[dict[str, Counter], dict[str, int]]:
        """Build per-week archetype counts and totals (cached-like)."""
        counts: dict[str, Counter] = defaultdict(Counter)
        totals: dict[str, int] = defaultdict(int)
        for t in self.tournaments:
            week = get_week_key(t.get("date", ""))
            for d in t.get("decks", []):
                arch = d.get("archetype", "Unknown")
                counts[week][arch] += 1
                totals[week] += 1
        return counts, totals

    # ────────────────────────────────────────────────────────────────────
    #  1. Bayesian Win Rate
    # ────────────────────────────────────────────────────────────────────

    def bayesian_win_rates(self, min_entries: int = 3) -> list[dict[str, Any]]:
        """
        Beta-Binomial posterior win-rate estimates.

        Posterior: Beta(α + wins, β + n − wins), with prior Beta(2, 2).
        Returns list sorted by posterior mean (descending).
        """
        results: list[dict[str, Any]] = []

        for name, stats in self._arch.calculate_stats().items():
            if stats.deck_count < min_entries:
                continue

            n = stats.deck_count
            wins = stats.win_count
            a_post = self.PRIOR_ALPHA + wins
            b_post = self.PRIOR_BETA + (n - wins)

            mean = a_post / (a_post + b_post)
            var = (a_post * b_post) / (
                (a_post + b_post) ** 2 * (a_post + b_post + 1)
            )
            std = math.sqrt(var)
            ci_lo = max(0.0, mean - 1.96 * std)
            ci_hi = min(1.0, mean + 1.96 * std)

            results.append({
                "name": name,
                "observed_win_rate": round(wins / n * 100, 2) if n else 0,
                "posterior_mean": round(mean * 100, 2),
                "ci_low": round(ci_lo * 100, 2),
                "ci_high": round(ci_hi * 100, 2),
                "ci_width": round((ci_hi - ci_lo) * 100, 2),
                "wins": wins,
                "sample_size": n,
                "prior": f"Beta({self.PRIOR_ALPHA}, {self.PRIOR_BETA})",
            })

        results.sort(key=lambda r: r["posterior_mean"], reverse=True)
        return results

    # ────────────────────────────────────────────────────────────────────
    #  2. Matchup Significance (Binomial Exact Test)
    # ────────────────────────────────────────────────────────────────────

    def matchup_significance(self, top_n: int = 10) -> dict[str, Any]:
        """
        Two-sided binomial exact test for each matchup pair.

        H₀: P(A wins) = 0.5.  Reports p-value and significance markers
        (★ p < 0.01, ☆ p < 0.05).
        """
        matchups = self._matchup.calculate_matchups()
        arch_stats = self._arch.calculate_stats()

        top_set = set(
            sorted(arch_stats, key=lambda a: arch_stats[a].deck_count, reverse=True)[:top_n]
        )

        pairs: list[dict[str, Any]] = []
        for (a1, a2), md in matchups.items():
            if a1 not in top_set or a2 not in top_set:
                continue
            if md.total_matches < 3:
                continue

            w1, w2, n = md.archetype1_wins, md.archetype2_wins, md.total_matches
            observed = max(w1, w2)

            # Two-sided exact binomial p-value: 2 · P(X >= observed | p=0.5)
            p_tail = sum(math.exp(_binom_pmf_log(n, k)) for k in range(observed, n + 1))
            p_value = min(1.0, 2.0 * p_tail)

            pairs.append({
                "archetype1": a1,
                "archetype2": a2,
                "a1_wins": w1,
                "a2_wins": w2,
                "total": n,
                "win_rate": round(md.archetype1_winrate * 100, 1),
                "p_value": round(p_value, 4),
                "significant": p_value < 0.05,
                "label": "★" if p_value < 0.01 else ("☆" if p_value < 0.05 else "—"),
            })

        pairs.sort(key=lambda p: p["p_value"])
        return {
            "pairs": pairs,
            "test": "Two-sided Binomial Exact Test (H₀: p = 0.5)",
            "threshold": 0.05,
        }

    # ────────────────────────────────────────────────────────────────────
    #  3. Meta Stability (Coefficient of Variation)
    # ────────────────────────────────────────────────────────────────────

    def meta_stability(self, min_entries: int = 5) -> list[dict[str, Any]]:
        """
        CV of each archetype's weekly usage share.

        Lower CV → more stable meta presence.
        """
        weekly_counts, weekly_totals = self._weekly_breakdown()
        if len(weekly_counts) < 2:
            return []

        weeks = sorted(weekly_counts)
        results: list[dict[str, Any]] = []

        for name, stats in self._arch.calculate_stats().items():
            if stats.deck_count < min_entries:
                continue

            shares = [
                (weekly_counts[w].get(name, 0) / weekly_totals[w] * 100)
                if weekly_totals[w] > 0 else 0.0
                for w in weeks
            ]
            mean = sum(shares) / len(shares)
            if len(shares) > 1 and mean > 0:
                var = sum((s - mean) ** 2 for s in shares) / (len(shares) - 1)
                std = math.sqrt(var)
                cv = std / mean * 100
            else:
                std, cv = 0.0, 0.0

            results.append({
                "name": name,
                "mean_share": round(mean, 2),
                "std_share": round(std, 2),
                "cv": round(cv, 1),
                "weekly_shares": [round(s, 2) for s in shares],
                "weeks": weeks,
                "stability_label": (
                    "非常穩定" if cv < 20 else
                    "穩定" if cv < 50 else
                    "波動" if cv < 100 else
                    "極度波動"
                ),
                "deck_count": stats.deck_count,
            })

        results.sort(key=lambda r: r["cv"])
        return results

    # ────────────────────────────────────────────────────────────────────
    #  4. Chi-Square Meta Shift Detection
    # ────────────────────────────────────────────────────────────────────

    def meta_shift_test(self) -> dict[str, Any]:
        """
        χ² goodness-of-fit: does this week's archetype distribution differ
        significantly from last week's?

        H₀: distributions are the same.
        """
        weekly_counts, _ = self._weekly_breakdown()
        weeks = sorted(weekly_counts)

        if len(weeks) < 2:
            return {
                "result": "insufficient_data",
                "message": "需要至少兩週的資料才能進行分析",
            }

        cur, prev = weekly_counts[weeks[-1]], weekly_counts[weeks[-2]]
        total_cur, total_prev = sum(cur.values()), sum(prev.values())

        if total_prev == 0 or total_cur == 0:
            return {"result": "insufficient_data", "message": "資料不足"}

        all_archetypes = sorted(set(cur) | set(prev))

        chi2 = 0.0
        details: list[dict[str, Any]] = []
        for arch in all_archetypes:
            obs = cur.get(arch, 0)
            exp = (prev.get(arch, 0) / total_prev) * total_cur

            contrib = (obs - exp) ** 2 / exp if exp > 0 else 0.0
            chi2 += contrib

            details.append({
                "archetype": arch,
                "observed": obs,
                "expected": round(exp, 1),
                "contribution": round(contrib, 2),
                "direction": "↑" if obs > exp + 0.5 else ("↓" if obs < exp - 0.5 else "→"),
            })

        df = max(1, len(all_archetypes) - 1)
        p_value = _chi2_sf(chi2, df)

        details.sort(key=lambda d: d["contribution"], reverse=True)

        return {
            "result": "complete",
            "current_week": weeks[-1],
            "previous_week": weeks[-2],
            "chi_square": round(chi2, 2),
            "degrees_of_freedom": df,
            "p_value": round(p_value, 4),
            "significant": p_value < 0.05,
            "interpretation": (
                "環境顯著變化 ✅" if p_value < 0.01 else
                "環境有變化趨勢" if p_value < 0.05 else
                "環境穩定，無顯著變化"
            ),
            "top_shifts": details[:15],
            "total_current": total_cur,
            "total_previous": total_prev,
        }

    # ────────────────────────────────────────────────────────────────────
    #  5. Concentration Indices
    # ────────────────────────────────────────────────────────────────────

    def concentration_indices(self) -> dict[str, Any]:
        """
        Diversity / concentration metrics:
          · Simpson's Diversity (1 − Σpᵢ²)
          · Shannon Entropy  H = −Σ pᵢ · ln(pᵢ)
          · Evenness          H / ln(S)
          · HHI               Σpᵢ²
        """
        arch_stats = self._arch.calculate_stats()
        if not arch_stats:
            return {"error": "no data"}

        total = sum(s.deck_count for s in arch_stats.values())
        if total == 0:
            return {"error": "no data"}

        props = [s.deck_count / total for s in arch_stats.values()]
        S = len(props)

        hhi = sum(p * p for p in props)
        simpsons = 1.0 - hhi
        hhi_norm = (hhi - 1.0 / S) / (1.0 - 1.0 / S) if S > 1 else 0.0

        shannon = -sum(p * math.log(p) for p in props if p > 0)
        max_shannon = math.log(S) if S > 1 else 1.0
        evenness = shannon / max_shannon if max_shannon > 0 else 0.0
        effective_n = math.exp(shannon)

        counts_sorted = sorted(
            (s.deck_count for s in arch_stats.values()), reverse=True,
        )
        dom = counts_sorted[0] / total * 100
        top3 = sum(counts_sorted[:3]) / total * 100 if len(counts_sorted) >= 3 else dom
        top5 = sum(counts_sorted[:5]) / total * 100 if len(counts_sorted) >= 5 else top3

        return {
            "simpsons_index": round(simpsons, 4),
            "shannon_entropy": round(shannon, 4),
            "max_shannon": round(max_shannon, 4),
            "evenness": round(evenness, 4),
            "hhi": round(hhi, 4),
            "hhi_normalized": round(hhi_norm, 4),
            "effective_species": round(effective_n, 1),
            "species_richness": S,
            "dominance_pct": round(dom, 1),
            "top3_pct": round(top3, 1),
            "top5_pct": round(top5, 1),
            "total_decks": total,
            "interpretation": {
                "simpsons": (
                    "非常多元" if simpsons >= 0.9 else
                    "健康多元" if simpsons >= 0.8 else
                    "中等集中" if simpsons >= 0.6 else
                    "高度集中"
                ),
                "hhi": (
                    "競爭性環境" if hhi < 0.15 else
                    "中等集中" if hhi < 0.25 else
                    "高度集中"
                ),
                "evenness": (
                    "非常均勻" if evenness >= 0.8 else
                    "中等均勻" if evenness >= 0.6 else
                    "不均勻"
                ),
            },
        }

    # ────────────────────────────────────────────────────────────────────
    #  6. Expected Value (EV) Analysis
    # ────────────────────────────────────────────────────────────────────

    # Point values for placements
    _PTS_WIN, _PTS_T4, _PTS_T8 = 100, 50, 25

    def ev_analysis(self, min_entries: int = 5) -> list[dict[str, Any]]:
        """
        Expected tournament points per entry.

        Points: 1st = 100, Top4 = 50, Top8 = 25, Other = 0.
        Also reports StdDev and Sharpe-like ratio (EV / σ).
        """
        results: list[dict[str, Any]] = []

        for name, stats in self._arch.calculate_stats().items():
            if stats.deck_count < min_entries:
                continue

            n = stats.deck_count
            w, t4, t8 = stats.win_count, stats.top4_count, stats.top8_count

            ev = (self._PTS_WIN * w + self._PTS_T4 * t4 + self._PTS_T8 * t8) / n
            ev_sq = (self._PTS_WIN**2 * w + self._PTS_T4**2 * t4 + self._PTS_T8**2 * t8) / n
            std = math.sqrt(max(0.0, ev_sq - ev * ev))
            sharpe = ev / std if std > 0 else 0.0

            results.append({
                "name": name,
                "ev": round(ev, 2),
                "std": round(std, 2),
                "sharpe": round(sharpe, 3),
                "deck_count": n,
                "wins": w,
                "top4": t4,
                "top8": t8,
                "ev_label": (
                    "極高回報" if ev >= 20 else
                    "高回報" if ev >= 10 else
                    "中等回報" if ev >= 5 else
                    "低回報"
                ),
            })

        results.sort(key=lambda r: r["ev"], reverse=True)
        return results

    # ────────────────────────────────────────────────────────────────────
    #  7. Wilson Score Confidence Interval
    # ────────────────────────────────────────────────────────────────────

    def wilson_ci(self, min_entries: int = 3, z: float = 1.96) -> list[dict[str, Any]]:
        """
        Wilson score intervals for win / top-4 / top-8 rates.

        More accurate than the Wald interval, especially for small n.
        """
        results: list[dict[str, Any]] = []

        for name, stats in self._arch.calculate_stats().items():
            if stats.deck_count < min_entries:
                continue

            n = stats.deck_count
            metrics = {
                "win_rate": stats.win_count,
                "top4_rate": stats.win_count + stats.top4_count,
                "top8_rate": stats.win_count + stats.top4_count + stats.top8_count,
            }

            entry: dict[str, Any] = {"name": name, "deck_count": n}
            for metric, successes in metrics.items():
                p, lo, hi = _wilson_interval(successes, n, z)
                entry[metric] = round(p * 100, 2)
                entry[f"{metric}_ci_low"] = round(lo * 100, 2)
                entry[f"{metric}_ci_high"] = round(hi * 100, 2)

            results.append(entry)

        results.sort(key=lambda r: r["top8_rate"], reverse=True)
        return results

    # ────────────────────────────────────────────────────────────────────
    #  Combined API
    # ────────────────────────────────────────────────────────────────────

    def get_full_analysis(self, min_entries: int = 5) -> dict[str, Any]:
        """Return every analysis in a single payload."""
        return {
            "bayesian_win_rates": self.bayesian_win_rates(min_entries),
            "matchup_significance": self.matchup_significance(),
            "meta_stability": self.meta_stability(min_entries),
            "meta_shift": self.meta_shift_test(),
            "concentration": self.concentration_indices(),
            "ev_analysis": self.ev_analysis(min_entries),
            "wilson_ci": self.wilson_ci(min_entries),
        }
