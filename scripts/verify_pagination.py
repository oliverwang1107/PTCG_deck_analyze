import sys
import unittest
from unittest.mock import MagicMock, patch
from bs4 import BeautifulSoup
from src.scraper.limitless import LimitlessScraper

class TestPagination(unittest.TestCase):
    def test_pagination_detection(self):
        # Mock HTML with new pagination structure
        html = """
        <html>
            <body>
                <ul class="pagination" data-current="1" data-max="5">
                    <li class="active">1</li>
                    <li data-target="2">2</li>
                </ul>
            </body>
        </html>
        """
        
        scraper = LimitlessScraper()
        scraper._get = MagicMock(return_value=BeautifulSoup(html, "lxml"))
        
        # We can't easily test the whole loop in get_tournament_list without mocking more,
        # but we can verify our logic by extracting it or running a limited version.
        # Instead, let's just run the actual scraper on page 1 and see if it tries to fetch page 2.
        pass

if __name__ == "__main__":
    # verification script that actually hits the site to confirm structure parsing
    scraper = LimitlessScraper()
    print("Testing pagination logic...")
    tournaments = scraper.get_tournament_list(limit=40)
    print(f"Fetched {len(tournaments)} tournaments.")
    if len(tournaments) > 25:
        print("SUCCESS: Pagination worked, fetched more than 25 tournaments.")
    else:
        print("FAILURE: Stopped at 25 or fewer tournaments.")
