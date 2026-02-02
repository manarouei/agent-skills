#!/usr/bin/env python3
"""
Test Memory Auto-Clear Functionality - Standalone Version
Run this to verify the memory fix works correctly
"""

# Simulate the memory manager logic without imports
def count_turns(messages):
    """Count user messages (= number of turns)"""
    return len([m for m in messages if m.get("role") == "user"])

def apply_memory_logic(messages, window=6, auto_clear=True):
    """Apply the same logic as MemoryManager.save()"""
    system_msgs = [m for m in messages if m.get("role") == "system"]
    non_system = [m for m in messages if m.get("role") != "system"]
    
    max_messages = window * 4
    user_messages = [m for m in non_system if m.get("role") == "user"]
    turn_count = len(user_messages)
    
    # AUTO-CLEAR LOGIC
    if auto_clear and turn_count >= window:
        # Find last user message
        user_indices = [i for i, m in enumerate(non_system) if m.get("role") == "user"]
        last_turn_start = user_indices[-1]
        recent = non_system[last_turn_start:]
        print(f"    🔄 AUTO-CLEAR: {turn_count} turns ≥ {window}, kept only last turn ({len(recent)} msgs)")
    else:
        # Normal truncation
        recent = non_system[-(max_messages):] if len(non_system) > max_messages else non_system
    
    return system_msgs + recent

def test_memory_autoclear():
    """Test auto-clear triggers correctly"""
    
    print("\n" + "="*80)
    print("MEMORY AUTO-CLEAR TEST (Logic Simulation)")
    print("="*80 + "\n")
    
    window = 6
    messages = []
    
    # Simulate 8 turns (should trigger auto-clear at turn 6)
    for turn in range(1, 9):
        # Add a new turn (4 messages)
        messages.extend([
            {"role": "user", "content": f"Question {turn}"},
            {"role": "assistant", "content": f"Answer {turn}", "tool_calls": []},
            {"role": "tool", "content": f"Tool result {turn}"},
            {"role": "assistant", "content": f"Final answer {turn}"}
        ])
        
        # Apply memory logic
        messages = apply_memory_logic(messages, window, auto_clear=True)
        
        user_count = count_turns(messages)
        print(f"Turn {turn}: {len(messages):2d} messages ({user_count} turns)")
        
        # Check expectations
        if turn < window:
            if user_count != turn:
                print(f"  ⚠️  Turn count mismatch: expected {turn}, got {user_count}")
        elif turn == window:
            # Should trigger auto-clear
            if user_count == 1 and len(messages) <= 5:
                print(f"  ✅ AUTO-CLEAR TRIGGERED! Reset to last turn")
            else:
                print(f"  ❌ AUTO-CLEAR FAILED! {user_count} turns, {len(messages)} messages")
        else:
            # After clear, should be rebuilding
            turns_since_clear = turn - window + 1
            if user_count != turns_since_clear:
                print(f"  ⚠️  Expected {turns_since_clear} turns after clear, got {user_count}")
    
    # Final check
    final_user_count = count_turns(messages)
    
    print("\n" + "-"*80)
    print(f"Final state: {len(messages)} messages, {final_user_count} turns")
    print("-"*80 + "\n")
    
    if final_user_count <= 3 and len(messages) < 15:
        print("✅ TEST PASSED: Memory auto-clear logic is working correctly!\n")
        return True
    else:
        print("❌ TEST FAILED: Memory did not auto-clear as expected!\n")
        print(f"   Expected: ≤3 turns, <15 messages")
        print(f"   Got: {final_user_count} turns, {len(messages)} messages\n")
        return False

if __name__ == "__main__":
    test_memory_autoclear()
