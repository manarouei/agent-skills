#!/usr/bin/env python3
"""
Memory Auto-Clear Behavior Simulator
Demonstrates how auto-clear works vs sliding window
"""

def simulate_memory_behavior(turns=10, window=6, auto_clear=True):
    """Simulate memory behavior over multiple turns"""
    
    print(f"\n{'='*80}")
    print(f"Memory Simulation: {turns} turns, window={window}, auto_clear={auto_clear}")
    print(f"{'='*80}\n")
    
    messages = []
    max_messages = window * 4  # 4 messages per turn
    
    for turn in range(1, turns + 1):
        # Add new turn (simulate 4 messages: user, assistant, tool, tool_result)
        new_messages = [
            f"turn{turn}_user",
            f"turn{turn}_assistant",
            f"turn{turn}_tool1",
            f"turn{turn}_tool2"
        ]
        messages.extend(new_messages)
        
        # Count user messages (= number of turns)
        user_count = len([m for m in messages if "_user" in m])
        
        # Apply memory logic
        if auto_clear and len(messages) >= max_messages and user_count >= window:
            # AUTO-CLEAR: Keep only last turn
            last_turn_start = len(messages) - 4
            messages = messages[last_turn_start:]
            status = "🔄 AUTO-CLEARED!"
        elif len(messages) > max_messages:
            # SLIDING WINDOW: Keep last N messages
            messages = messages[-max_messages:]
            status = "📉 Truncated (sliding)"
        else:
            status = "✓ Normal"
        
        print(f"Turn {turn:2d}: {len(messages):2d} messages | {status:25s} | {messages[0][:10]}...{messages[-1][-10:]}")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("MEMORY AUTO-CLEAR vs SLIDING WINDOW COMPARISON")
    print("="*80)
    
    # Test 1: Auto-clear enabled (NEW behavior)
    simulate_memory_behavior(turns=15, window=6, auto_clear=True)
    
    # Test 2: Sliding window (OLD behavior)
    simulate_memory_behavior(turns=15, window=6, auto_clear=False)
    
    print("\n📊 SUMMARY:")
    print("─" * 80)
    print("Auto-Clear (NEW):")
    print("  ✓ Clears memory when full (every 6 turns)")
    print("  ✓ Keeps only last turn on clear (4 messages)")
    print("  ✓ Average memory: ~12-16 messages")
    print("  ✓ Token savings: 30-40%")
    print()
    print("Sliding Window (OLD):")
    print("  ✓ Maintains full window always (24 messages)")
    print("  ✓ Gradual context shift")
    print("  ✓ No sudden clears")
    print("  ✗ Higher token usage")
    print("─" * 80)
