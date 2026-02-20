
import requests
from bs4 import BeautifulSoup

def check_url(set_code, number):
    url = f"https://limitlesstcg.com/cards/{set_code}/{number}"
    print(f"Checking {url}...")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for JP Prints header
            jp_header = soup.find('th', string=lambda t: t and "JP. Prints" in t)
            if jp_header:
                print("Found JP Prints header!")
                current_row = jp_header.parent.find_next_sibling('tr')
                while current_row:
                    link = current_row.find('a', href=True)
                    if link:
                        print(f"  Found link: {link['href']}")
                        if '/cards/jp/' in link['href']:
                            print(f"  -> Match! {link.text.strip()}")
                    current_row = current_row.find_next_sibling('tr')
            else:
                print("JP Prints header NOT found.")
                
                # Print all headers to see what's there
                headers = soup.find_all('th')
                print("Headers found:", [h.text.strip() for h in headers])
        else:
            print("Failed to load page")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_url("TWM", "111")
