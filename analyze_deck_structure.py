"""Detailed analysis of Limitless deck page structure."""
import requests
from bs4 import BeautifulSoup
import re

print("Fetching deck page...")
resp = requests.get('https://limitlesstcg.com/decks/list/jp/16477', 
                    headers={'User-Agent': 'PTCG-Analyzer/1.0'})
soup = BeautifulSoup(resp.text, 'lxml')

# Find the decklist container
decklist = soup.select_one('.decklist')
if decklist:
    print("=== DECKLIST STRUCTURE ===\n")
    
    # Look for card sections
    sections = decklist.select('.decklist-section, .section')
    print(f"Found {len(sections)} sections\n")
    
    # Look for individual card entries
    card_entries = decklist.select('.decklist-card')
    print(f"Found {len(card_entries)} card entries\n")
    
    # Parse first few cards
    for i, card in enumerate(card_entries[:15]):
        card_text = card.get_text(strip=True)
        print(f"Card {i+1}: {card_text[:60]}")
        
        # Look for card link
        card_link = card.select_one('a.card-link')
        if card_link:
            href = card_link.get('href', '')
            name = card_link.get_text(strip=True)
            print(f"  Link: {href[:50]}... Name: {name}")
        
        # Look for count
        count_elem = card.select_one('.count, span:first-child')
        if count_elem:
            print(f"  Count element: {count_elem.get_text(strip=True)}")
    
    print("\n=== RAW HTML OF FIRST CARD ===")
    if card_entries:
        print(card_entries[0].prettify()[:500])
    
    # Look for section headers (Pokemon/Trainer/Energy)
    print("\n=== SECTION HEADERS ===")
    headers = decklist.select('h3, h4, .section-title, [class*="section"]')
    for h in headers[:5]:
        print(f"Header: {h.get('class')} - {h.get_text(strip=True)[:30]}")
        
    # Alternative: look for text patterns
    all_text = decklist.get_text()
    if 'Pokémon' in all_text or 'Pokemon' in all_text:
        print("\n=== TEXT CONTAINS POKEMON SECTION ===")
    if 'Trainer' in all_text:
        print("=== TEXT CONTAINS TRAINER SECTION ===")
    if 'Energy' in all_text:
        print("=== TEXT CONTAINS ENERGY SECTION ===")

    # Parse by looking at the full structure
    print("\n=== DECKLIST-CARDS CONTAINER ===")
    cards_container = decklist.select_one('.decklist-cards')
    if cards_container:
        print(cards_container.prettify()[:1000])
else:
    print("No decklist found")
    print(f"Page title: {soup.title.get_text() if soup.title else 'N/A'}")
