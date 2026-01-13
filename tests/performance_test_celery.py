"""
Performance tests for Celery infrastructure vs synchronous architecture.
Tests concurrent requests, response times, and task completion times.

Usage:
    # Test with Celery only:
    python tests/performance_test_celery.py --celery
    
    # Test synchronous only:
    python tests/performance_test_celery.py --sync
    
    # Test both (default):
    python tests/performance_test_celery.py
"""

import requests
import time
import json
import statistics
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import os
import argparse
import random
import string

# Use different URLs for different setups
CELERY_URL = "http://localhost:5000"  # Dockerized Celery setup
SYNC_URL = "http://localhost:5000"    # Synchronous previous setup

RESULTS_DIR = "tests/output/results"

# Test scenarios
TEST_SCENARIOS = {
    "very_light_load": {"concurrent_requests": 100, "total_requests": 100},
    "light_load": {"concurrent_requests": 1000, "total_requests": 1000},
    "medium_load": {"concurrent_requests": 10000, "total_requests": 10000},
    "heavy_load": {"concurrent_requests": 100000, "total_requests": 100000},
}

# Query randomization components
INGREDIENTS = [
    "chicken", "beef", "pork", "fish", "salmon", "tuna", "shrimp", "tofu",
    "pasta", "rice", "potato", "tomato", "onion", "garlic", "cheese", "egg",
    "flour", "milk", "butter", "oil", "salt", "pepper", "basil", "oregano",
    "carrot", "celery", "lemon", "lime", "ginger", "soy sauce", "wine", "broth",
    "spinach", "mushroom", "bell pepper", "zucchini", "eggplant", "avocado"
]

MEAL_TYPES = ["Breakfast", "Lunch", "Dinner"]

DIFFICULTY_LEVELS = [1, 2, 3]  # 1=easy, 2=moderate, 3=difficult

def generate_random_query() -> Dict[str, Any]:
    """
    Generate a randomized complex query matching /recipes endpoint parameters.
    
    Based on your actual API:
    - ingredients (str): Comma-separated or JSON list
    - vegan (bool): Filter for vegan recipes
    - vegetarian (bool): Filter for vegetarian recipes
    - meal_type (str): Breakfast, Lunch, Dinner, etc.
    - time (int): Maximum preparation time in minutes
    - difficulty (int): 1=easy, 2=moderate, 3=difficult
    - calories_min/calories_max (float)
    - protein_min/protein_max (float)
    - fat_min/fat_max (float)
    - carbohydrates_min/carbohydrates_max (float)
    - page (int), per_page (int)
    """
    complexity = random.randint(1, 4)
    
    query = {}
    
    # Always include at least one ingredient (1-4 ingredients for variety)
    num_ingredients = random.randint(1, 4)
    query['ingredients'] = ','.join(random.sample(INGREDIENTS, num_ingredients))
    
    # Add filters based on complexity level
    if complexity >= 2:
        # Add dietary restrictions or meal type
        if random.random() > 0.5:
            query['vegan'] = random.choice(['true', 'false'])
        else:
            query['vegetarian'] = random.choice(['true', 'false'])
        
        query['meal_type'] = random.choice(MEAL_TYPES)
    
    if complexity >= 3:
        # Add time and difficulty constraints
        query['time'] = random.randint(10, 120)  # 10-120 minutes
        query['difficulty'] = random.choice(DIFFICULTY_LEVELS)
        
        # Add one nutritional constraint
        nutrition_choice = random.choice(['calories', 'protein', 'fat', 'carbohydrates'])
        if nutrition_choice == 'calories':
            query['calories_min'] = random.randint(100, 400)
            query['calories_max'] = random.randint(500, 1000)
        elif nutrition_choice == 'protein':
            query['protein_min'] = random.randint(5, 20)
            query['protein_max'] = random.randint(30, 80)
        elif nutrition_choice == 'fat':
            query['fat_min'] = random.randint(5, 15)
            query['fat_max'] = random.randint(20, 60)
        else:  # carbohydrates
            query['carbohydrates_min'] = random.randint(10, 40)
            query['carbohydrates_max'] = random.randint(50, 150)
    
    if complexity >= 4:
        # Add multiple nutritional constraints for maximum complexity
        query['calories_min'] = random.randint(200, 500)
        query['calories_max'] = random.randint(600, 1200)
        query['protein_min'] = random.randint(10, 25)
        query['protein_max'] = random.randint(30, 100)
        
        # Add pagination parameters (to vary queries further)
        query['per_page'] = random.choice([10, 20, 50, 100])
    
    # Add unique identifiers to prevent caching
    # These parameters will be ignored API but ensure unique queries
    query['_cache_bust'] = datetime.now().isoformat()
    query['_random'] = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    return query

class PerformanceTester:
    def __init__(self, base_url: str, use_celery: bool = True):
        self.base_url = base_url
        self.use_celery = use_celery
        self.results = []
        self.error_summary = {}  # Track error types
        
        # Create results directory
        os.makedirs(RESULTS_DIR, exist_ok=True)
        
        # Verify server is accessible
        print(f"\nChecking server at {base_url}...")
        if not self._check_server():
            raise ConnectionError(
                f"Cannot connect to server at {base_url}\n"
                f"Please ensure the {'Celery' if use_celery else 'synchronous'} server is running."
            )
        print(f"✓ Server is responding\n")
    
    def _check_server(self) -> bool:
        """Check if server is accessible."""
        try:
            session = requests.Session()
            response = session.get(f"{self.base_url}/recipes", timeout=5, params={"per_page": 1})
            return response.status_code in [200, 400, 422]
        except:
            return False
    
    def make_request(self, endpoint: str, method: str = "GET", 
                     data: Dict = None, params: Dict = None, 
                     randomize_query: bool = False) -> Dict[str, Any]:
        """Make a single request and measure performance."""
        start_time = time.time()
        
        # Generate random query if requested
        if randomize_query and method == "GET":
            params = generate_random_query()
        elif randomize_query and method == "POST":
            data = generate_random_query()
        
        # Create a new session for each request to ensure separate client behavior
        session = requests.Session()
        
        try:
            if method == "GET":
                response = session.get(
                    f"{self.base_url}{endpoint}",
                    params=params,
                    timeout=60
                )
            elif method == "POST":
                response = session.post(
                    f"{self.base_url}{endpoint}",
                    json=data,
                    timeout=60
                )
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            end_time = time.time()
            
            result = {
                "endpoint": endpoint,
                "method": method,
                "status_code": response.status_code,
                "response_time": end_time - start_time,
                "success": response.status_code == 200,
                "timestamp": datetime.now().isoformat(),
                "use_celery": self.use_celery,
                "query_params": params if method == "GET" else data
            }
            
            # Track error details for non-200 responses
            if response.status_code != 200:
                error_key = f"HTTP_{response.status_code}"
                self.error_summary[error_key] = self.error_summary.get(error_key, 0) + 1
                try:
                    result["error_response"] = response.json()
                except:
                    result["error_response"] = response.text[:200]
            
            # Try to extract task_id if present (for Celery endpoints)
            try:
                response_data = response.json()
                if "task_id" in response_data:
                    result["task_id"] = response_data["task_id"]
            except:
                pass
            
            return result
            
        except Exception as e:
            end_time = time.time()
            error_type = type(e).__name__
            self.error_summary[error_type] = self.error_summary.get(error_type, 0) + 1
            
            return {
                "endpoint": endpoint,
                "method": method,
                "status_code": 0,
                "response_time": end_time - start_time,
                "success": False,
                "error": str(e),
                "error_type": error_type,
                "timestamp": datetime.now().isoformat(),
                "use_celery": self.use_celery
            }
    
    def concurrent_requests(self, endpoint: str, num_requests: int, 
                           max_workers: int, method: str = "GET",
                           data: Dict = None, randomize_query: bool = False) -> List[Dict[str, Any]]:
        """Execute multiple concurrent requests."""
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.make_request, endpoint, method, data, None, randomize_query)
                for _ in range(num_requests)
            ]
            
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                self.results.append(result)
        
        return results
    
    def test_endpoint_scenario(self, endpoint: str, scenario_name: str,
                               method: str = "GET", data: Dict = None,
                               randomize_query: bool = False) -> Dict[str, Any]:
        """Test a specific endpoint with a given scenario."""
        scenario = TEST_SCENARIOS[scenario_name]
        
        print(f"\nTesting {endpoint} - {scenario_name}")
        print(f"  Concurrent: {scenario['concurrent_requests']}, Total: {scenario['total_requests']}")
        print(f"  Using Celery: {self.use_celery}")
        print(f"  Randomized queries: {randomize_query}")
        
        # Clear error summary for this scenario
        self.error_summary = {}
        
        start_time = time.time()
        results = self.concurrent_requests(
            endpoint,
            scenario['total_requests'],
            scenario['concurrent_requests'],
            method,
            data,
            randomize_query
        )
        total_time = time.time() - start_time
        
        # Calculate statistics
        response_times = [r['response_time'] for r in results]
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        stats = {
            "scenario": scenario_name,
            "endpoint": endpoint,
            "use_celery": self.use_celery,
            "total_requests": len(results),
            "successful_requests": len(successful),
            "failed_requests": len(results) - len(successful),
            "success_rate": len(successful) / len(results) * 100,
            "total_time": total_time,
            "requests_per_second": len(results) / total_time,
            "avg_response_time": statistics.mean(response_times),
            "median_response_time": statistics.median(response_times),
            "min_response_time": min(response_times),
            "max_response_time": max(response_times),
            "stdev_response_time": statistics.stdev(response_times) if len(response_times) > 1 else 0,
            "p95_response_time": self._percentile(response_times, 95),
            "p99_response_time": self._percentile(response_times, 99),
            "error_summary": self.error_summary.copy()
        }
        
        print(f"  Completed in {total_time:.2f}s")
        print(f"  Success rate: {stats['success_rate']:.1f}%")
        print(f"  Avg response time: {stats['avg_response_time']:.3f}s")
        print(f"  Requests/sec: {stats['requests_per_second']:.2f}")
        
        # Print error summary if there are failures
        if failed:
            print(f"\n  ⚠ Error Summary:")
            for error_type, count in sorted(self.error_summary.items(), key=lambda x: x[1], reverse=True):
                print(f"    - {error_type}: {count} occurrences")
            
            # Show sample failed request details
            print(f"\n  Sample Failed Request:")
            sample_fail = failed[0]
            print(f"    Status Code: {sample_fail.get('status_code')}")
            if 'error' in sample_fail:
                print(f"    Error: {sample_fail['error'][:150]}")
            if 'error_response' in sample_fail:
                print(f"    Response: {str(sample_fail['error_response'])[:200]}")
            if 'query_params' in sample_fail:
                print(f"    Query Params: {str(sample_fail['query_params'])[:200]}")
        
        return stats
    
    def test_endpoint_scenario_multiple_runs(self, endpoint: str, scenario_name: str,
                                            method: str = "GET", data: Dict = None,
                                            num_runs: int = 7, randomize_query: bool = False) -> Dict[str, Any]:
        """Run test scenario multiple times and keep middle 5 runs."""
        print(f"\n{'=' * 80}")
        print(f"Running {num_runs} iterations for {endpoint} - {scenario_name}")
        print(f"{'=' * 80}")
        
        all_run_stats = []
        
        # Run the test num_runs times
        for run_num in range(1, num_runs + 1):
            print(f"\n--- Run {run_num}/{num_runs} ---")
            stats = self.test_endpoint_scenario(endpoint, scenario_name, method, data, randomize_query)
            stats['run_number'] = run_num
            all_run_stats.append(stats)
            
            # Small delay between runs
            if run_num < num_runs:
                time.sleep(2)
        
        # Sort by avg_response_time and discard best and worst
        sorted_stats = sorted(all_run_stats, key=lambda x: x['avg_response_time'])
        
        # Keep middle 5 runs (discard first and last)
        kept_runs = sorted_stats[1:-1]
        
        print(f"\n{'=' * 80}")
        print(f"Keeping runs (by avg_response_time): {[r['run_number'] for r in kept_runs]}")
        print(f"Discarded best: Run {sorted_stats[0]['run_number']} ({sorted_stats[0]['avg_response_time']:.3f}s)")
        print(f"Discarded worst: Run {sorted_stats[-1]['run_number']} ({sorted_stats[-1]['avg_response_time']:.3f}s)")
        print(f"{'=' * 80}")
        
        # Calculate averages from kept runs
        metrics_to_average = [
            'total_time', 'requests_per_second', 'avg_response_time',
            'median_response_time', 'min_response_time', 'max_response_time',
            'stdev_response_time', 'p95_response_time', 'p99_response_time',
            'success_rate', 'successful_requests', 'failed_requests'
        ]
        
        averaged_stats = {
            "scenario": scenario_name,
            "endpoint": endpoint,
            "use_celery": self.use_celery,
            "total_requests": kept_runs[0]['total_requests'],
            "num_runs": len(kept_runs),
            "runs_data": kept_runs,
        }
        
        # Add averages for each metric
        for metric in metrics_to_average:
            values = [run[metric] for run in kept_runs]
            averaged_stats[f"{metric}_avg"] = statistics.mean(values)
            averaged_stats[f"{metric}_min"] = min(values)
            averaged_stats[f"{metric}_max"] = max(values)
            averaged_stats[f"{metric}_stdev"] = statistics.stdev(values) if len(values) > 1 else 0
        
        # For backward compatibility, add non-suffixed versions using avg
        for metric in metrics_to_average:
            averaged_stats[metric] = averaged_stats[f"{metric}_avg"]
        
        print(f"\nAveraged Results (5 runs):")
        print(f"  Avg response time: {averaged_stats['avg_response_time']:.3f}s ± {averaged_stats['avg_response_time_stdev']:.3f}s")
        print(f"  Requests/sec: {averaged_stats['requests_per_second']:.2f} ± {averaged_stats['requests_per_second_stdev']:.2f}")
        print(f"  Success rate: {averaged_stats['success_rate']:.1f}% ± {averaged_stats['success_rate_stdev']:.1f}%")
        
        return averaged_stats
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile."""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def save_results(self, append: bool = False):
        """Save results to JSON file."""
        filename = "results_all.json"
        filepath = os.path.join(RESULTS_DIR, filename)
        
        if append and os.path.exists(filepath):
            # Load existing results and append
            try:
                with open(filepath, 'r') as f:
                    existing_results = json.load(f)
                combined_results = existing_results + self.results
            except:
                combined_results = self.results
        else:
            combined_results = self.results
        
        with open(filepath, 'w') as f:
            json.dump(combined_results, f, indent=2)
        print(f"\nResults saved to {filepath}")
    
    def run_full_test_suite(self, endpoints: List[Dict[str, Any]]):
        """Run complete test suite on all endpoints."""
        all_stats = []
        
        for endpoint_config in endpoints:
            endpoint = endpoint_config['endpoint']
            method = endpoint_config.get('method', 'GET')
            data = endpoint_config.get('data', None)
            randomize_query = endpoint_config.get('randomize_query', False)
            
            for scenario_name in TEST_SCENARIOS.keys():
                stats = self.test_endpoint_scenario_multiple_runs(
                    endpoint, scenario_name, method, data, num_runs=7, randomize_query=randomize_query
                )
                all_stats.append(stats)
        
        # Save aggregated statistics
        stats_filename = "stats_all.json"
        stats_filepath = os.path.join(RESULTS_DIR, stats_filename)
        
        # Append to existing stats if file exists
        if os.path.exists(stats_filepath):
            try:
                with open(stats_filepath, 'r') as f:
                    existing_stats = json.load(f)
                all_stats = existing_stats + all_stats
            except:
                pass
        
        with open(stats_filepath, 'w') as f:
            json.dump(all_stats, f, indent=2)
        
        print(f"\nStatistics saved to {stats_filepath}")
        return all_stats


def main():
    """Main test execution with CLI arguments."""
    
    parser = argparse.ArgumentParser(description='Performance tests for Celery vs Synchronous')
    parser.add_argument('--celery', action='store_true', help='Test with Celery only')
    parser.add_argument('--sync', action='store_true', help='Test synchronous only')
    args = parser.parse_args()
    
    # Determine which tests to run
    run_celery = args.celery or (not args.celery and not args.sync)
    run_sync = args.sync or (not args.celery and not args.sync)
    
    # ENDPOINTS TO TEST
    ENDPOINTS = [
        {
            "endpoint": "/recipes",
            "method": "GET",
            "randomize_query": True
        }
    ]
    
    print("=" * 80)
    print("CELERY PERFORMANCE TEST SUITE")
    print("=" * 80)
    print("\nTest Configuration:")
    print(f"  - Celery URL: {CELERY_URL}")
    print(f"  - Sync URL: {SYNC_URL}")
    print(f"  - Randomized complex queries: ENABLED (prevents server-side caching)")
    print(f"  - Query parameters match /recipes API specification")
    print(f"  - Load scenarios: Very Light (100), Light (1K), Medium (10K), Heavy (100K)")
    print("\n" + "=" * 80)
    print("Query Parameters Being Used:")
    print("  - ingredients: 1-4 random ingredients")
    print("  - vegan/vegetarian: Random boolean filters")
    print("  - meal_type: Random meal type (Breakfast, Lunch, etc.)")
    print("  - time: Random max prep time (10-120 min)")
    print("  - difficulty: Random level (1-3)")
    print("  - Nutritional filters: calories/protein/fat/carbohydrates min/max")
    print("  - _cache_bust & _random: Unique identifiers per request")
    print("=" * 80)
    
    # Test with Celery
    if run_celery:
        print("\n" + "=" * 80)
        print("TESTING WITH CELERY ENABLED")
        print(f"Target: {CELERY_URL}")
        print("=" * 80)
        try:
            tester_celery = PerformanceTester(CELERY_URL, use_celery=True)
            stats_celery = tester_celery.run_full_test_suite(ENDPOINTS)
            tester_celery.save_results(append=True)
        except ConnectionError as e:
            print(f"\n❌ ERROR: {e}")
            print("\nTo start Celery setup:")
            print("  docker-compose up")
            if not run_sync:
                return
    
    # Test without Celery (synchronous)
    if run_sync:
        print("\n" + "=" * 80)
        print("TESTING WITH SYNCHRONOUS PROCESSING")
        print(f"Target: {SYNC_URL}")
        print("=" * 80)
        try:
            tester_sync = PerformanceTester(SYNC_URL, use_celery=False)
            stats_sync = tester_sync.run_full_test_suite(ENDPOINTS)
            tester_sync.save_results(append=True)
        except ConnectionError as e:
            print(f"\n❌ ERROR: {e}")
            print("\nTo start synchronous Flask server:")
            print("  python app.py")
            print("  # or")
            print("  flask run --port 5000")
            return
    
    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETED")
    print("=" * 80)
    print(f"Results saved to {RESULTS_DIR}/")
    print("\nRun the plotting script to visualize results:")
    print("  python tests/plot_performance_results.py")


if __name__ == "__main__":
    main()
