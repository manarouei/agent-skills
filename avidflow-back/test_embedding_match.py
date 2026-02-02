#!/usr/bin/env python3
"""
Test script to verify OpenAI embeddings and Qdrant retrieval
Compare local results with production expectations
"""

import requests
import json
from qdrant_client import QdrantClient


def test_embedding():
    """Test if OpenAI embedding works correctly"""
    print("=" * 60)
    print("STEP 1: Testing OpenAI Embedding Generation")
    print("=" * 60)
    
    query = "مالیات بر ارث"
    print(f"Query: {query}\n")
    
    url = "https://api.openai.com/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    payload = {
        "input": [query],
        "model": "text-embedding-3-small",
        "dimensions": 1536
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        vector = data["data"][0]["embedding"]
        
        print(f"✓ Successfully generated embedding")
        print(f"  Dimensions: {len(vector)}")
        print(f"  First 5 values: {vector[:5]}")
        print(f"  Last 5 values: {vector[-5:]}")
        print(f"  Sum: {sum(vector):.4f}")
        
        return vector
        
    except Exception as e:
        print(f"✗ Failed to generate embedding: {e}")
        return None

def test_qdrant_search(vector):
    """Test Qdrant search with the generated vector"""
    print("\n" + "=" * 60)
    print("STEP 2: Testing Qdrant Search")
    print("=" * 60)
    
    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        
        # Test collection info
        collection_info = client.get_collection("all_files_a4")
        print(f"\n✓ Collection 'all_files_a4' info:")
        print(f"  Points count: {collection_info.points_count}")
        print(f"  Vector size: {collection_info.config.params.vectors.size}")
        
        # Search for similar documents
        results = client.search(
            collection_name="all_files_a4",
            query_vector=vector,
            limit=10,
            with_payload=True
        )
        
        print(f"\n✓ Found {len(results)} results\n")
        
        # Expected articles for "مالیات بر ارث" (inheritance tax)
        expected_articles = ["ماده ۱۷", "ماده ۱۹", "ماده ۲۰", "ماده ۲۱", "ماده ۲۸", "ماده ۳۲"]
        
        found_articles = []
        for i, result in enumerate(results[:10], 1):
            metadata = result.payload.get("metadata", {})
            search_title = metadata.get("search_title", "N/A")
            clause = metadata.get("clause", "N/A")
            content = result.payload.get("content", "")[:150]
            
            print(f"{i}. Score: {result.score:.4f}")
            print(f"   Title: {search_title}")
            print(f"   Clause: {clause}")
            print(f"   Content: {content}...")
            print()
            
            found_articles.append(clause)
        
        # Check if we found expected articles
        print("=" * 60)
        print("VALIDATION: Checking for expected inheritance tax articles")
        print("=" * 60)
        
        for expected in expected_articles:
            if any(expected in article for article in found_articles):
                print(f"✓ Found: {expected}")
            else:
                print(f"✗ Missing: {expected}")
        
        return results
        
    except Exception as e:
        print(f"✗ Failed to search Qdrant: {e}")
        return None

def main():
    print("\n🔍 Testing Local Embedding and Qdrant Retrieval\n")
    
    # Check if credentials are set
    if OPENAI_API_KEY == "YOUR_OPENAI_API_KEY":
        print("❌ Please set OPENAI_API_KEY in the script")
        return
    
    if QDRANT_API_KEY == "YOUR_QDRANT_API_KEY":
        print("❌ Please set QDRANT_API_KEY in the script")
        return
    
    # Test embedding
    vector = test_embedding()
    if not vector:
        return
    
    # Test Qdrant search
    results = test_qdrant_search(vector)
    if not results:
        return
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("If the top results include ماده ۱۷, ماده ۱۹, ماده ۲۱:")
    print("  → Local system is working correctly ✓")
    print("  → Problem might be in AI Agent's processing")
    print("\nIf the top results are about other topics:")
    print("  → Database might have wrong data ✗")
    print("  → OR wrong collection/credentials ✗")
    print("\n")

if __name__ == "__main__":
    main()
