"""
CLI entry point for PTCG City League Analyzer.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="PTCG City League Deck Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main scrape --limit 10    # Scrape 10 tournaments
  python -m src.main analyze              # Show analysis summary
  python -m src.main web                  # Start web interface
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape data from Limitless TCG")
    scrape_parser.add_argument(
        "--limit", "-l", 
        type=int, 
        default=None,
        help="Maximum number of tournaments to scrape (default: 20)"
    )
    scrape_parser.add_argument(
        "--delay", "-d",
        type=float,
        default=1.0,
        help="Delay between requests in seconds (default: 1.0)"
    )
    scrape_parser.add_argument(
        "--fetch-cards", "-c",
        action="store_true",
        help="Fetch detailed card lists for each deck (slower, enables card analysis)"
    )
    scrape_parser.add_argument(
        "--days",
        type=int,
        help="Scrape tournaments from the last N days"
    )
    scrape_parser.add_argument(
        "--weeks", "-w",
        type=int,
        help="Scrape tournaments from the last N weeks (convenience for --days)"
    )
    scrape_parser.add_argument(
        "--update-card-map",
        action="store_true",
        help="Update Limitless to JP card mapping"
    )
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Show analysis summary")
    analyze_parser.add_argument(
        "--archetype", "-a",
        type=str,
        help="Show detail for specific archetype"
    )
    
    # Web command
    web_parser = subparsers.add_parser("web", help="Start web interface")
    web_parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    web_parser.add_argument(
        "--port", "-p",
        type=int,
        default=5000,
        help="Port to bind to (default: 5000)"
    )
    web_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    # Cards command (External Tool Integration)
    cards_parser = subparsers.add_parser("cards", help="Manage local card database (ptcg_tw)")
    cards_parser.add_argument("card_args", nargs=argparse.REMAINDER, help="Arguments for ptcg_tw tool")

    # Workflow command
    workflow_parser = subparsers.add_parser("workflow", help="Run full data update workflow")
    workflow_parser.add_argument("--skip-cards", action="store_true", help="Skip card DB sync")
    workflow_parser.add_argument("--days", type=int, default=14, help="Scrape last N days (default: 14)")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Launch statistical analysis dashboard (Streamlit)")
    stats_parser.add_argument("--port", "-p", type=int, default=8501, help="Port for Streamlit (default: 8501)")
    
    args = parser.parse_args()
    
    if args.command == "scrape":
        run_scrape(args)
    elif args.command == "analyze":
        run_analyze(args)
    elif args.command == "web":
        run_web(args)
    elif args.command == "cards":
        run_cards(args)
    elif args.command == "workflow":
        run_workflow(args)
    elif args.command == "stats":
        run_stats(args)
    else:
        parser.print_help()


def run_scrape(args):
    """Run the scraper."""
    from .scraper.limitless import LimitlessScraper
    
    if args.update_card_map:
        from .scraper.mapper import CardMapper
        print("Starting card mapping update...")
        mapper = CardMapper()
        mapper.run()
        if not args.limit and not args.fetch_cards:
            return

    today = datetime.now().date()
    
    # Calculate days if weeks provided
    days = args.days
    if args.weeks:
        days = args.weeks * 7
        print(f"Scraping last {args.weeks} weeks ({days} days)...")
    
    # Set default limit if nothing else specified
    limit = args.limit
    if limit is None and days is None:
        limit = 20
        print("No limit or time range specified. Defaulting to latest 20 tournaments.")
    elif days is not None and limit is None:
        print(f"Scraping all tournaments from the last {days} days (no limit).")

    print(f"Starting scrape with limit={limit}, days={days}, delay={args.delay}s, fetch_cards={args.fetch_cards}")
    
    scraper = LimitlessScraper(cache_dir="data", delay=args.delay)
    data = scraper.scrape_all(tournament_limit=limit, days=days, fetch_cards=args.fetch_cards)
    
    print(f"\n✅ Scrape complete!")
    print(f"   Tournaments: {len(data.get('tournaments', []))}")

def run_analyze(args):
    """Run analysis and print summary."""
    from .scraper.limitless import LimitlessScraper
    from .analyzer.archetype import ArchetypeAnalyzer
    from .analyzer.winrate import WinRateAnalyzer
    from .analyzer.matchups import MatchupAnalyzer
    
    scraper = LimitlessScraper(cache_dir="data")
    data = scraper.load_cached_data()
    
    if not data:
        print("❌ No data found. Run 'scrape' command first.")
        return
    
    if args.archetype:
        # Show specific archetype detail
        archetype_analyzer = ArchetypeAnalyzer(data)
        matchup_analyzer = MatchupAnalyzer(data)
        
        detail = archetype_analyzer.get_archetype_detail(args.archetype)
        matchups = matchup_analyzer.get_archetype_matchups(args.archetype)
        
        print(f"\n📊 {args.archetype} Analysis")
        print("=" * 50)
        print(f"   Total Entries: {detail.get('deck_count', 0)}")
        print(f"   Wins: {detail.get('win_count', 0)}")
        print(f"   Win Rate: {detail.get('win_rate', 0)}%")
        print(f"   Top 8 Rate: {detail.get('top8_rate', 0)}%")
        
        if matchups.get('favorable'):
            print(f"\n✅ Favorable Matchups:")
            for m in matchups['favorable'][:5]:
                print(f"   vs {m['opponent']}: {m['winrate']}%")
        
        if matchups.get('unfavorable'):
            print(f"\n❌ Unfavorable Matchups:")
            for m in matchups['unfavorable'][:5]:
                print(f"   vs {m['opponent']}: {m['winrate']}%")
        
        # Card Analysis
        if data.get("has_card_data"):
            from .analyzer.cards import CardAnalyzer
            card_analyzer = CardAnalyzer(data)
            card_usage = card_analyzer.get_card_usage(args.archetype)
            
            if card_usage.get("ace_specs"):
                print(f"\n⭐ ACE SPEC Preference:")
                for c in card_usage["ace_specs"]:
                    print(f"   {c['name']}: {c['usage_rate']}%")
            
            if card_usage.get("core_cards"):
                print(f"\n💎 Core Cards (>80%):")
                for c in card_usage["core_cards"][:10]:
                    print(f"   {c['name']} ({c['avg_copies']}x): {c['usage_rate']}%")
            
            if card_usage.get("tech_cards"):
                print(f"\n🔧 Tech Cards (20-80%):")
                for c in card_usage["tech_cards"][:10]:
                    print(f"   {c['name']} ({c['avg_copies']}x): {c['usage_rate']}%")
        else:
            print("\n⚠️ No card data available. Run 'scrape --fetch-cards' to see card analysis.")
    else:
        # Show overall summary
        archetype_analyzer = ArchetypeAnalyzer(data)
        winrate_analyzer = WinRateAnalyzer(data)
        
        top_archetypes = archetype_analyzer.get_top_archetypes(10)
        
        print(f"\n📊 PTCG City League Analysis Summary")
        print("=" * 50)
        print(f"Total Tournaments: {len(data.get('tournaments', []))}")
        print(f"Scraped at: {data.get('scraped_at', 'Unknown')}")
        
        print(f"\n🏆 Top 10 Archetypes by Usage:")
        for i, arch in enumerate(top_archetypes, 1):
            print(f"   {i:2}. {arch.name}")
            print(f"       Usage: {arch.usage_rate*100:.1f}% | Wins: {arch.win_count} | Top8: {arch.top8_count}")


def run_web(args):
    """Run the web interface."""
    from .web.app import run
    
    print(f"🌐 Starting web interface at http://{args.host}:{args.port}")
    run(host=args.host, port=args.port, debug=args.debug)


def run_cards(args):
    """Run the card database tool."""
    from .card_db.__main__ import main as card_main
    
    # args.card_args is a list of strings, e.g. ['sync', '--db', ...]
    sys.exit(card_main(args.card_args))

def run_workflow(args):
    """Run the full data update workflow."""
    print("🚀 Starting Full Data Update Workflow")
    print(f"📅 Target: Last {args.days} days")
    print("=" * 50)
    
    # 1. Sync Card DB (if not skipped)
    if not args.skip_cards:
        print("\n[1/3] Syncing Card Database (Official TW)...")
        from .card_db.__main__ import main as card_main
        # Default to syncing all regulation marked cards, parallel workers
        # Using lists=8, workers=4 (default)
        cmd = ["sync", "--db", "data/ptcg_hij.sqlite", "--regulation-mark", "H,I,J"]
        try:
            card_main(cmd)
        except SystemExit as e:
            if e.code != 0:
                print("❌ Card sync failed")
                return
        except Exception as e:
            print(f"❌ Card sync failed: {e}")
            return
    else:
        print("\n[1/3] Skipping Card Database Sync")

    # 2. Scrape Decks
    print("\n[2/3] Scraping City League Decks (Limitless)...")
    from .scraper.limitless import LimitlessScraper
    # Scrape with days specified, limit=None to get all within range
    scraper = LimitlessScraper(cache_dir="data")
    scraper.scrape_all(days=args.days, fetch_cards=True)
    
    # 3. Update Mapping
    print("\n[3/3] Updating Card Mapping...")
    from .scraper.mapper import CardMapper
    mapper = CardMapper()
    mapper.run()
    
    print("\n✅ Workflow Complete!")
    print("Run 'python -m src.main web' to view results.")


def run_stats(args):
    """Launch statistical analysis Streamlit app."""
    import subprocess
    app_path = Path(__file__).parent.parent / "stats_app.py"
    if not app_path.exists():
        print(f"❌ stats_app.py not found at {app_path}")
        return
    print(f"📐 Launching Statistical Analysis Dashboard on port {args.port}...")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", str(app_path),
        "--server.port", str(args.port),
        "--server.headless", "false",
    ])


if __name__ == "__main__":
    main()
