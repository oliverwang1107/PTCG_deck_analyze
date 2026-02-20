import time
import unittest
from src.web.app import app, data_manager

class Benchmark(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        # Ensure data is loaded once before benchmarking to be fair to "hot cache" scenario
        data_manager.get_data()

    def test_overview_performance(self):
        start = time.time()
        for _ in range(10):
            self.client.get('/api/overview')
        end = time.time()
        avg = (end - start) / 10
        print(f"Average /api/overview response time: {avg:.4f}s")
        self.assertLess(avg, 0.1, "Overview API is too slow")

    def test_archetypes_performance(self):
        start = time.time()
        for _ in range(10):
            self.client.get('/api/archetypes')
        end = time.time()
        avg = (end - start) / 10
        print(f"Average /api/archetypes response time: {avg:.4f}s")
        self.assertLess(avg, 0.2, "Archetypes API is too slow")

    def test_archetype_detail_performance(self):
        # Need a valid archetype name. Let's find one first.
        data = data_manager.get_data()
        if not data["tournaments"]:
            print("Skipping detail benchmark (no data)")
            return
            
        # Find a popular archetype
        from src.analyzer.archetype import ArchetypeAnalyzer
        analyzer = ArchetypeAnalyzer(data)
        top = analyzer.get_top_archetypes(1)
        if not top:
            return
        name = top[0].name
        
        start = time.time()
        for _ in range(10):
            self.client.get(f'/api/archetype/{name}/detail')
        end = time.time()
        avg = (end - start) / 10
        print(f"Average /api/archetype/detail response time: {avg:.4f}s")
        self.assertLess(avg, 0.3, "Archetype Detail API is too slow")

if __name__ == "__main__":
    unittest.main()
