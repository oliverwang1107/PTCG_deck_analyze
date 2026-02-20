import requests
from bs4 import BeautifulSoup

def inspect():
    url = "https://limitlesstcg.com/tournaments/jp?page=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "lxml")
    
    # Find pagination container
    # Often it's a nav or div with class 'pagination'
    pagination = soup.select_one(".pagination, nav[aria-label='Pagination']")
    
    if pagination:
        print("Pagination HTML found:")
        print(pagination.prettify())
    else:
        print("No standard pagination container found.")
        # Print last few elements of body
        print(soup.select("body")[-1].prettify()[:1000] if soup.select("body") else "No body")

if __name__ == "__main__":
    inspect()
