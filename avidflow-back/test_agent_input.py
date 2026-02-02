#!/usr/bin/env python3
"""
Debug script to see what the AI Agent actually receives from Qdrant
"""
import json
import sys

# Simulate the response that would come from Qdrant retrieval
sample_response = {
    "items": [
        {
            "id": "1",
            "payload": {
                "content": "ماده 21 - اموالی که جزء ماترک متوفی باشد...",
                "metadata": {
                    "search_title": "[ماده قانونی] — ماده ۲۱",
                    "clause": "ماده ۲۱"
                }
            },
            "score": 0.5302
        },
        {
            "id": "2",
            "payload": {
                "content": "ماده 17 - اموال و دارایی ­هایی که در نتیجه فوت شخص...",
                "metadata": {
                    "search_title": "[ماده قانونی] — ماده ۱۷",
                    "clause": "ماده ۱۷"
                }
            },
            "score": 0.4921
        }
    ],
    "count": 2
}

print("=== Simulated Qdrant Response ===")
print(json.dumps(sample_response, indent=2, ensure_ascii=False))

print("\n=== What AI Agent Sees (after process_tool_response) ===")
# This would be the processed version
print("Tool: Qdrant_Vector_Store")
print(f"Document count: {len(sample_response['items'])}")
print("\nFirst document:")
print(f"  Title: {sample_response['items'][0]['payload']['metadata']['search_title']}")
print(f"  Content: {sample_response['items'][0]['payload']['content'][:100]}...")

