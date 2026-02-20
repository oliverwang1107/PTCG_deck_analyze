import requests
from bs4 import BeautifulSoup

def check():
    url = "https://limitlesstcg.com/tournaments/jp?page=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "lxml")
    
    # Check count
    links = soup.select("a[href*='/tournaments/jp/']")
    seen = set()
    count = 0
    import re
    for link in links:
        href = link.get("href", "")
        match = re.search(r"/tournaments/jp/(\d+)", href)
        if match:
            tid = match.group(1)
            if tid not in seen:
                seen.add(tid)
                count += 1
    
    print(f"Page 1 count: {count}")
    
    # Check next link
    next_link = soup.select_one("a[rel='next'], .pagination a:contains('»')")
    print(f"Next link found: {bool(next_link)}")
    if next_link:
        print(f"Next link href: {next_link.get('href')}")

if __name__ == "__main__":
    check()
