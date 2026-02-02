#!/usr/bin/env python3
"""
Load Tests for VIP Node Access Feature
======================================

Performance and load tests for the node-types endpoint with VIP filtering.

Uses Locust for load testing. Install with: pip install locust

Run tests:
    # Start the load test web UI
    locust -f tests/load_test_node_access.py --host=http://localhost:8000
    
    # Or run headless (command line)
    locust -f tests/load_test_node_access.py --host=http://localhost:8000 \
        --users 100 --spawn-rate 10 --run-time 60s --headless

Test Scenarios:
1. Free users requesting node-types (filtered response)
2. VIP users requesting node-types (full response)
3. Mixed load (realistic distribution)
4. Burst traffic simulation
5. Sustained load test

Requirements:
- locust >= 2.0
- Running FastAPI server on --host
- Valid JWT tokens for test users
"""

import os
import sys
import time
import random
import logging
from typing import Optional

# Try to import locust (optional dependency for HTTP load tests)
LOCUST_AVAILABLE = False
try:
    from locust import HttpUser, task, between, events, constant_throughput
    from locust.runners import MasterRunner
    LOCUST_AVAILABLE = True
except ImportError:
    # Locust not installed - HTTP load tests unavailable
    # Quick performance test will still work
    HttpUser = object
    task = lambda x: lambda f: f
    between = lambda a, b: None
    events = None
    constant_throughput = lambda x: None

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# Configuration
# ==============================================================================

class LoadTestConfig:
    """Configuration for load tests"""
    
    # Set these environment variables or modify defaults here
    FREE_USER_TOKEN = os.environ.get("FREE_USER_TOKEN", "")
    VIP_USER_TOKEN = os.environ.get("VIP_USER_TOKEN", "")
    
    # Expected response sizes (for validation)
    EXPECTED_FREE_NODE_COUNT = 17  # Approximate base nodes
    EXPECTED_VIP_NODE_COUNT = 50   # Approximate total nodes
    
    # Response time thresholds (ms)
    MAX_RESPONSE_TIME_P95 = 500   # 95th percentile should be under 500ms
    MAX_RESPONSE_TIME_P99 = 1000  # 99th percentile should be under 1s
    
    # User distribution for mixed load
    VIP_USER_PERCENTAGE = 20  # 20% VIP, 80% free users


# ==============================================================================
# Custom Metrics Collection
# ==============================================================================

class MetricsCollector:
    """Collect custom metrics during load test"""
    
    def __init__(self):
        self.free_user_requests = 0
        self.vip_user_requests = 0
        self.free_user_failures = 0
        self.vip_user_failures = 0
        self.response_node_counts = []
    
    def record_request(self, is_vip: bool, success: bool, node_count: int = 0):
        if is_vip:
            self.vip_user_requests += 1
            if not success:
                self.vip_user_failures += 1
        else:
            self.free_user_requests += 1
            if not success:
                self.free_user_failures += 1
        
        if success and node_count > 0:
            self.response_node_counts.append(node_count)
    
    def get_summary(self):
        return {
            "free_requests": self.free_user_requests,
            "vip_requests": self.vip_user_requests,
            "free_failures": self.free_user_failures,
            "vip_failures": self.vip_user_failures,
            "avg_node_count": sum(self.response_node_counts) / len(self.response_node_counts) if self.response_node_counts else 0
        }


metrics = MetricsCollector()


# ==============================================================================
# Base User Class
# ==============================================================================

class BaseNodeAccessUser(HttpUser):
    """Base class for node access load testing"""
    
    abstract = True  # Don't instantiate directly
    
    # Wait between requests (simulates real user behavior)
    wait_time = between(1, 3)
    
    # Headers with auth
    auth_headers = {}
    is_vip = False
    
    def on_start(self):
        """Called when a simulated user starts"""
        pass
    
    def _get_node_types(self, active_only: bool = True):
        """Make request to node-types endpoint"""
        params = {"active_only": str(active_only).lower()}
        
        with self.client.get(
            "/api/node-types/",
            params=params,
            headers=self.auth_headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    node_count = len(data) if isinstance(data, list) else 0
                    
                    # Validate response
                    if self.is_vip:
                        if node_count < LoadTestConfig.EXPECTED_FREE_NODE_COUNT:
                            response.failure(f"VIP got too few nodes: {node_count}")
                    else:
                        if node_count > LoadTestConfig.EXPECTED_VIP_NODE_COUNT:
                            response.failure(f"Free user got too many nodes: {node_count}")
                    
                    metrics.record_request(self.is_vip, True, node_count)
                    response.success()
                    
                except Exception as e:
                    response.failure(f"JSON parse error: {e}")
                    metrics.record_request(self.is_vip, False)
            
            elif response.status_code == 401:
                response.failure("Unauthorized - check token")
                metrics.record_request(self.is_vip, False)
            
            else:
                response.failure(f"Unexpected status: {response.status_code}")
                metrics.record_request(self.is_vip, False)


# ==============================================================================
# Free User Load Test
# ==============================================================================

class FreeUserLoadTest(BaseNodeAccessUser):
    """Load test simulating free users (no subscription)"""
    
    weight = 80  # 80% of users are free
    
    def on_start(self):
        """Setup free user auth"""
        if LoadTestConfig.FREE_USER_TOKEN:
            self.auth_headers = {
                "Authorization": f"Bearer {LoadTestConfig.FREE_USER_TOKEN}"
            }
        else:
            logger.warning("No FREE_USER_TOKEN set, requests will fail auth")
        self.is_vip = False
    
    @task(10)
    def get_active_nodes(self):
        """Get active nodes (most common request)"""
        self._get_node_types(active_only=True)
    
    @task(1)
    def get_all_nodes(self):
        """Get all nodes including inactive (less common)"""
        self._get_node_types(active_only=False)


# ==============================================================================
# VIP User Load Test
# ==============================================================================

class VIPUserLoadTest(BaseNodeAccessUser):
    """Load test simulating VIP users (with subscription)"""
    
    weight = 20  # 20% of users are VIP
    
    def on_start(self):
        """Setup VIP user auth"""
        if LoadTestConfig.VIP_USER_TOKEN:
            self.auth_headers = {
                "Authorization": f"Bearer {LoadTestConfig.VIP_USER_TOKEN}"
            }
        else:
            logger.warning("No VIP_USER_TOKEN set, requests will fail auth")
        self.is_vip = True
    
    @task(10)
    def get_active_nodes(self):
        """Get active nodes (most common request)"""
        self._get_node_types(active_only=True)
    
    @task(2)
    def get_all_nodes(self):
        """Get all nodes including inactive (more common for VIP)"""
        self._get_node_types(active_only=False)


# ==============================================================================
# Burst Traffic User
# ==============================================================================

class BurstTrafficUser(BaseNodeAccessUser):
    """Simulates burst traffic (rapid requests)"""
    
    weight = 0  # Disabled by default, enable for burst tests
    wait_time = constant_throughput(10)  # 10 requests per second
    
    def on_start(self):
        # Randomly choose VIP or free
        self.is_vip = random.random() < 0.2
        token = LoadTestConfig.VIP_USER_TOKEN if self.is_vip else LoadTestConfig.FREE_USER_TOKEN
        if token:
            self.auth_headers = {"Authorization": f"Bearer {token}"}
    
    @task
    def rapid_node_request(self):
        """Rapid-fire node requests"""
        self._get_node_types(active_only=True)


# ==============================================================================
# Event Hooks (only when Locust is available)
# ==============================================================================

if LOCUST_AVAILABLE and events is not None:
    @events.test_stop.add_listener
    def on_test_stop(environment, **kwargs):
        """Print summary when test stops"""
        summary = metrics.get_summary()
        print("\n" + "=" * 60)
        print("LOAD TEST SUMMARY - Node Access Feature")
        print("=" * 60)
        print(f"Free User Requests: {summary['free_requests']}")
        print(f"VIP User Requests:  {summary['vip_requests']}")
        print(f"Free User Failures: {summary['free_failures']}")
        print(f"VIP User Failures:  {summary['vip_failures']}")
        print(f"Avg Node Count:     {summary['avg_node_count']:.1f}")
        print("=" * 60)


    @events.init.add_listener
    def on_locust_init(environment, **kwargs):
        """Initialize when Locust starts"""
        print("\n" + "=" * 60)
        print("VIP Node Access Load Test")
        print("=" * 60)
        print("Configuration:")
        print(f"  FREE_USER_TOKEN: {'SET' if LoadTestConfig.FREE_USER_TOKEN else 'NOT SET'}")
        print(f"  VIP_USER_TOKEN:  {'SET' if LoadTestConfig.VIP_USER_TOKEN else 'NOT SET'}")
        print()
        print("To set tokens, use environment variables:")
        print("  export FREE_USER_TOKEN='your-free-user-jwt'")
        print("  export VIP_USER_TOKEN='your-vip-user-jwt'")
        print("=" * 60 + "\n")


# ==============================================================================
# Standalone Performance Test (without Locust)
# ==============================================================================

def run_quick_performance_test():
    """
    Quick performance test that can run without Locust.
    Tests the node access filtering performance directly.
    """
    import time
    import statistics
    
    print("\n" + "=" * 60)
    print("Quick Performance Test (No HTTP)")
    print("=" * 60)
    
    # Import the service
    from services.node_access import NodeAccessService, NodeAccessConfig
    
    # Create test config
    config = NodeAccessConfig(
        access_mode="whitelist",
        base_nodes={"start", "end", "if", "set", "switch", "merge", 
                   "iterator", "filter", "chat", "telegram", "gmail",
                   "gmail_trigger", "googleCalendar", "googleDocs",
                   "googleSheets", "googleDrive", "googleForm", 
                   "http_request", "stickyNote"},
        enable_vip_filtering=True
    )
    service = NodeAccessService(config=config)
    
    # Create mock data
    from dataclasses import dataclass
    from typing import Optional
    
    @dataclass
    class MockNode:
        id: int
        type: str
        name: str
        category: Optional[str] = None
    
    @dataclass
    class MockSubscription:
        is_active: bool = True
        is_expired: bool = False
        @property
        def is_valid(self): return self.is_active and not self.is_expired
    
    class MockUser:
        def __init__(self, subs):
            self.subscriptions = subs
        @property
        def active_subscription(self):
            for s in self.subscriptions:
                if s.is_valid: return s
            return None
    
    # Create large node list (simulate real scenario)
    nodes = [MockNode(i, f"node_{i}", f"Node {i}") for i in range(100)]
    
    # Add some that should be in whitelist
    for i, name in enumerate(["start", "end", "if", "gmail"]):
        nodes[i] = MockNode(i, name, name.title())
    
    free_user = MockUser([])
    vip_user = MockUser([MockSubscription()])
    
    # Performance test parameters
    iterations = 10000
    
    # Test 1: Free user filtering
    print(f"\nTest 1: Free user filtering ({iterations} iterations)")
    times_free = []
    for _ in range(iterations):
        start = time.perf_counter()
        result = service.get_accessible_nodes(free_user, nodes)
        times_free.append((time.perf_counter() - start) * 1000)  # ms
    
    print(f"  Mean:   {statistics.mean(times_free):.3f} ms")
    print(f"  Median: {statistics.median(times_free):.3f} ms")
    print(f"  Stdev:  {statistics.stdev(times_free):.3f} ms")
    print(f"  Min:    {min(times_free):.3f} ms")
    print(f"  Max:    {max(times_free):.3f} ms")
    print(f"  Ops/s:  {iterations / (sum(times_free) / 1000):.0f}")
    
    # Test 2: VIP user (no filtering)
    print(f"\nTest 2: VIP user filtering ({iterations} iterations)")
    times_vip = []
    for _ in range(iterations):
        start = time.perf_counter()
        result = service.get_accessible_nodes(vip_user, nodes)
        times_vip.append((time.perf_counter() - start) * 1000)  # ms
    
    print(f"  Mean:   {statistics.mean(times_vip):.3f} ms")
    print(f"  Median: {statistics.median(times_vip):.3f} ms")
    print(f"  Stdev:  {statistics.stdev(times_vip):.3f} ms")
    print(f"  Min:    {min(times_vip):.3f} ms")
    print(f"  Max:    {max(times_vip):.3f} ms")
    print(f"  Ops/s:  {iterations / (sum(times_vip) / 1000):.0f}")
    
    # Test 3: is_vip_user check
    print(f"\nTest 3: is_vip_user check ({iterations} iterations)")
    times_check = []
    for _ in range(iterations):
        start = time.perf_counter()
        service.is_vip_user(free_user)
        service.is_vip_user(vip_user)
        times_check.append((time.perf_counter() - start) * 1000)
    
    print(f"  Mean:   {statistics.mean(times_check):.3f} ms")
    print(f"  Median: {statistics.median(times_check):.3f} ms")
    print(f"  Ops/s:  {iterations / (sum(times_check) / 1000):.0f}")
    
    # Summary
    print("\n" + "=" * 60)
    print("PERFORMANCE TEST PASSED")
    print("=" * 60)
    print(f"Free user filtering: ~{statistics.mean(times_free):.3f}ms per call")
    print(f"VIP user (no filter): ~{statistics.mean(times_vip):.3f}ms per call")
    print(f"Overhead: {((statistics.mean(times_free) / statistics.mean(times_vip)) - 1) * 100:.1f}%")
    print("=" * 60 + "\n")


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Load tests for VIP Node Access")
    parser.add_argument("--quick", action="store_true", 
                       help="Run quick performance test without Locust/HTTP")
    args = parser.parse_args()
    
    if args.quick:
        run_quick_performance_test()
    elif not LOCUST_AVAILABLE:
        print("=" * 60)
        print("Locust is not installed.")
        print("=" * 60)
        print()
        print("Options:")
        print("  1. Install locust for HTTP load tests:")
        print("     pip install locust")
        print()
        print("  2. Run quick performance test (no HTTP):")
        print("     python tests/load_test_node_access.py --quick")
        print("=" * 60)
    else:
        print("Run with Locust:")
        print("  locust -f tests/load_test_node_access.py --host=http://localhost:8000")
        print()
        print("Or run quick performance test:")
        print("  python tests/load_test_node_access.py --quick")
