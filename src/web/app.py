"""
Flask web application for PTCG City League analysis.
"""
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from ..scraper.limitless import LimitlessScraper
from ..analyzer.archetype import ArchetypeAnalyzer
from ..analyzer.winrate import WinRateAnalyzer
from ..analyzer.matchups import MatchupAnalyzer
from ..analyzer.trends import TrendsAnalyzer
from ..analyzer.cards import CardAnalyzer
from ..analyzer.meta_insight import MetaInsightAnalyzer
from ..translation import translate_archetype
from ..utils.card_db import CardDB
from ..utils.date_utils import get_week_key, get_previous_week


app = Flask(__name__, 
            template_folder="templates",
            static_folder="static")

# Data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"


from .data_manager import DataManager

# Data directory
DATA_DIR = Path(__file__).parent.parent.parent / "data"
data_manager = DataManager(DATA_DIR)

@app.route("/")
def index():
    """Main dashboard page."""
    return render_template("index.html")


@app.route("/api/overview")
def api_overview():
    """Get overview statistics."""
    week_param = request.args.get("week")
    data = data_manager.get_data()
    
    # Calculate global (latest) week if not provided
    if not week_param:
        weeks = data_manager.get_all_weeks()
        if weeks:
            week_param = weeks[-1]
    
    # Filter data for the rolling window (Current + Previous week)
    window_data = data_manager.get_window_data(week_param, window_size=2)
    
    tournaments = window_data.get("tournaments", [])
    total_tournaments = len(tournaments)
    total_decks = sum(len(t.get("decks", [])) for t in tournaments)
    
    # Breakdown by week
    current_week_count = 0
    prev_week_count = 0
    
    prev_week_key = get_previous_week(week_param) if week_param else None
    
    for t in tournaments:
        wk = get_week_key(t.get("date", ""))
        if wk == week_param:
            current_week_count += len(t.get("decks", []))
        elif wk == prev_week_key:
            prev_week_count += len(t.get("decks", []))
            
    # Count unique archetypes in this window
    archetypes = set()
    for t in tournaments:
        for d in t.get("decks", []):
            archetypes.add(d.get("archetype", "Unknown"))
    
    return jsonify({
        "total_tournaments": total_tournaments,
        "total_decks": total_decks,
        "total_archetypes": len(archetypes),
        "scraped_at": data.get("scraped_at"),
        "current_week": week_param,
        "current_week_decks": current_week_count,
        "prev_week": prev_week_key,
        "prev_week_decks": prev_week_count
    })


@app.route("/api/archetypes")
def api_archetypes():
    """Get archetype distribution data."""
    week_param = request.args.get("week")
    window_data = data_manager.get_window_data(week_param)
    analyzer = ArchetypeAnalyzer(window_data)
    
    distribution = analyzer.get_distribution_data()
    top_archetypes = [
        analyzer.get_archetype_detail(s.name)
        for s in analyzer.get_top_archetypes(15)
    ]
    
    return jsonify({
        "distribution": distribution,
        "top_archetypes": top_archetypes
    })


@app.route("/api/archetype/<path:name>/detail")
def api_archetype_detail(name: str):
    """Get detailed analysis for a specific archetype."""
    week_param = request.args.get("week")
    data = data_manager.get_data()
    
    # Prepare different data views
    window_data = data_manager.get_window_data(week_param)
    history_data = data_manager.get_history_data(week_param)
    
    # Get CardDB singleton
    card_db = data_manager.get_card_db()
    
    # Use window_data for point-in-time stats
    archetype_analyzer = ArchetypeAnalyzer(window_data)
    matchup_analyzer = MatchupAnalyzer(window_data)
    card_analyzer = CardAnalyzer(window_data, card_db=card_db)
    
    # Use history_data for trends
    trends_analyzer = TrendsAnalyzer(history_data)
    
    detail = archetype_analyzer.get_archetype_detail(name)
    matchups = matchup_analyzer.get_archetype_matchups(name)
    summary = trends_analyzer.get_archetype_summary(name)
    
    card_usage = card_analyzer.get_card_usage(name)
    recent_decks = archetype_analyzer.get_recent_decks(name, limit=50)
    
    # Translate opponent names in matchups
    if matchups:
        for key in ["favorable", "unfavorable", "all"]:
            if key in matchups and matchups[key]:
                for m in matchups[key]:
                    if "opponent" in m:
                        m["opponent_zh"] = translate_archetype(m["opponent"])
    
    # Add translated archetype name
    detail["name_zh"] = translate_archetype(name)
    
    # Check if card data is available
    has_card_data = data.get("has_card_data", False) or card_usage.get("deck_count", 0) > 0
    
    # Deep Analysis Data
    consensus_score = 0.0
    tech_trends = {}
    ace_spec_trends = {}
    energy_profile = None
    
    if has_card_data:
        # Consensus score should be based on the window (current meta)
        consensus_score = archetype_analyzer.calculate_consensus_score(name)
        # Trends should be based on history
        tech_trends = trends_analyzer.get_tech_trends(name)
        ace_spec_trends = trends_analyzer.get_ace_spec_trends(name)
        # Energy profile
        meta_insight = MetaInsightAnalyzer(window_data)
        energy_profile = meta_insight.get_energy_profile(name)
    
    return jsonify({
        "stats": detail,
        "matchups": matchups,
        "building_trends": summary,
        "card_analysis": card_usage if has_card_data else None,
        "has_card_data": has_card_data,
        "recent_decks": recent_decks,
        "energy_profile": energy_profile,
        "deep_analysis": {
            "consensus_score": round(consensus_score, 2),
            "tech_trends": tech_trends,
            "ace_spec_trends": ace_spec_trends
        }
    })


@app.route("/api/winrates")
def api_winrates():
    """Get win rate statistics."""
    week_param = request.args.get("week")
    window_data = data_manager.get_window_data(week_param)
    analyzer = WinRateAnalyzer(window_data)
    
    return jsonify({
        "chart_data": analyzer.get_chart_data(),
        "rankings": analyzer.get_performance_ranking(min_entries=3)[:20]
    })


@app.route("/api/matchups")
def api_matchups():
    """Get matchup matrix data."""
    week_param = request.args.get("week")
    window_data = data_manager.get_window_data(week_param)
    analyzer = MatchupAnalyzer(window_data)
    
    top_n = request.args.get("top", 10, type=int)
    
    return jsonify({
        "heatmap": analyzer.get_heatmap_data(top_n),
        "matrix": analyzer.get_matchup_matrix(top_n)
    })


@app.route("/api/matchups-zh")
def api_matchups_chinese():
    """Get matchup matrix data with Chinese translations."""
    week_param = request.args.get("week")
    window_data = data_manager.get_window_data(week_param)
    analyzer = MatchupAnalyzer(window_data)
    
    top_n = request.args.get("top", 10, type=int)
    
    heatmap = analyzer.get_heatmap_data(top_n)
    
    # Translate labels
    translated_heatmap = {
        "labels": [translate_archetype(label) for label in heatmap.get("labels", [])],
        "labels_en": heatmap.get("labels", []),
        "values": heatmap.get("values", [])
    }
    
    return jsonify({
        "heatmap": translated_heatmap,
        "matrix": analyzer.get_matchup_matrix(top_n)
    })


@app.route("/api/trends")
def api_trends():
    """Get metagame trend data."""
    week_param = request.args.get("week")
    history_data = data_manager.get_history_data(week_param)
    analyzer = TrendsAnalyzer(history_data)
    
    return jsonify({
        "chart_data": analyzer.get_chart_data(),
        "meta_trends": analyzer.get_meta_trends()
    })


@app.route("/api/scrape")
def api_scrape():
    """Trigger a new scrape (limited)."""
    limit = request.args.get("limit", 10, type=int)
    
    scraper = LimitlessScraper(cache_dir=str(DATA_DIR))
    data = scraper.scrape_all(tournament_limit=limit)
    
    # Refresh cache
    data_manager.get_data(force_refresh=True)
    
    return jsonify({
        "status": "success",
        "tournaments_scraped": len(data.get("tournaments", [])),
        "scraped_at": data.get("scraped_at")
    })


@app.route("/api/meta-insight")
def api_meta_insight():
    """Get tier list, power rankings, and meta health data."""
    week_param = request.args.get("week")
    window_data = data_manager.get_window_data(week_param)
    analyzer = MetaInsightAnalyzer(window_data)

    insight = analyzer.get_full_insight()

    # Translate archetype names
    for tier_key in ["S", "A", "B", "C"]:
        for item in insight["tier_list"].get(tier_key, []):
            item["name_zh"] = translate_archetype(item["name"])
    for item in insight["power_rankings"]:
        item["name_zh"] = translate_archetype(item["name"])

    return jsonify(insight)


@app.route("/api/meta-share-trend")
def api_meta_share_trend():
    """Get meta share trend data for stacked area chart."""
    week_param = request.args.get("week")
    history_data = data_manager.get_history_data(week_param)
    analyzer = MetaInsightAnalyzer(history_data)

    trend = analyzer.get_meta_share_trend(top_n=8)

    # Translate archetype names
    for arch in trend["archetypes"]:
        arch["name_zh"] = translate_archetype(arch["name"])

    return jsonify(trend)


@app.route("/api/archetypes-zh")
def api_archetypes_chinese():
    """Get archetype distribution with Chinese translations."""
    week_param = request.args.get("week")
    window_data = data_manager.get_window_data(week_param)
    analyzer = ArchetypeAnalyzer(window_data)
    
    # Get top archetypes and translate them
    top_archetypes = []
    for stat in analyzer.get_top_archetypes(20):
        detail = analyzer.get_archetype_detail(stat.name)
        detail["name_en"] = stat.name
        detail["name_zh"] = translate_archetype(stat.name)
        top_archetypes.append(detail)
    
    # Get distribution with translated labels
    distribution = analyzer.get_distribution_data()
    translated_distribution = {
        "labels": [translate_archetype(label) for label in distribution["labels"]],
        "labels_en": distribution["labels"],
        "values": distribution["values"]
    }
    
    return jsonify({
        "distribution": translated_distribution,
        "top_archetypes": top_archetypes
    })


def get_week_label(week_key: str) -> str:
    """Get human readable week label."""
    try:
        year, week = week_key.split("-W")
        return f"{year}年 第{int(week)}週"
    except (ValueError, AttributeError):
        return week_key


@app.route("/api/tournaments/weekly")
def api_tournaments_weekly():
    """Get tournaments grouped by week with Chinese-translated archetypes."""
    data = data_manager.get_data()
    tournaments = data.get("tournaments", [])
    
    # Group tournaments by week
    weekly_data = defaultdict(lambda: {
        "tournaments": [],
        "deck_count": 0,
        "archetype_counts": defaultdict(int)
    })
    
    for t in tournaments:
        week_key = get_week_key(t.get("date", ""))
        weekly_data[week_key]["tournaments"].append({
            "id": t.get("id"),
            "name": t.get("name"),
            "date": t.get("date"),
            "location": t.get("location"),
            "shop": t.get("shop"),
            "deck_count": len(t.get("decks", []))
        })
        weekly_data[week_key]["deck_count"] += len(t.get("decks", []))
        
        # Count archetypes
        for deck in t.get("decks", []):
            archetype = deck.get("archetype", "Unknown")
            weekly_data[week_key]["archetype_counts"][archetype] += 1
    
    # Convert to list and sort by week
    result = []
    for week_key in sorted(weekly_data.keys(), reverse=True):
        week_info = weekly_data[week_key]
        
        # Get top archetypes for this week (translated)
        top_archetypes = sorted(
            week_info["archetype_counts"].items(),
            key=lambda x: -x[1]
        )[:10]
        
        result.append({
            "week": week_key,
            "week_label": get_week_label(week_key),
            "tournament_count": len(week_info["tournaments"]),
            "deck_count": week_info["deck_count"],
            "tournaments": week_info["tournaments"],
            "top_archetypes": [
                {
                    "name_en": arch,
                    "name_zh": translate_archetype(arch),
                    "count": count
                }
                for arch, count in top_archetypes
            ]
        })
    
    return jsonify({
        "weeks": result,
        "total_weeks": len(result)
    })


def run(host: str = "127.0.0.1", port: int = 5000, debug: bool = True):
    """Run the Flask application."""
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run()
