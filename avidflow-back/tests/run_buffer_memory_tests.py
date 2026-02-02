#!/usr/bin/env python3
"""
Standalone Buffer Memory Test Runner

Run with:
    python tests/run_buffer_memory_tests.py

This script tests the buffer_memory module without requiring pytest.
Uses Python's built-in unittest framework.
"""
from __future__ import annotations

import gc
import sys
import time
import uuid
import logging
import threading
import unittest
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, '/home/toni/n8n/back')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#                              HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_conversation(num_turns: int) -> List[Dict[str, Any]]:
    """Create a realistic conversation with N turns."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
    for i in range(num_turns):
        messages.append({"role": "user", "content": f"User message {i+1}"})
        messages.append({"role": "assistant", "content": f"Assistant response {i+1}"})
    return messages


def create_fresh_store():
    """Create a fresh memory store for isolated testing."""
    from nodes.memory.buffer_memory import _InMemoryConversationStore
    import nodes.memory.buffer_memory as buffer_module
    
    # Create new store (disable cleanup greenlet for controlled testing)
    new_store = _InMemoryConversationStore.__new__(_InMemoryConversationStore)
    new_store._lock = threading.RLock()
    new_store._store = {}
    new_store._cleanup_running = True  # Prevent auto-spawn
    
    # Swap global store
    original_store = buffer_module._STORE
    buffer_module._STORE = new_store
    
    return new_store, original_store, buffer_module


def restore_store(buffer_module, original_store):
    """Restore original store."""
    buffer_module._STORE = original_store


# ═══════════════════════════════════════════════════════════════════════════════
#                              TEST CASES
# ═══════════════════════════════════════════════════════════════════════════════

class TestHighConcurrencySessionCreation(unittest.TestCase):
    """Test concurrent session creation."""
    
    def setUp(self):
        self.fresh_store, self.original_store, self.buffer_module = create_fresh_store()
        from nodes.memory.buffer_memory import MemoryManager
        self.memory_manager = MemoryManager
    
    def tearDown(self):
        restore_store(self.buffer_module, self.original_store)
    
    def test_concurrent_session_creation_1000_users(self):
        """Create 1,000 sessions concurrently and verify integrity."""
        NUM_SESSIONS = 1000
        NUM_THREADS = 50
        sessions_created = []
        errors = []
        lock = threading.Lock()
        
        def create_session(session_id: str):
            try:
                messages = create_conversation(3)
                self.memory_manager.save(session_id, messages, ttl_seconds=300)
                loaded = self.memory_manager.load(session_id, context_window=5)
                if len(loaded) > 0:
                    with lock:
                        sessions_created.append(session_id)
                else:
                    with lock:
                        errors.append(f"Session {session_id}: Empty after save")
            except Exception as e:
                with lock:
                    errors.append(f"Session {session_id}: {str(e)}")
        
        session_ids = [f"stress-test-{uuid.uuid4()}" for _ in range(NUM_SESSIONS)]
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            futures = [executor.submit(create_session, sid) for sid in session_ids]
            for future in as_completed(futures):
                pass
        
        elapsed = time.time() - start_time
        
        logger.info(f"[STRESS TEST] Created {len(sessions_created)}/{NUM_SESSIONS} sessions in {elapsed:.2f}s")
        logger.info(f"[STRESS TEST] Store size: {len(self.fresh_store._store)} entries")
        logger.info(f"[STRESS TEST] Errors: {len(errors)}")
        
        self.assertEqual(len(errors), 0, f"Session creation errors: {errors[:5]}")
        self.assertEqual(len(sessions_created), NUM_SESSIONS)
        self.assertEqual(len(self.fresh_store._store), NUM_SESSIONS)
        
        logger.info("✅ PASSED: High concurrency session creation (1000 users)")


class TestTTLExpiration(unittest.TestCase):
    """Test TTL expiration behavior."""
    
    def setUp(self):
        self.fresh_store, self.original_store, self.buffer_module = create_fresh_store()
        from nodes.memory.buffer_memory import MemoryManager
        self.memory_manager = MemoryManager
    
    def tearDown(self):
        restore_store(self.buffer_module, self.original_store)
    
    def test_ttl_expiration_basic(self):
        """Verify basic TTL expiration with short TTL."""
        session_id = "ttl-test-basic"
        messages = create_conversation(2)
        
        # Save with 1 second TTL
        self.memory_manager.save(session_id, messages, ttl_seconds=1)
        
        # Verify immediately accessible
        loaded = self.memory_manager.load(session_id, context_window=5)
        self.assertGreater(len(loaded), 0, "Session should be accessible immediately")
        
        # Wait for TTL to expire
        time.sleep(1.5)
        
        # Trigger cleanup
        self.fresh_store._purge_expired()
        
        # Verify expired
        loaded_after = self.memory_manager.load(session_id, context_window=5)
        self.assertEqual(len(loaded_after), 0, "Session should be expired and removed")
        
        logger.info("✅ PASSED: Basic TTL expiration")
    
    def test_ttl_expiration_mixed_sessions(self):
        """Test TTL expiration with mix of expired and active sessions."""
        NUM_EXPIRED = 100
        NUM_ACTIVE = 100
        
        # Create sessions that will expire
        expired_ids = [f"expire-{i}" for i in range(NUM_EXPIRED)]
        for sid in expired_ids:
            self.memory_manager.save(sid, create_conversation(1), ttl_seconds=1)
        
        # Create sessions that will remain active
        active_ids = [f"active-{i}" for i in range(NUM_ACTIVE)]
        for sid in active_ids:
            self.memory_manager.save(sid, create_conversation(1), ttl_seconds=3600)
        
        initial_count = len(self.fresh_store._store)
        logger.info(f"[TTL TEST] Initial store size: {initial_count}")
        
        # Wait for expired sessions to exceed TTL
        time.sleep(1.5)
        
        # Trigger cleanup
        self.fresh_store._purge_expired()
        
        final_count = len(self.fresh_store._store)
        logger.info(f"[TTL TEST] Final store size: {final_count}")
        logger.info(f"[TTL TEST] Purged: {initial_count - final_count} sessions")
        
        # Verify expired sessions are gone
        for sid in expired_ids:
            loaded = self.memory_manager.load(sid, context_window=5)
            self.assertEqual(len(loaded), 0, f"Expired session {sid} should be removed")
        
        # Verify active sessions remain
        for sid in active_ids:
            loaded = self.memory_manager.load(sid, context_window=5)
            self.assertGreater(len(loaded), 0, f"Active session {sid} should remain")
        
        self.assertEqual(final_count, NUM_ACTIVE)
        
        logger.info("✅ PASSED: Mixed TTL expiration")


class TestContextWindowOverflow(unittest.TestCase):
    """Test context window truncation."""
    
    def setUp(self):
        self.fresh_store, self.original_store, self.buffer_module = create_fresh_store()
        from nodes.memory.buffer_memory import MemoryManager
        self.memory_manager = MemoryManager
    
    def tearDown(self):
        restore_store(self.buffer_module, self.original_store)
    
    def test_context_window_truncation(self):
        """Verify context window truncates messages correctly."""
        session_id = "window-test"
        context_window = 3  # 3 turns = ~12 messages max
        
        # Create conversation with 10 turns (way more than window)
        messages = create_conversation(10)
        
        # Save with context window
        self.memory_manager.save(
            session_id, 
            messages, 
            ttl_seconds=3600,
            context_window=context_window
        )
        
        # Load and verify
        loaded = self.memory_manager.load(session_id, context_window=context_window)
        
        # Count non-system messages
        non_system = [m for m in loaded if m.get("role") != "system"]
        system = [m for m in loaded if m.get("role") == "system"]
        
        logger.info(f"[WINDOW TEST] Loaded {len(loaded)} messages ({len(system)} system, {len(non_system)} conversation)")
        
        # Verify system messages preserved
        self.assertEqual(len(system), 1, "System message should be preserved")
        
        # Verify conversation truncated (window * 4 max)
        max_expected = context_window * 4
        self.assertLessEqual(len(non_system), max_expected)
        
        logger.info("✅ PASSED: Context window truncation")
    
    def test_800_message_hard_cap(self):
        """Verify the 800 message hard cap in _store.set()."""
        session_id = "hard-cap-test"
        
        # Create way more than 800 messages
        messages = []
        for i in range(500):  # 500 turns = 1000+ messages
            messages.append({"role": "user", "content": f"Message {i}"})
            messages.append({"role": "assistant", "content": f"Response {i}"})
        
        logger.info(f"[HARD CAP TEST] Attempting to save {len(messages)} messages")
        
        # Save without context window (tests hard cap)
        self.memory_manager.save(session_id, messages, ttl_seconds=3600)
        
        # Verify stored count
        key = self.memory_manager._key(session_id)
        stored = self.fresh_store._store.get(key)
        
        stored_count = len(stored.messages) if stored else 0
        logger.info(f"[HARD CAP TEST] Stored: {stored_count} messages")
        
        self.assertLessEqual(stored_count, 800, f"Hard cap should limit to 800, got {stored_count}")
        
        logger.info("✅ PASSED: 800 message hard cap")


class TestMemoryLeakDetection(unittest.TestCase):
    """Test memory leak detection."""
    
    def setUp(self):
        self.fresh_store, self.original_store, self.buffer_module = create_fresh_store()
        from nodes.memory.buffer_memory import MemoryManager
        self.memory_manager = MemoryManager
    
    def tearDown(self):
        restore_store(self.buffer_module, self.original_store)
    
    def test_memory_stability_over_iterations(self):
        """Run multiple create/expire cycles and verify memory stability."""
        ITERATIONS = 5
        SESSIONS_PER_ITERATION = 50
        
        memory_samples = []
        
        for iteration in range(ITERATIONS):
            # Create sessions with short TTL
            for i in range(SESSIONS_PER_ITERATION):
                session_id = f"leak-test-{iteration}-{i}"
                self.memory_manager.save(
                    session_id,
                    create_conversation(3),
                    ttl_seconds=1
                )
            
            # Wait for expiration
            time.sleep(1.2)
            
            # Force cleanup
            self.fresh_store._purge_expired()
            
            # Force garbage collection
            gc.collect()
            
            # Sample store size
            store_size = len(self.fresh_store._store)
            memory_samples.append(store_size)
            
            logger.info(f"[LEAK TEST] Iteration {iteration+1}: Store size = {store_size}")
        
        # Verify store size returns to zero after each iteration
        self.assertTrue(all(s == 0 for s in memory_samples), f"Store should be empty after cleanup: {memory_samples}")
        
        logger.info("✅ PASSED: Memory stability over iterations")


class TestConcurrentReadWrite(unittest.TestCase):
    """Test concurrent read/write operations."""
    
    def setUp(self):
        self.fresh_store, self.original_store, self.buffer_module = create_fresh_store()
        from nodes.memory.buffer_memory import MemoryManager
        self.memory_manager = MemoryManager
    
    def tearDown(self):
        restore_store(self.buffer_module, self.original_store)
    
    def test_concurrent_read_write_same_session(self):
        """Multiple threads reading and writing to same session."""
        session_id = "concurrent-rw-test"
        NUM_OPERATIONS = 200
        NUM_THREADS = 20
        
        # Initialize session
        self.memory_manager.save(session_id, create_conversation(1), ttl_seconds=3600)
        
        read_counts = []
        write_counts = []
        errors = []
        lock = threading.Lock()
        
        def read_operation():
            try:
                loaded = self.memory_manager.load(session_id, context_window=10)
                with lock:
                    read_counts.append(len(loaded))
            except Exception as e:
                with lock:
                    errors.append(f"Read error: {e}")
        
        def write_operation(msg_num: int):
            try:
                existing = self.memory_manager.load(session_id, context_window=10)
                existing.append({"role": "user", "content": f"Concurrent message {msg_num}"})
                self.memory_manager.save(session_id, existing, ttl_seconds=3600)
                with lock:
                    write_counts.append(msg_num)
            except Exception as e:
                with lock:
                    errors.append(f"Write error: {e}")
        
        # Mix of read and write operations
        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            futures = []
            for i in range(NUM_OPERATIONS):
                if i % 2 == 0:
                    futures.append(executor.submit(read_operation))
                else:
                    futures.append(executor.submit(write_operation, i))
            
            for future in as_completed(futures):
                pass
        
        logger.info(f"[CONCURRENT RW] Reads: {len(read_counts)}, Writes: {len(write_counts)}")
        logger.info(f"[CONCURRENT RW] Errors: {len(errors)}")
        
        self.assertEqual(len(errors), 0, f"Concurrent operations had errors: {errors[:5]}")
        
        logger.info("✅ PASSED: Concurrent read/write operations")


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def setUp(self):
        self.fresh_store, self.original_store, self.buffer_module = create_fresh_store()
        from nodes.memory.buffer_memory import MemoryManager
        self.memory_manager = MemoryManager
    
    def tearDown(self):
        restore_store(self.buffer_module, self.original_store)
    
    def test_empty_session_load(self):
        """Load from non-existent session returns empty list."""
        loaded = self.memory_manager.load("non-existent-session", context_window=5)
        self.assertEqual(loaded, [], "Non-existent session should return empty list")
        logger.info("✅ PASSED: Empty session load")
    
    def test_zero_context_window(self):
        """Zero context window should return only system messages."""
        session_id = "zero-window-test"
        messages = create_conversation(5)
        self.memory_manager.save(session_id, messages, ttl_seconds=3600)
        
        loaded = self.memory_manager.load(session_id, context_window=0)
        
        # Should only have system message
        self.assertTrue(all(m.get("role") == "system" for m in loaded), "Should only return system messages")
        logger.info("✅ PASSED: Zero context window")
    
    def test_zero_ttl(self):
        """Zero TTL means no expiration."""
        session_id = "zero-ttl-test"
        self.memory_manager.save(session_id, create_conversation(1), ttl_seconds=0)
        
        # Verify entry has expires_at = 0 (no expiration)
        key = self.memory_manager._key(session_id)
        entry = self.fresh_store._store.get(key)
        
        self.assertIsNotNone(entry, "Entry should exist")
        self.assertEqual(entry.expires_at, 0, "expires_at should be 0 for no expiration")
        
        logger.info("✅ PASSED: Zero TTL (no expiration)")
    
    def test_special_characters_in_session_id(self):
        """Session IDs with special characters should work."""
        special_ids = [
            "user:123:session:456",
            "email@example.com",
            "path/to/session",
            "session with spaces",
        ]
        
        for sid in special_ids:
            self.memory_manager.save(sid, create_conversation(1), ttl_seconds=3600)
            loaded = self.memory_manager.load(sid, context_window=5)
            self.assertGreater(len(loaded), 0, f"Session '{sid}' should be accessible")
        
        logger.info("✅ PASSED: Special characters in session ID")


class TestCleanupPerformance(unittest.TestCase):
    """Test cleanup performance."""
    
    def setUp(self):
        self.fresh_store, self.original_store, self.buffer_module = create_fresh_store()
        from nodes.memory.buffer_memory import MemoryManager
        self.memory_manager = MemoryManager
    
    def tearDown(self):
        restore_store(self.buffer_module, self.original_store)
    
    def test_purge_expired_performance(self):
        """Verify _purge_expired is fast even with many sessions."""
        NUM_SESSIONS = 1000
        
        # Create sessions
        for i in range(NUM_SESSIONS):
            self.memory_manager.save(f"perf-test-{i}", create_conversation(2), ttl_seconds=3600)
        
        # Time purge operation
        start = time.time()
        self.fresh_store._purge_expired()
        elapsed = time.time() - start
        
        logger.info(f"[PURGE PERF] Scanned {NUM_SESSIONS} sessions in {elapsed:.4f}s")
        
        # Should be very fast (< 500ms for 1000 sessions)
        self.assertLess(elapsed, 0.5, f"Purge too slow: {elapsed}s")
        
        logger.info("✅ PASSED: Purge performance acceptable")


# ═══════════════════════════════════════════════════════════════════════════════
#                              MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def run_tests():
    """Run all test suites."""
    print("\n" + "="*80)
    print("BUFFER MEMORY STRESS TEST SUITE")
    print("="*80 + "\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestHighConcurrencySessionCreation,
        TestTTLExpiration,
        TestContextWindowOverflow,
        TestMemoryLeakDetection,
        TestConcurrentReadWrite,
        TestEdgeCases,
        TestCleanupPerformance,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED!")
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}: {traceback[:100]}...")
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}: {traceback[:100]}...")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
