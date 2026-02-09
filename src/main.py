"""
CLI entry point for PTCG City League Analyzer.
"""
import argparse
import sys
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
        default=20,
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
    
    args = parser.parse_args()
    
    if args.command == "scrape":
        run_scrape(args)
    elif args.command == "analyze":
        run_analyze(args)
    elif args.command == "web":
        run_web(args)
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

    print(f"Starting scrape with limit={args.limit}, delay={args.delay}s, fetch_cards={args.fetch_cards}")
    
    scraper = LimitlessScraper(cache_dir="data", delay=args.delay)
    data = scraper.scrape_all(tournament_limit=args.limit, fetch_cards=args.fetch_cards)
    
    print(f"\n✅ Scrape complete!")
    print(f"   Tournaments: {len(data.get('tournaments', []))}")
    if data.get('has_card_data'):
        total_cards = sum(len(d.get('cards', [])) for t in data['tournaments'] for d in t['decks'])
        print(f"   Card data: Yes ({total_cards} card entries)")
    print(f"   Saved to: data/scraped_data.json")


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


if __name__ == "__main__":
    main()
