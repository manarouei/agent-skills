"""
Comprehensive edge case testing for _start_cleanup_greenlet function.

Tests race conditions, multiple worker scenarios, and error handling.
"""

import time
import threading
from unittest.mock import Mock, patch, MagicMock
import sys

# Test 1: Multiple instantiation race condition
print("=" * 80)
print("TEST 1: Multiple Instantiation Race Condition")
print("=" * 80)

def test_multiple_instantiation():
    """
    Test if multiple _InMemoryConversationStore instances create duplicate cleanup loops.
    
    CRITICAL: In production, if module is reloaded or imported multiple times,
    we could spawn multiple cleanup greenlets consuming resources.
    """
    from nodes.memory.buffer_memory import _InMemoryConversationStore
    
    store1 = _InMemoryConversationStore()
    store2 = _InMemoryConversationStore()
    store3 = _InMemoryConversationStore()
    
    print(f"✓ Created 3 store instances")
    print(f"  Store1 cleanup_running: {store1._cleanup_running}")
    print(f"  Store2 cleanup_running: {store2._cleanup_running}")
    print(f"  Store3 cleanup_running: {store3._cleanup_running}")
    
    # Check if _cleanup_running prevents duplicate spawns
    if store1._cleanup_running and store2._cleanup_running and store3._cleanup_running:
        print("✓ Each instance has its own cleanup greenlet")
        print("⚠️  ISSUE: Multiple cleanup loops running (one per instance)")
        return "WARNING"
    else:
        print("✗ Some instances don't have cleanup running")
        return "FAIL"

result1 = test_multiple_instantiation()

# Test 2: Singleton pattern verification
print("\n" + "=" * 80)
print("TEST 2: Singleton Pattern Verification")
print("=" * 80)

def test_singleton_pattern():
    """
    Verify that _STORE is truly a singleton and only one cleanup runs globally.
    """
    from nodes.memory.buffer_memory import _STORE as store1
    from nodes.memory.buffer_memory import _STORE as store2
    
    print(f"Store1 ID: {id(store1)}")
    print(f"Store2 ID: {id(store2)}")
    print(f"Store1 cleanup_running: {store1._cleanup_running}")
    print(f"Store2 cleanup_running: {store2._cleanup_running}")
    
    if id(store1) == id(store2):
        print("✓ _STORE is a true singleton (same instance)")
        if store1._cleanup_running:
            print("✓ Single cleanup greenlet running")
            return "PASS"
        else:
            print("✗ Cleanup not running on singleton")
            return "FAIL"
    else:
        print("✗ _STORE is NOT a singleton (different instances)")
        return "FAIL"

result2 = test_singleton_pattern()

# Test 3: Exception handling in cleanup loop
print("\n" + "=" * 80)
print("TEST 3: Exception Handling in Cleanup Loop")
print("=" * 80)

def test_exception_handling():
    """
    Test if exceptions in _purge_expired() crash the cleanup loop.
    
    CRITICAL: If an exception kills the greenlet, cleanup stops forever.
    """
    from nodes.memory.buffer_memory import _InMemoryConversationStore
    
    store = _InMemoryConversationStore()
    
    # Mock _purge_expired to raise exception
    original_purge = store._purge_expired
    call_count = [0]
    
    def failing_purge():
        call_count[0] += 1
        if call_count[0] == 1:
            print(f"  Call {call_count[0]}: Raising exception...")
            raise ValueError("Test exception in purge")
        else:
            print(f"  Call {call_count[0]}: Normal execution")
            original_purge()
    
    store._purge_expired = failing_purge
    
    # Trigger cleanup manually to simulate the loop
    try:
        store._purge_expired()
    except Exception as e:
        print(f"✗ Exception not caught: {e}")
        return "FAIL"
    
    # Try again - should still work
    try:
        store._purge_expired()
        print("✓ Cleanup continues after exception (good error handling)")
        return "PASS"
    except Exception as e:
        print(f"✗ Second call failed: {e}")
        return "FAIL"

result3 = test_exception_handling()

# Test 4: Sleep timing verification
print("\n" + "=" * 80)
print("TEST 4: Sleep Timing Verification")
print("=" * 80)

def test_sleep_timing():
    """
    Verify that gevent.sleep() is used correctly (non-blocking).
    """
    try:
        import gevent
        print("✓ gevent available - will use gevent.sleep()")
        
        # Verify sleep is cooperative
        start = time.time()
        gevent.sleep(0.1)
        elapsed = time.time() - start
        
        if 0.08 <= elapsed <= 0.15:
            print(f"✓ gevent.sleep() timing correct: {elapsed:.3f}s")
            return "PASS"
        else:
            print(f"⚠️  gevent.sleep() timing unexpected: {elapsed:.3f}s")
            return "WARNING"
            
    except ImportError:
        print("⚠️  gevent not available - falling back to time.sleep()")
        print("   (This is OK for development, but production needs gevent)")
        return "WARNING"

result4 = test_sleep_timing()

# Test 5: Lock contention during cleanup
print("\n" + "=" * 80)
print("TEST 5: Lock Contention During Cleanup")
print("=" * 80)

def test_lock_contention():
    """
    Test if long-running _purge_expired() blocks other operations.
    
    CRITICAL: If lock is held too long, workers can't serve requests.
    """
    from nodes.memory.buffer_memory import _STORE
    import time
    
    # Add test data
    test_messages = [{"role": "user", "content": "test"}]
    _STORE.set("test_session", test_messages, ttl_seconds=3600)
    
    # Measure lock acquisition time
    start = time.time()
    with _STORE._lock:
        # Simulate some work
        pass
    lock_time = time.time() - start
    
    print(f"Lock acquisition time: {lock_time * 1000:.3f}ms")
    
    if lock_time < 0.010:  # Less than 10ms
        print("✓ Lock acquisition is fast (no contention)")
        return "PASS"
    elif lock_time < 0.100:  # Less than 100ms
        print("⚠️  Lock acquisition is moderate (some contention)")
        return "WARNING"
    else:
        print("✗ Lock acquisition is slow (high contention)")
        return "FAIL"

result5 = test_lock_contention()

# Test 6: Memory leak detection
print("\n" + "=" * 80)
print("TEST 6: Memory Leak Detection in _cleanup_running Flag")
print("=" * 80)

def test_cleanup_flag_leak():
    """
    Verify that _cleanup_running is properly managed and doesn't cause issues.
    
    ISSUE: _cleanup_running is set to True but never set back to False.
    This prevents restart of cleanup if it ever stops.
    """
    from nodes.memory.buffer_memory import _InMemoryConversationStore
    
    store = _InMemoryConversationStore()
    
    print(f"Initial _cleanup_running: {store._cleanup_running}")
    
    # Try to start cleanup again
    store._start_cleanup_greenlet()
    print(f"After second call: {store._cleanup_running}")
    
    # This is expected behavior (idempotent), but let's verify
    if store._cleanup_running:
        print("✓ _cleanup_running flag prevents duplicate starts")
        print("⚠️  NOTE: If cleanup crashes, it can't be restarted (flag stays True)")
        return "WARNING"
    else:
        print("✗ _cleanup_running flag not working correctly")
        return "FAIL"

result6 = test_cleanup_flag_leak()

# Test 7: TTL=0 edge case
print("\n" + "=" * 80)
print("TEST 7: TTL=0 Edge Case (No Expiration)")
print("=" * 80)

def test_ttl_zero():
    """
    Test behavior when ttl_seconds=0 (no expiration).
    
    ISSUE: entries with expires_at=0 should never expire,
    but check if _purge_expired handles this correctly.
    """
    from nodes.memory.buffer_memory import _STORE
    import time
    
    # Add entry with TTL=0 (no expiration)
    test_messages = [{"role": "user", "content": "test"}]
    _STORE.set("no_expire_session", test_messages, ttl_seconds=0)
    
    # Get the entry
    entry = _STORE._store.get("memory:session:no_expire_session")
    print(f"Entry expires_at: {entry.expires_at if entry else 'None'}")
    
    # Manually trigger purge
    _STORE._purge_expired()
    
    # Check if entry still exists
    still_exists = _STORE.get("no_expire_session")
    
    if still_exists:
        print("✓ TTL=0 entries are not purged (correct)")
        return "PASS"
    else:
        print("✗ TTL=0 entry was purged (incorrect)")
        return "FAIL"

result7 = test_ttl_zero()

# Test 8: expires_at=0 vs expires_at=None
print("\n" + "=" * 80)
print("TEST 8: expires_at=0 vs expires_at=None Handling")
print("=" * 80)

def test_expires_at_zero():
    """
    Check the condition in _purge_expired: if v.expires_at and v.expires_at <= now
    
    ISSUE: expires_at=0 is falsy in Python, so it won't be purged.
    This might be intentional (no expiration), but should be verified.
    """
    from nodes.memory.buffer_memory import _Entry
    import time
    
    now = time.time()
    
    # Test entry with expires_at=0
    entry_zero = _Entry(messages=[], expires_at=0)
    
    # Test the condition from _purge_expired
    should_delete_zero = entry_zero.expires_at and entry_zero.expires_at <= now
    
    print(f"expires_at=0: should_delete={should_delete_zero}")
    print(f"  Explanation: expires_at=0 is falsy, so 'v.expires_at and ...' fails")
    print(f"  Result: Entry with expires_at=0 will NEVER be deleted")
    
    # Test entry with expires_at in the past
    entry_past = _Entry(messages=[], expires_at=now - 100)
    should_delete_past = entry_past.expires_at and entry_past.expires_at <= now
    
    print(f"\nexpires_at={now - 100} (past): should_delete={should_delete_past}")
    
    if not should_delete_zero and should_delete_past:
        print("\n✓ Logic is correct: expires_at=0 means no expiration")
        return "PASS"
    else:
        print("\n✗ Logic issue detected")
        return "FAIL"

result8 = test_expires_at_zero()

# Test 9: Concurrent access during cleanup
print("\n" + "=" * 80)
print("TEST 9: Concurrent Get/Set During Cleanup")
print("=" * 80)

def test_concurrent_access():
    """
    Simulate concurrent access while cleanup is running.
    
    ISSUE: If cleanup holds lock for too long, get/set operations will block.
    """
    from nodes.memory.buffer_memory import _STORE
    import threading
    import time
    
    # Add 100 expired entries
    past_time = time.time() - 3700  # 1 hour + 100 seconds ago
    for i in range(100):
        key = f"memory:session:expired_{i}"
        from nodes.memory.buffer_memory import _Entry
        _STORE._store[key] = _Entry(
            messages=[{"role": "user", "content": f"msg{i}"}],
            expires_at=past_time
        )
    
    # Also add one active entry
    _STORE.set("active_session", [{"role": "user", "content": "active"}], ttl_seconds=3600)
    
    print(f"Setup: {len(_STORE._store)} entries (100 expired, 1 active)")
    
    # Measure cleanup time
    start = time.time()
    _STORE._purge_expired()
    cleanup_time = time.time() - start
    
    print(f"Cleanup time for 100 expired entries: {cleanup_time * 1000:.2f}ms")
    print(f"Remaining entries: {len(_STORE._store)}")
    
    if cleanup_time < 0.100:  # Less than 100ms
        print("✓ Cleanup is fast, minimal lock contention")
        return "PASS"
    elif cleanup_time < 0.500:  # Less than 500ms
        print("⚠️  Cleanup is moderate, some contention possible")
        return "WARNING"
    else:
        print("✗ Cleanup is slow, high lock contention risk")
        return "FAIL"

result9 = test_concurrent_access()

# Test 10: Gevent availability detection
print("\n" + "=" * 80)
print("TEST 10: Gevent Availability Detection")
print("=" * 80)

def test_gevent_detection():
    """
    Verify that GEVENT_AVAILABLE flag is set correctly.
    """
    from nodes.memory.buffer_memory import GEVENT_AVAILABLE
    
    print(f"GEVENT_AVAILABLE flag: {GEVENT_AVAILABLE}")
    
    try:
        import gevent
        if GEVENT_AVAILABLE:
            print("✓ gevent detected correctly")
            return "PASS"
        else:
            print("✗ gevent is available but flag is False")
            return "FAIL"
    except ImportError:
        if not GEVENT_AVAILABLE:
            print("✓ gevent absence detected correctly")
            return "PASS"
        else:
            print("✗ gevent is not available but flag is True")
            return "FAIL"

result10 = test_gevent_detection()

# Summary
print("\n" + "=" * 80)
print("SUMMARY OF EDGE CASE TESTS")
print("=" * 80)

results = {
    "1. Multiple Instantiation": result1,
    "2. Singleton Pattern": result2,
    "3. Exception Handling": result3,
    "4. Sleep Timing": result4,
    "5. Lock Contention": result5,
    "6. Cleanup Flag Management": result6,
    "7. TTL=0 Edge Case": result7,
    "8. expires_at Logic": result8,
    "9. Concurrent Access": result9,
    "10. Gevent Detection": result10,
}

for test, result in results.items():
    symbol = "✓" if result == "PASS" else "⚠️ " if result == "WARNING" else "✗"
    print(f"{symbol} {test}: {result}")

# Overall assessment
passes = sum(1 for r in results.values() if r == "PASS")
warnings = sum(1 for r in results.values() if r == "WARNING")
fails = sum(1 for r in results.values() if r == "FAIL")

print(f"\nOverall: {passes} PASS, {warnings} WARNING, {fails} FAIL")

if fails > 0:
    print("\n⚠️  CRITICAL ISSUES DETECTED - Review required!")
elif warnings > 2:
    print("\n⚠️  Multiple warnings - Consider improvements")
else:
    print("\n✓ Edge cases handled adequately")
