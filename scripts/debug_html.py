"""Debug the archetype extraction specifically."""
import requests
from bs4 import BeautifulSoup

url = "https://limitlesstcg.com/tournaments/jp/4027"

response = requests.get(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

soup = BeautifulSoup(response.text, "lxml")

# Get all rows
rows = soup.select("table tr")
print(f"Found {len(rows)} table rows")

for i, row in enumerate(rows[:4]):
    # Skip header
    if row.select("th"):
        print(f"Row {i}: HEADER")
        continue
    
    cells = row.select("td")
    print(f"\nRow {i}: {len(cells)} cells")
    
    # Look for img with alt
    imgs_with_alt = row.select("img[alt]")
    print(f"  img[alt] selector: {len(imgs_with_alt)} found")
    
    # Look for all images
    all_imgs = row.select("img")
    print(f"  All img tags: {len(all_imgs)} found")
    
    for img in all_imgs:
        attrs = dict(img.attrs)
        # Replace non-ASCII
        for k, v in list(attrs.items()):
            if isinstance(v, str):
                attrs[k] = ''.join(c if ord(c) < 128 else '?' for c in v)[:50]
            else:
                attrs[k] = str(v)[:50]
        print(f"    img attrs: {attrs}")
    
    # Extract archetype
    pokemon_names = []
    for img in all_imgs:
        alt = img.get("alt", "")
        if alt and alt.strip():
            pokemon_names.append(alt)
    
    archetype = " / ".join(pokemon_names[:2]) if pokemon_names else "Unknown"
    archetype = ''.join(c if ord(c) < 128 else '?' for c in archetype)
    print(f"  Extracted archetype: '{archetype}'")
