
import sys
import json
from pathlib import Path

# Add src to path
sys.path.append(str(Path.cwd()))

from src.analyzer.trends import TrendsAnalyzer
from src.analyzer.archetype import ArchetypeAnalyzer
from src.scraper.limitless import LimitlessScraper

def verify_deep_analysis():
    print("Loading data...")
    scraper = LimitlessScraper(cache_dir="data")
    data = scraper.load_cached_data()
    
    if not data:
        print("Error: No data found. Please scrape data first.")
        return

    print(f"Loaded {len(data.get('tournaments', []))} tournaments.")
    
    # Initialize Analyzers
    trends_analyzer = TrendsAnalyzer(data)
    archetype_analyzer = ArchetypeAnalyzer(data)
    
    # Get top archetype to test
    top_archetypes = archetype_analyzer.get_top_archetypes(1)
    if not top_archetypes:
        print("Error: No archetypes found.")
        return
        
    test_archetype = top_archetypes[0].name
    print(f"\nTesting Deep Analysis for: {test_archetype}")
    
    # 1. Test Consensus Score
    print("\n[1] Testing Consensus Score...")
    score = archetype_analyzer.calculate_consensus_score(test_archetype)
    print(f"Consensus Score: {score}")
    if 0 <= score <= 1:
        print("✅ Consensus Score is valid (0.0 - 1.0)")
    else:
        print(f"❌ Invalid Consensus Score: {score}")
        
    # 2. Test Tech Trends
    print("\n[2] Testing Tech Trends...")
    tech_trends = trends_analyzer.get_tech_trends(test_archetype)
    if "weeks" in tech_trends and "datasets" in tech_trends:
        print(f"✅ Tech Trends structure valid. Found {len(tech_trends['datasets'])} cards.")
        for ds in tech_trends["datasets"]:
            print(f"   - {ds['label']}")
    else:
        print("❌ Invalid Tech Trends structure")
        
    # 3. Test ACE SPEC Trends
    print("\n[3] Testing ACE SPEC Trends...")
    ace_trends = trends_analyzer.get_ace_spec_trends(test_archetype)
    if "weeks" in ace_trends and "datasets" in ace_trends:
        print(f"✅ ACE SPEC Trends structure valid. Found {len(ace_trends['datasets'])} cards.")
        for ds in ace_trends["datasets"]:
            print(f"   - {ds['label']}")
    else:
        print("❌ Invalid ACE SPEC Trends structure")

if __name__ == "__main__":
    verify_deep_analysis()
