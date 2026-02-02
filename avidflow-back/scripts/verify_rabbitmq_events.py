#!/usr/bin/env python3
"""
RabbitMQ Event Verification Script

This script monitors the workflow_updates queue and logs all events,
allowing you to verify which events are being published.

Usage:
    python scripts/verify_rabbitmq_events.py

Expected output (after suppression):
    - node_completed events (from executor)
    - agent_completed events (final result)
    - agent_error events (on failures)

Should NOT see (if suppression working):
    - agent_step events
    - tool_called events
    - tool_result events
    - memory_result events
    - model_result events
"""

import sys
import os
import json
from datetime import datetime
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pika
from config import settings


def create_connection():
    """Create RabbitMQ connection"""
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            virtual_host=settings.RABBITMQ_VHOST,
            credentials=pika.PlainCredentials(
                username=settings.RABBITMQ_USER,
                password=settings.RABBITMQ_PASSWORD
            )
        )
    )


def monitor_queue(duration_seconds: int = 60):
    """
    Monitor workflow_updates queue for specified duration.
    
    Args:
        duration_seconds: How long to monitor (default 60s)
    """
    print("=" * 80)
    print("RABBITMQ EVENT MONITOR")
    print("=" * 80)
    print(f"Queue: workflow_updates")
    print(f"Monitoring for {duration_seconds} seconds...")
    print(f"Start time: {datetime.now().isoformat()}")
    print()
    print("Events received:")
    print("-" * 80)
    
    event_counts = defaultdict(int)
    messages_received = []
    
    connection = create_connection()
    channel = connection.channel()
    
    # Declare queue (ensure it exists)
    channel.queue_declare(queue="workflow_updates", durable=True)
    
    def callback(ch, method, properties, body):
        try:
            message = json.loads(body)
            event_type = message.get("event", "unknown")
            node_name = message.get("node_name", "N/A")
            workflow_id = message.get("workflow_id", "N/A")[:8] + "..."
            
            event_counts[event_type] += 1
            messages_received.append({
                "event": event_type,
                "node": node_name,
                "time": datetime.now().isoformat()
            })
            
            # Color-code output based on event type
            suppressed_events = {"agent_step", "tool_called", "tool_result", "memory_result", "model_result"}
            if event_type in suppressed_events:
                print(f"  ❌ [{event_type:20}] node={node_name:25} workflow={workflow_id}  ← SHOULD BE SUPPRESSED!")
            else:
                print(f"  ✅ [{event_type:20}] node={node_name:25} workflow={workflow_id}")
            
            # Acknowledge message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            print(f"  ⚠️ Error processing message: {e}")
            ch.basic_ack(delivery_tag=method.delivery_tag)
    
    # Set up consumer
    channel.basic_consume(queue="workflow_updates", on_message_callback=callback)
    
    # Consume for specified duration
    import time
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration_seconds:
            connection.process_data_events(time_limit=1)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    finally:
        connection.close()
    
    # Print summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total messages: {sum(event_counts.values())}")
    print()
    print("Event breakdown:")
    
    suppressed_events = {"agent_step", "tool_called", "tool_result", "memory_result", "model_result"}
    
    for event_type, count in sorted(event_counts.items()):
        if event_type in suppressed_events:
            print(f"  ❌ {event_type}: {count}  ← SUPPRESSION FAILED!")
        else:
            print(f"  ✅ {event_type}: {count}")
    
    # Check for suppression leaks
    leaked = [e for e in suppressed_events if event_counts.get(e, 0) > 0]
    if leaked:
        print()
        print("⚠️ WARNING: The following events should be suppressed but were received:")
        for e in leaked:
            print(f"   - {e}: {event_counts[e]} messages")
    else:
        print()
        print("✅ All suppressed events are working correctly (none received)")


def get_queue_stats():
    """Get current queue statistics"""
    connection = create_connection()
    channel = connection.channel()
    
    # Passive declare to get queue info without creating
    result = channel.queue_declare(queue="workflow_updates", durable=True, passive=True)
    
    print("=" * 80)
    print("QUEUE STATISTICS")
    print("=" * 80)
    print(f"Queue: workflow_updates")
    print(f"Messages ready: {result.method.message_count}")
    print(f"Consumers: {result.method.consumer_count}")
    
    connection.close()


def purge_queue():
    """Purge all messages from the queue (useful for testing)"""
    connection = create_connection()
    channel = connection.channel()
    
    result = channel.queue_purge(queue="workflow_updates")
    
    print(f"Purged {result.method.message_count} messages from workflow_updates")
    
    connection.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RabbitMQ Event Verification")
    parser.add_argument("--monitor", "-m", type=int, default=0, 
                       help="Monitor queue for N seconds")
    parser.add_argument("--stats", "-s", action="store_true",
                       help="Show queue statistics")
    parser.add_argument("--purge", "-p", action="store_true",
                       help="Purge queue (delete all messages)")
    
    args = parser.parse_args()
    
    if args.stats:
        get_queue_stats()
    elif args.purge:
        purge_queue()
    elif args.monitor > 0:
        monitor_queue(args.monitor)
    else:
        # Default: show stats then monitor
        get_queue_stats()
        print()
        monitor_queue(30)
