import unittest
from unittest.mock import MagicMock
from src.web.app import app
from src.analyzer.archetype import ArchetypeAnalyzer

class TestRecentDecks(unittest.TestCase):
    def test_api_returns_50_decks(self):
        # Create a mock analyzer that returns 60 decks
        mock_decks = [{"player_name": f"Player {i}", "placement": i, "date": "2025-01-01"} for i in range(60)]
        
        # Patch the ArchetypeAnalyzer.get_recent_decks method
        original_method = ArchetypeAnalyzer.get_recent_decks
        ArchetypeAnalyzer.get_recent_decks = MagicMock(return_value=mock_decks[:50])
        
        # Determine strict limit or just check it calls with limit=50
        
        with app.test_client() as client:
            # We need to mock get_data as well since the API calls it
            with unittest.mock.patch('src.web.app.get_data') as mock_get_data:
                mock_get_data.return_value = {
                    "tournaments": [], # Empty is fine, we mocked the analyzer method call effectively? 
                    # Wait, app.py instantiates ArchetypeAnalyzer(window_data).
                    # So we need to patch ArchetypeAnalyzer class in app.py context or just the method.
                    "has_card_data": False
                }
                
                # Actually, simpler to just inspect the code or use a functional test if we had data.
                # Since we don't know if the user has data, let's just verify the app.py logic by 
                # strictly checking the limit argument passed to get_recent_decks.
                
                from src.web.app import api_archetype_detail
                
                # Mock request args
                with app.test_request_context('/api/archetype/Test/detail'):
                     # We need to mock ArchetypeAnalyzer instance used inside the view
                     with unittest.mock.patch('src.web.app.ArchetypeAnalyzer') as MockAnalyzer:
                        mock_instance = MockAnalyzer.return_value
                        mock_instance.get_archetype_detail.return_value = {}
                        mock_instance.get_recent_decks.return_value = []
                        
                        # Call the view function directly or via client
                        client.get('/api/archetype/Test/detail')
                        
                        # Verify get_recent_decks was called with limit=50
                        mock_instance.get_recent_decks.assert_called_with('Test', limit=50)
                        print("\nSUCCESS: api_archetype_detail called get_recent_decks with limit=50")

        # Restore
        ArchetypeAnalyzer.get_recent_decks = original_method

if __name__ == "__main__":
    unittest.main()
