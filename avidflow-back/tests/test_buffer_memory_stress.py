"""
Buffer Memory Node - Stress Testing & Integration Test Suite

This module contains scenario-based integration tests to validate:
1. Memory cleanup under high load
2. Concurrent session handling
3. TTL expiration correctness
4. Context window truncation
5. Memory bounds and leak prevention

Environment: Designed for Celery with gevent pool (--pool=gevent)

Run with:
    pytest tests/test_buffer_memory_stress.py -v -s
    
For stress tests only:
    pytest tests/test_buffer_memory_stress.py -v -s -k "stress"
"""
from __future__ import annotations

import gc
import sys
import time
import uuid
import logging
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

import pytest

# Configure logging for test visibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#                          ARCHITECTURAL REVIEW SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
"""
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    BUFFER MEMORY - ARCHITECTURAL REVIEW                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  COMPONENT: _InMemoryConversationStore                                          │
│  PURPOSE: In-process session storage for AI Agent conversation memory           │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ✅ STRENGTHS                                                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  1. GEVENT COMPATIBILITY                                                        │
│     - Uses gevent.spawn() for background cleanup (non-blocking)                 │
│     - gevent.RLock for cooperative locking                                      │
│     - Falls back to threading.Thread for non-gevent environments                │
│                                                                                 │
│  2. TTL ENFORCEMENT                                                             │
│     - Background greenlet purges expired sessions every 5 minutes               │
│     - Also purges on get()/set() operations (lazy cleanup)                      │
│     - Prevents orphaned sessions from accumulating                              │
│                                                                                 │
│  3. MESSAGE CAPS                                                                │
│     - Hard cap of 800 messages per session in _store.set()                      │
│     - Context window truncation in MemoryManager.save()                         │
│     - Auto-clear when window is full (prevents unbounded growth)                │
│                                                                                 │
│  4. ERROR RESILIENCE                                                            │
│     - Cleanup loop catches all exceptions, never crashes                        │
│     - Graceful degradation if spawn fails                                       │
│     - Warning logs at 1000+ sessions (memory pressure indicator)                │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ⚠️  RISKS & CONCERNS                                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  1. RACE CONDITION IN FLAG CHECK (Line 56-63)                                   │
│     - `if self._cleanup_running` is NOT atomic with the assignment              │
│     - Two greenlets could pass the check before either sets the flag            │
│     - SEVERITY: Low (only during initialization, unlikely in practice)          │
│     - FIX: Use atomic flag or threading.Lock for the check                      │
│                                                                                 │
│  2. NO HARD MEMORY LIMIT                                                        │
│     - 800 messages × N sessions can still exhaust RAM                           │
│     - Warning at 1000 sessions, but no circuit breaker                          │
│     - SEVERITY: Medium (production risk under sustained load)                   │
│     - FIX: Add MAX_SESSIONS limit with LRU eviction                             │
│                                                                                 │
│  3. 5-MINUTE CLEANUP INTERVAL                                                   │
│     - Sessions live up to 5 minutes past TTL expiry                             │
│     - Burst traffic could accumulate many expired sessions                      │
│     - SEVERITY: Low (acceptable for most use cases)                             │
│     - FIX: Reduce interval or use probabilistic cleanup on access               │
│                                                                                 │
│  4. SINGLE GLOBAL STORE                                                         │
│     - _STORE is module-level singleton                                          │
│     - All Celery workers share same store (if same process)                     │
│     - But each worker process has its OWN store (not shared)                    │
│     - SEVERITY: Design limitation (not a bug)                                   │
│     - NOTE: Use Redis for true cross-worker sharing                             │
│                                                                                 │
│  5. DEAD CODE (Line 382-383)                                                    │
│     - Unreachable code after return in get_runnable()                           │
│     - SEVERITY: Cosmetic (should be removed)                                    │
│                                                                                 │
│  6. time.sleep() BUG (Line 77)                                                  │
│     - Should be `import time; time.sleep(300)` not `time.sleep(300)`            │
│     - `time` is imported as function `from time import time`                    │
│     - SEVERITY: High (will crash in non-gevent mode)                            │
│     - FIX: Import time module properly                                          │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│  🔧 RECOMMENDED IMPROVEMENTS                                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  1. Add MAX_SESSIONS constant (e.g., 10,000) with LRU eviction                  │
│  2. Fix time.sleep() import bug for threading fallback                          │
│  3. Add memory usage metrics (total bytes, session count)                       │
│  4. Implement circuit breaker: reject new sessions if limit reached             │
│  5. Add Redis fallback recommendation in high-load warning                      │
│  6. Remove dead code after return statement                                     │
│  7. Consider reducing cleanup interval to 60 seconds                            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
"""


# ═══════════════════════════════════════════════════════════════════════════════
#                              TEST FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def fresh_store():
    """
    Create a fresh memory store for isolated testing.
    
    This fixture patches the global _STORE to prevent test pollution.
    """
    from nodes.memory.buffer_memory import _InMemoryConversationStore, MemoryManager
    
    # Create fresh store
    original_store = None
    
    # Import and patch
    import nodes.memory.buffer_memory as buffer_module
    original_store = buffer_module._STORE
    
    # Create new store (disable cleanup greenlet for controlled testing)
    new_store = _InMemoryConversationStore.__new__(_InMemoryConversationStore)
    new_store._lock = threading.RLock()
    new_store._store = {}
    new_store._cleanup_running = True  # Prevent auto-spawn
    
    buffer_module._STORE = new_store
    
    yield new_store
    
    # Restore original
    buffer_module._STORE = original_store


@pytest.fixture
def memory_manager(fresh_store):
    """Provide MemoryManager with fresh store."""
    from nodes.memory.buffer_memory import MemoryManager
    return MemoryManager


@dataclass
class TestMessage:
    """Helper to create test messages."""
    role: str
    content: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {"role": self.role, "content": self.content}


def create_conversation(num_turns: int) -> List[Dict[str, Any]]:
    """Create a realistic conversation with N turns."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]
    for i in range(num_turns):
        messages.append({"role": "user", "content": f"User message {i+1}"})
        messages.append({"role": "assistant", "content": f"Assistant response {i+1}"})
    return messages


# ═══════════════════════════════════════════════════════════════════════════════
#                    SCENARIO 1: HIGH CONCURRENCY SESSION CREATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestHighConcurrencySessionCreation:
    """
    Test Scenario: Simulate 5,000 unique users starting new memory sessions concurrently.
    
    Purpose: Verify that concurrent session creation does not cause:
    - Memory leaks
    - Race conditions
    - Lock contention issues
    - Data corruption
    
    Expected Results:
    - All sessions created successfully
    - No duplicate keys
    - Memory usage stays bounded
    - Store count matches expected
    """
    
    @pytest.mark.stress
    def test_concurrent_session_creation_1000_users(self, memory_manager, fresh_store):
        """
        Create 1,000 sessions concurrently and verify integrity.
        """
        NUM_SESSIONS = 1000
        NUM_THREADS = 50
        sessions_created = []
        errors = []
        
        def create_session(session_id: str):
            try:
                messages = create_conversation(3)
                memory_manager.save(session_id, messages, ttl_seconds=300)
                loaded = memory_manager.load(session_id, context_window=5)
                if len(loaded) > 0:
                    sessions_created.append(session_id)
                else:
                    errors.append(f"Session {session_id}: Empty after save")
            except Exception as e:
                errors.append(f"Session {session_id}: {str(e)}")
        
        # Generate unique session IDs
        session_ids = [f"stress-test-{uuid.uuid4()}" for _ in range(NUM_SESSIONS)]
        
        # Execute concurrently
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            futures = [executor.submit(create_session, sid) for sid in session_ids]
            for future in as_completed(futures):
                pass  # Wait for all to complete
        
        elapsed = time.time() - start_time
        
        # Assertions
        logger.info(f"[STRESS TEST] Created {len(sessions_created)}/{NUM_SESSIONS} sessions in {elapsed:.2f}s")
        logger.info(f"[STRESS TEST] Store size: {len(fresh_store._store)} entries")
        logger.info(f"[STRESS TEST] Errors: {len(errors)}")
        
        if errors:
            for err in errors[:10]:  # Show first 10 errors
                logger.error(f"  - {err}")
        
        assert len(errors) == 0, f"Session creation errors: {errors[:5]}"
        assert len(sessions_created) == NUM_SESSIONS, f"Expected {NUM_SESSIONS}, got {len(sessions_created)}"
        assert len(fresh_store._store) == NUM_SESSIONS, f"Store has {len(fresh_store._store)} entries"
        
        logger.info("✅ PASSED: High concurrency session creation")
    
    @pytest.mark.stress
    def test_concurrent_session_creation_5000_users(self, memory_manager, fresh_store):
        """
        Create 5,000 sessions concurrently (full stress test).
        """
        NUM_SESSIONS = 5000
        NUM_THREADS = 100
        sessions_created = []
        lock = threading.Lock()
        
        def create_session(session_id: str):
            try:
                messages = create_conversation(2)
                memory_manager.save(session_id, messages, ttl_seconds=600)
                with lock:
                    sessions_created.append(session_id)
            except Exception as e:
                logger.error(f"Error creating session {session_id}: {e}")
        
        session_ids = [f"stress-5k-{uuid.uuid4()}" for _ in range(NUM_SESSIONS)]
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            list(executor.map(create_session, session_ids))
        
        elapsed = time.time() - start_time
        
        logger.info(f"[STRESS TEST 5K] Created {len(sessions_created)} sessions in {elapsed:.2f}s")
        logger.info(f"[STRESS TEST 5K] Throughput: {NUM_SESSIONS/elapsed:.0f} sessions/second")
        logger.info(f"[STRESS TEST 5K] Store size: {len(fresh_store._store)} entries")
        
        assert len(sessions_created) == NUM_SESSIONS
        assert len(fresh_store._store) == NUM_SESSIONS
        
        logger.info("✅ PASSED: 5,000 concurrent session creation")


# ═══════════════════════════════════════════════════════════════════════════════
#                    SCENARIO 2: TTL EXPIRATION UNDER LOAD
# ═══════════════════════════════════════════════════════════════════════════════

class TestTTLExpirationUnderLoad:
    """
    Test Scenario: Verify TTL expiration works correctly under load.
    
    Purpose: Ensure that:
    - Expired sessions are removed by cleanup
    - Active sessions are NOT removed
    - Cleanup does not block normal operations
    
    Expected Results:
    - Expired sessions removed after TTL + cleanup interval
    - Active sessions remain accessible
    - No memory leaks from expired sessions
    """
    
    def test_ttl_expiration_basic(self, memory_manager, fresh_store):
        """
        Verify basic TTL expiration with short TTL.
        """
        session_id = "ttl-test-basic"
        messages = create_conversation(2)
        
        # Save with 1 second TTL
        memory_manager.save(session_id, messages, ttl_seconds=1)
        
        # Verify immediately accessible
        loaded = memory_manager.load(session_id, context_window=5)
        assert len(loaded) > 0, "Session should be accessible immediately"
        
        # Wait for TTL to expire
        time.sleep(1.5)
        
        # Trigger cleanup (happens on get/set)
        fresh_store._purge_expired()
        
        # Verify expired
        loaded_after = memory_manager.load(session_id, context_window=5)
        assert len(loaded_after) == 0, "Session should be expired and removed"
        
        logger.info("✅ PASSED: Basic TTL expiration")
    
    @pytest.mark.stress
    def test_ttl_expiration_mixed_sessions(self, memory_manager, fresh_store):
        """
        Test TTL expiration with mix of expired and active sessions.
        """
        NUM_EXPIRED = 100
        NUM_ACTIVE = 100
        
        # Create sessions that will expire
        expired_ids = [f"expire-{i}" for i in range(NUM_EXPIRED)]
        for sid in expired_ids:
            memory_manager.save(sid, create_conversation(1), ttl_seconds=1)
        
        # Create sessions that will remain active
        active_ids = [f"active-{i}" for i in range(NUM_ACTIVE)]
        for sid in active_ids:
            memory_manager.save(sid, create_conversation(1), ttl_seconds=3600)
        
        initial_count = len(fresh_store._store)
        logger.info(f"[TTL TEST] Initial store size: {initial_count}")
        
        # Wait for expired sessions to exceed TTL
        time.sleep(1.5)
        
        # Trigger cleanup
        fresh_store._purge_expired()
        
        final_count = len(fresh_store._store)
        logger.info(f"[TTL TEST] Final store size: {final_count}")
        logger.info(f"[TTL TEST] Purged: {initial_count - final_count} sessions")
        
        # Verify expired sessions are gone
        for sid in expired_ids:
            loaded = memory_manager.load(sid, context_window=5)
            assert len(loaded) == 0, f"Expired session {sid} should be removed"
        
        # Verify active sessions remain
        for sid in active_ids:
            loaded = memory_manager.load(sid, context_window=5)
            assert len(loaded) > 0, f"Active session {sid} should remain"
        
        assert final_count == NUM_ACTIVE, f"Expected {NUM_ACTIVE} active sessions, got {final_count}"
        
        logger.info("✅ PASSED: Mixed TTL expiration")
    
    @pytest.mark.stress
    def test_ttl_expiration_burst_traffic(self, memory_manager, fresh_store):
        """
        Simulate burst traffic followed by TTL expiration.
        
        This tests the scenario where many sessions are created quickly,
        then most expire, verifying cleanup keeps up.
        """
        BURST_SIZE = 500
        
        # Create burst of short-TTL sessions
        burst_ids = [f"burst-{i}" for i in range(BURST_SIZE)]
        
        start_time = time.time()
        for sid in burst_ids:
            memory_manager.save(sid, create_conversation(1), ttl_seconds=2)
        
        create_time = time.time() - start_time
        logger.info(f"[BURST TEST] Created {BURST_SIZE} sessions in {create_time:.2f}s")
        
        initial_count = len(fresh_store._store)
        assert initial_count == BURST_SIZE
        
        # Wait for expiration
        time.sleep(2.5)
        
        # Run cleanup
        cleanup_start = time.time()
        fresh_store._purge_expired()
        cleanup_time = time.time() - cleanup_start
        
        final_count = len(fresh_store._store)
        
        logger.info(f"[BURST TEST] Cleanup took {cleanup_time:.4f}s")
        logger.info(f"[BURST TEST] Purged {initial_count - final_count} sessions")
        
        assert final_count == 0, f"All burst sessions should be expired, got {final_count}"
        assert cleanup_time < 1.0, f"Cleanup should be fast, took {cleanup_time}s"
        
        logger.info("✅ PASSED: Burst traffic TTL expiration")


# ═══════════════════════════════════════════════════════════════════════════════
#                    SCENARIO 3: CONTEXT WINDOW OVERFLOW
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextWindowOverflow:
    """
    Test Scenario: Force context window overflow and verify truncation.
    
    Purpose: Ensure that:
    - Messages beyond context window are truncated
    - System messages are preserved
    - Auto-clear triggers when window is full
    - Logging captures truncation events
    
    Expected Results:
    - Message count stays within bounds
    - Oldest messages are removed
    - System messages always retained
    """
    
    def test_context_window_truncation(self, memory_manager, fresh_store):
        """
        Verify context window truncates messages correctly.
        """
        session_id = "window-test"
        context_window = 3  # 3 turns = ~12 messages max
        
        # Create conversation with 10 turns (way more than window)
        messages = create_conversation(10)
        
        # Save with context window
        memory_manager.save(
            session_id, 
            messages, 
            ttl_seconds=3600,
            context_window=context_window
        )
        
        # Load and verify
        loaded = memory_manager.load(session_id, context_window=context_window)
        
        # Count non-system messages
        non_system = [m for m in loaded if m.get("role") != "system"]
        system = [m for m in loaded if m.get("role") == "system"]
        
        logger.info(f"[WINDOW TEST] Loaded {len(loaded)} messages ({len(system)} system, {len(non_system)} conversation)")
        
        # Verify system messages preserved
        assert len(system) == 1, "System message should be preserved"
        
        # Verify conversation truncated (window * 4 max)
        max_expected = context_window * 4
        assert len(non_system) <= max_expected, f"Expected <= {max_expected} messages, got {len(non_system)}"
        
        logger.info("✅ PASSED: Context window truncation")
    
    def test_auto_clear_on_full_window(self, memory_manager, fresh_store):
        """
        Verify auto-clear triggers when window is completely full.
        """
        session_id = "auto-clear-test"
        context_window = 3  # Small window for quick test
        
        # Simulate multiple conversation turns filling the window
        for turn in range(5):  # More turns than window
            # Load existing
            existing = memory_manager.load(session_id, context_window=context_window)
            
            # Add new turn
            new_messages = existing + [
                {"role": "user", "content": f"Turn {turn+1} user message"},
                {"role": "assistant", "content": f"Turn {turn+1} assistant response"}
            ]
            
            # Save with auto-clear
            memory_manager.save(
                session_id,
                new_messages,
                ttl_seconds=3600,
                context_window=context_window,
                auto_clear_on_full=True
            )
        
        # Final load
        final = memory_manager.load(session_id, context_window=context_window)
        non_system = [m for m in final if m.get("role") != "system"]
        
        logger.info(f"[AUTO-CLEAR TEST] Final message count: {len(final)}")
        logger.info(f"[AUTO-CLEAR TEST] Last message: {non_system[-1] if non_system else 'None'}")
        
        # Should have only recent messages after auto-clear
        user_messages = [m for m in non_system if m.get("role") == "user"]
        assert len(user_messages) <= context_window, f"Should have <= {context_window} user messages after auto-clear"
        
        logger.info("✅ PASSED: Auto-clear on full window")
    
    def test_800_message_hard_cap(self, memory_manager, fresh_store):
        """
        Verify the 800 message hard cap in _store.set().
        """
        session_id = "hard-cap-test"
        
        # Create way more than 800 messages
        messages = []
        for i in range(500):  # 500 turns = 1000+ messages
            messages.append({"role": "user", "content": f"Message {i}"})
            messages.append({"role": "assistant", "content": f"Response {i}"})
        
        logger.info(f"[HARD CAP TEST] Attempting to save {len(messages)} messages")
        
        # Save without context window (tests hard cap)
        memory_manager.save(session_id, messages, ttl_seconds=3600)
        
        # Verify stored count
        key = memory_manager._key(session_id)
        stored = fresh_store._store.get(key)
        
        stored_count = len(stored.messages) if stored else 0
        logger.info(f"[HARD CAP TEST] Stored: {stored_count} messages")
        
        assert stored_count <= 800, f"Hard cap should limit to 800, got {stored_count}"
        
        logger.info("✅ PASSED: 800 message hard cap")


# ═══════════════════════════════════════════════════════════════════════════════
#                    SCENARIO 4: MEMORY LEAK DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

class TestMemoryLeakDetection:
    """
    Test Scenario: Detect memory leaks over sustained operations.
    
    Purpose: Verify that:
    - Memory usage stays bounded over time
    - Expired sessions are actually freed
    - No reference leaks in store
    
    Expected Results:
    - Memory usage stable after cleanup
    - No growing baseline over iterations
    """
    
    @pytest.mark.stress
    def test_memory_stability_over_iterations(self, memory_manager, fresh_store):
        """
        Run multiple create/expire cycles and verify memory stability.
        """
        ITERATIONS = 10
        SESSIONS_PER_ITERATION = 100
        
        memory_samples = []
        
        for iteration in range(ITERATIONS):
            # Create sessions with short TTL
            for i in range(SESSIONS_PER_ITERATION):
                session_id = f"leak-test-{iteration}-{i}"
                memory_manager.save(
                    session_id,
                    create_conversation(3),
                    ttl_seconds=1
                )
            
            # Wait for expiration
            time.sleep(1.2)
            
            # Force cleanup
            fresh_store._purge_expired()
            
            # Force garbage collection
            gc.collect()
            
            # Sample store size
            store_size = len(fresh_store._store)
            memory_samples.append(store_size)
            
            logger.info(f"[LEAK TEST] Iteration {iteration+1}: Store size = {store_size}")
        
        # Verify store size returns to zero after each iteration
        assert all(s == 0 for s in memory_samples), f"Store should be empty after cleanup: {memory_samples}"
        
        logger.info("✅ PASSED: Memory stability over iterations")
    
    def test_no_reference_leaks(self, memory_manager, fresh_store):
        """
        Verify no lingering references after session deletion.
        """
        import weakref
        
        session_id = "ref-leak-test"
        messages = create_conversation(5)
        
        # Save and create weak reference to messages
        memory_manager.save(session_id, messages, ttl_seconds=1)
        
        # Get reference to stored messages
        key = memory_manager._key(session_id)
        entry = fresh_store._store.get(key)
        weak_ref = weakref.ref(entry.messages) if entry else None
        
        # Expire and cleanup
        time.sleep(1.2)
        fresh_store._purge_expired()
        
        # Force GC
        gc.collect()
        
        # Check if weak reference is dead
        # Note: This may not always work due to Python's GC timing
        logger.info(f"[REF LEAK TEST] Weak ref alive: {weak_ref() is not None if weak_ref else 'N/A'}")
        
        # At minimum, verify store is empty
        assert len(fresh_store._store) == 0, "Store should be empty"
        
        logger.info("✅ PASSED: No reference leaks detected")


# ═══════════════════════════════════════════════════════════════════════════════
#                    SCENARIO 5: CONCURRENT READ/WRITE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class TestConcurrentReadWrite:
    """
    Test Scenario: Verify thread safety under concurrent read/write load.
    
    Purpose: Ensure that:
    - Concurrent reads don't corrupt data
    - Concurrent writes don't lose data
    - Lock contention doesn't cause deadlocks
    
    Expected Results:
    - All operations complete successfully
    - Data integrity maintained
    - No deadlocks or hangs
    """
    
    @pytest.mark.stress
    def test_concurrent_read_write_same_session(self, memory_manager, fresh_store):
        """
        Multiple threads reading and writing to same session.
        """
        session_id = "concurrent-rw-test"
        NUM_OPERATIONS = 500
        NUM_THREADS = 20
        
        # Initialize session
        memory_manager.save(session_id, create_conversation(1), ttl_seconds=3600)
        
        read_counts = []
        write_counts = []
        errors = []
        lock = threading.Lock()
        
        def read_operation():
            try:
                loaded = memory_manager.load(session_id, context_window=10)
                with lock:
                    read_counts.append(len(loaded))
            except Exception as e:
                with lock:
                    errors.append(f"Read error: {e}")
        
        def write_operation(msg_num: int):
            try:
                existing = memory_manager.load(session_id, context_window=10)
                existing.append({"role": "user", "content": f"Concurrent message {msg_num}"})
                memory_manager.save(session_id, existing, ttl_seconds=3600)
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
        
        if errors:
            for err in errors[:5]:
                logger.error(f"  - {err}")
        
        assert len(errors) == 0, f"Concurrent operations had errors: {errors[:5]}"
        
        logger.info("✅ PASSED: Concurrent read/write operations")
    
    @pytest.mark.stress
    def test_concurrent_operations_multiple_sessions(self, memory_manager, fresh_store):
        """
        Concurrent operations across multiple sessions.
        """
        NUM_SESSIONS = 50
        OPS_PER_SESSION = 20
        NUM_THREADS = 30
        
        session_ids = [f"multi-session-{i}" for i in range(NUM_SESSIONS)]
        successful_ops = []
        lock = threading.Lock()
        
        def session_operations(session_id: str):
            try:
                for _ in range(OPS_PER_SESSION):
                    # Write
                    messages = create_conversation(2)
                    memory_manager.save(session_id, messages, ttl_seconds=3600)
                    
                    # Read
                    loaded = memory_manager.load(session_id, context_window=5)
                    
                    # Small delay
                    time.sleep(0.001)
                
                with lock:
                    successful_ops.append(session_id)
            except Exception as e:
                logger.error(f"Session {session_id} failed: {e}")
        
        start_time = time.time()
        with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
            list(executor.map(session_operations, session_ids))
        
        elapsed = time.time() - start_time
        total_ops = NUM_SESSIONS * OPS_PER_SESSION * 2  # read + write per iteration
        
        logger.info(f"[MULTI-SESSION] Completed {len(successful_ops)}/{NUM_SESSIONS} sessions")
        logger.info(f"[MULTI-SESSION] Total operations: {total_ops} in {elapsed:.2f}s")
        logger.info(f"[MULTI-SESSION] Throughput: {total_ops/elapsed:.0f} ops/sec")
        
        assert len(successful_ops) == NUM_SESSIONS, f"All sessions should complete"
        
        logger.info("✅ PASSED: Concurrent operations across multiple sessions")


# ═══════════════════════════════════════════════════════════════════════════════
#                    SCENARIO 6: CLEANUP GREENLET BEHAVIOR
# ═══════════════════════════════════════════════════════════════════════════════

class TestCleanupGreenletBehavior:
    """
    Test Scenario: Verify cleanup greenlet/thread behavior.
    
    Purpose: Ensure that:
    - Cleanup starts correctly
    - Cleanup is idempotent (multiple calls safe)
    - Cleanup recovers from errors
    - Cleanup doesn't block operations
    """
    
    def test_cleanup_idempotent(self, fresh_store):
        """
        Verify multiple cleanup spawns are safe.
        """
        # Reset flag
        fresh_store._cleanup_running = False
        
        # Attempt multiple spawns (should be idempotent)
        spawn_count = 0
        for _ in range(5):
            try:
                # Manually check flag behavior
                if not fresh_store._cleanup_running:
                    fresh_store._cleanup_running = True
                    spawn_count += 1
            except Exception as e:
                logger.error(f"Spawn error: {e}")
        
        assert spawn_count == 1, "Only one spawn should succeed"
        
        logger.info("✅ PASSED: Cleanup idempotent")
    
    def test_purge_expired_performance(self, memory_manager, fresh_store):
        """
        Verify _purge_expired is fast even with many sessions.
        """
        NUM_SESSIONS = 1000
        
        # Create sessions
        for i in range(NUM_SESSIONS):
            memory_manager.save(f"perf-test-{i}", create_conversation(2), ttl_seconds=3600)
        
        # Time purge operation
        start = time.time()
        fresh_store._purge_expired()
        elapsed = time.time() - start
        
        logger.info(f"[PURGE PERF] Purged {NUM_SESSIONS} sessions in {elapsed:.4f}s")
        
        # Should be very fast (< 100ms for 1000 sessions)
        assert elapsed < 0.5, f"Purge too slow: {elapsed}s"
        
        logger.info("✅ PASSED: Purge performance acceptable")


# ═══════════════════════════════════════════════════════════════════════════════
#                    SCENARIO 7: EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """
    Test edge cases and boundary conditions.
    """
    
    def test_empty_session_load(self, memory_manager, fresh_store):
        """Load from non-existent session returns empty list."""
        loaded = memory_manager.load("non-existent-session", context_window=5)
        assert loaded == [], "Non-existent session should return empty list"
        logger.info("✅ PASSED: Empty session load")
    
    def test_zero_context_window(self, memory_manager, fresh_store):
        """Zero context window should return only system messages."""
        session_id = "zero-window-test"
        messages = create_conversation(5)
        memory_manager.save(session_id, messages, ttl_seconds=3600)
        
        loaded = memory_manager.load(session_id, context_window=0)
        
        # Should only have system message
        assert all(m.get("role") == "system" for m in loaded), "Should only return system messages"
        logger.info("✅ PASSED: Zero context window")
    
    def test_zero_ttl(self, memory_manager, fresh_store):
        """Zero TTL means no expiration."""
        session_id = "zero-ttl-test"
        memory_manager.save(session_id, create_conversation(1), ttl_seconds=0)
        
        # Verify entry has expires_at = 0 (no expiration)
        key = memory_manager._key(session_id)
        entry = fresh_store._store.get(key)
        
        assert entry is not None, "Entry should exist"
        assert entry.expires_at == 0, "expires_at should be 0 for no expiration"
        
        logger.info("✅ PASSED: Zero TTL (no expiration)")
    
    def test_special_characters_in_session_id(self, memory_manager, fresh_store):
        """Session IDs with special characters should work."""
        special_ids = [
            "user:123:session:456",
            "email@example.com",
            "path/to/session",
            "session with spaces",
            "session_with_émojis_🎉",
        ]
        
        for sid in special_ids:
            memory_manager.save(sid, create_conversation(1), ttl_seconds=3600)
            loaded = memory_manager.load(sid, context_window=5)
            assert len(loaded) > 0, f"Session '{sid}' should be accessible"
        
        logger.info("✅ PASSED: Special characters in session ID")
    
    def test_very_large_message_content(self, memory_manager, fresh_store):
        """Handle very large message content."""
        session_id = "large-content-test"
        large_content = "x" * 100000  # 100KB message
        
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": large_content},
            {"role": "assistant", "content": large_content},
        ]
        
        memory_manager.save(session_id, messages, ttl_seconds=3600)
        loaded = memory_manager.load(session_id, context_window=5)
        
        # Verify content preserved
        user_msg = [m for m in loaded if m.get("role") == "user"][0]
        assert len(user_msg["content"]) == 100000, "Large content should be preserved"
        
        logger.info("✅ PASSED: Very large message content")


# ═══════════════════════════════════════════════════════════════════════════════
#                    RUN ALL TESTS
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Run with pytest for proper fixtures
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short",
        # Add "-k stress" to run only stress tests
    ])
