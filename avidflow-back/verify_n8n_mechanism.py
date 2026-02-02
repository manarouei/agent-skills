"""
Verify n8n's Multi-Query Mechanism

This script checks if n8n's advantage comes from:
1. Multiple tool calls
2. Better LLM synthesis
3. Cross-references in metadata
"""

import json
from typing import List, Dict, Set

def extract_article_numbers(text: str) -> Set[str]:
    """Extract article numbers from Persian text"""
    import re
    # Match patterns like: ماده ۱۹, ماده 19, ماده (19)
    patterns = [
        r'ماده\s*[\(]?(\d+)[\)]?',
        r'ماده\s*[\(]?([۰-۹]+)[\)]?'
    ]
    
    articles = set()
    for pattern in patterns:
        matches = re.findall(pattern, text)
        articles.update(matches)
    
    return articles

def analyze_n8n_response(response_data: Dict) -> Dict:
    """Analyze n8n response to understand mechanism"""
    
    analysis = {
        "tool_calls": [],
        "retrieved_articles": set(),
        "mentioned_articles": set(),
        "hallucinated_articles": set(),
        "chunk_cross_references": {}
    }
    
    # Extract tool calls
    if "intermediate_steps" in response_data:
        for step in response_data["intermediate_steps"]:
            if "action" in step:
                query = step["action"].get("tool_input", {}).get("query", "")
                analysis["tool_calls"].append(query)
            
            # Analyze retrieved chunks
            if "observation" in step:
                obs = step["observation"]
                if isinstance(obs, dict) and "items" in obs:
                    for item in obs["items"]:
                        # Parse JSON content
                        if "text" in item:
                            chunk_data = json.loads(item["text"])
                            
                            # Extract articles from metadata
                            metadata = chunk_data.get("metadata", {})
                            search_title = metadata.get("search_title", "")
                            articles_in_title = extract_article_numbers(search_title)
                            analysis["retrieved_articles"].update(articles_in_title)
                            
                            # Check for cross-references in content
                            content = chunk_data.get("pageContent", "")
                            articles_in_content = extract_article_numbers(content)
                            
                            # Store cross-references
                            for article in articles_in_title:
                                if article not in analysis["chunk_cross_references"]:
                                    analysis["chunk_cross_references"][article] = set()
                                analysis["chunk_cross_references"][article].update(
                                    articles_in_content - articles_in_title
                                )
    
    # Extract mentioned articles from final response
    if "message" in response_data:
        analysis["mentioned_articles"] = extract_article_numbers(
            response_data["message"]
        )
    
    # Find hallucinated articles
    analysis["hallucinated_articles"] = (
        analysis["mentioned_articles"] - analysis["retrieved_articles"]
    )
    
    return analysis


def compare_n8n_platform(n8n_data: Dict, platform_data: Dict) -> Dict:
    """Compare n8n and platform responses"""
    
    n8n_analysis = analyze_n8n_response(n8n_data)
    platform_analysis = analyze_n8n_response(platform_data)
    
    comparison = {
        "n8n_tool_calls": len(n8n_analysis["tool_calls"]),
        "platform_tool_calls": len(platform_analysis["tool_calls"]),
        
        "n8n_retrieved": len(n8n_analysis["retrieved_articles"]),
        "platform_retrieved": len(platform_analysis["retrieved_articles"]),
        
        "n8n_mentioned": len(n8n_analysis["mentioned_articles"]),
        "platform_mentioned": len(platform_analysis["mentioned_articles"]),
        
        "n8n_hallucinated": list(n8n_analysis["hallucinated_articles"]),
        "platform_hallucinated": list(platform_analysis["hallucinated_articles"]),
        
        "articles_only_in_n8n": list(
            n8n_analysis["mentioned_articles"] - platform_analysis["mentioned_articles"]
        ),
        "articles_only_in_platform": list(
            platform_analysis["mentioned_articles"] - n8n_analysis["mentioned_articles"]
        ),
        
        "n8n_cross_refs": n8n_analysis["chunk_cross_references"],
        "platform_cross_refs": platform_analysis["chunk_cross_references"]
    }
    
    return comparison


def print_analysis(comparison: Dict):
    """Print analysis results"""
    
    print("=" * 80)
    print("n8n vs Platform Mechanism Analysis")
    print("=" * 80)
    
    print("\n📊 Tool Calls:")
    print(f"  n8n: {comparison['n8n_tool_calls']} calls")
    print(f"  Platform: {comparison['platform_tool_calls']} calls")
    
    print("\n📚 Articles Retrieved:")
    print(f"  n8n: {comparison['n8n_retrieved']} articles")
    print(f"  Platform: {comparison['platform_retrieved']} articles")
    
    print("\n📝 Articles Mentioned in Response:")
    print(f"  n8n: {comparison['n8n_mentioned']} articles")
    print(f"  Platform: {comparison['platform_mentioned']} articles")
    
    print("\n🚨 Hallucinated Articles (not in chunks):")
    print(f"  n8n: {comparison['n8n_hallucinated']}")
    print(f"  Platform: {comparison['platform_hallucinated']}")
    
    print("\n🎯 Unique Articles:")
    print(f"  Only in n8n: {comparison['articles_only_in_n8n']}")
    print(f"  Only in platform: {comparison['articles_only_in_platform']}")
    
    print("\n🔗 Cross-References in Chunks:")
    print("  n8n cross-refs:")
    for article, refs in list(comparison['n8n_cross_refs'].items())[:3]:
        print(f"    ماده {article} → {refs}")
    
    print("\n" + "=" * 80)
    
    # Conclusions
    print("\n🎯 Conclusions:")
    
    if comparison['n8n_tool_calls'] > comparison['platform_tool_calls']:
        print("  ✅ n8n uses MULTIPLE tool calls (multi-turn retrieval)")
    else:
        print("  ❌ n8n uses SINGLE tool call (same as platform)")
    
    if len(comparison['n8n_hallucinated']) > 0:
        print(f"  ⚠️  n8n LLM mentions {len(comparison['n8n_hallucinated'])} articles NOT in chunks")
        print("      → Either hallucination OR cross-reference following")
    
    if len(comparison['n8n_cross_refs']) > len(comparison['platform_cross_refs']):
        print("  ✅ n8n chunks contain MORE cross-references")
    
    print("\n💡 Recommendation:")
    if comparison['n8n_tool_calls'] > 1:
        print("  → Implement multi-turn tool calling in platform agent")
    elif len(comparison['n8n_hallucinated']) > 0:
        print("  → Investigate if n8n is using cross-references from metadata")
        print("  → Or test if GPT-4.1-mini has better synthesis capabilities")
    else:
        print("  → Focus on improving chunk quality and metadata")


if __name__ == "__main__":
    print("\n🔍 Loading test data...")
    print("   Please provide n8n and platform response JSON files\n")
    
    # Example usage:
    # with open("n8n_inheritance_response.json") as f:
    #     n8n_data = json.load(f)
    # 
    # with open("platform_inheritance_response.json") as f:
    #     platform_data = json.load(f)
    # 
    # comparison = compare_n8n_platform(n8n_data, platform_data)
    # print_analysis(comparison)
    
    print("📝 To run analysis:")
    print("   python verify_n8n_mechanism.py")
    print("   Then provide the JSON response files")
