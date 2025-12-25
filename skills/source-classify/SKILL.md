---
name: source-classify
description: Classify the source type for node implementation. Determines if source is Type1 (existing n8n TypeScript node) or Type2 (documentation-only). Returns confidence score and evidence. Use when you need to determine the implementation approach for a workflow node.
---

# Source Classify

Classify the source type to determine the implementation approach.

## When to use this skill

Use this skill when:
- Starting node implementation and need to determine approach
- Have a node name and need to find if TypeScript source exists
- Need to decide between code conversion (Type1) or LLM implementation (Type2)

## Source types

### Type1: N8N TypeScript
- An existing n8n TypeScript node implementation exists
- Path pattern: packages/nodes-base/nodes/{NodeName}/{NodeName}.node.ts
- Approach: Convert TypeScript to Python

### Type2: Documentation Only
- No existing implementation, only API documentation
- May have: API docs URL, OpenAPI spec, or manual documentation
- Approach: LLM-based implementation from documentation

### Unknown
- Cannot determine source type with confidence
- Requires human clarification

## Classification process

1. Check if source_refs.ts_path points to valid TypeScript file
2. Search n8n repository for matching node name patterns
3. Check if source_refs.docs_url is provided
4. Calculate confidence score based on evidence

## Confidence scoring

- 0.9-1.0: High confidence, proceed automatically
- 0.7-0.9: Medium confidence, flag for verification
- Below 0.7: Low confidence, require human input

## Guidelines

- Always return confidence score
- Collect all available evidence
- Return UNKNOWN if confidence below 0.5
- Never guess without evidence
