---
name: source-ingest
description: Ingest and parse source materials for node implementation. Fetches TypeScript source code or API documentation based on classified source type. Extracts relevant content and stores in context. Use when you have a classified source and need to fetch its contents.
---

# Source Ingest

Fetch and parse source materials based on classified source type.

## When to use this skill

Use this skill when:
- Source has been classified (Type1 or Type2)
- Need to fetch TypeScript code from n8n repository
- Need to fetch API documentation from URLs
- Preparing content for schema inference

## Ingestion by source type

### Type1: TypeScript Source
1. Fetch TypeScript file from GitHub
2. Parse and extract key components:
   - Node class definition
   - Properties array
   - Methods (execute, trigger, etc.)
   - Imports and dependencies
3. Store parsed content in context

### Type2: Documentation
1. Fetch documentation from provided URLs
2. Parse documentation format (HTML, Markdown, OpenAPI)
3. Extract:
   - Endpoints and operations
   - Parameters and schemas
   - Authentication requirements
   - Example requests/responses
4. Store parsed content in context

## Parsing guidelines

- Preserve original structure where possible
- Extract code blocks separately
- Identify and flag complex patterns
- Note any missing or incomplete sections

## Output format

Store ingested content with:
- Raw source content
- Parsed structured data
- Metadata (fetch time, source URL)
- Any extraction warnings
