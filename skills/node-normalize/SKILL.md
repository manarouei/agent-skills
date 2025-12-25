---
name: node-normalize
description: Normalize incoming node implementation requests. Generates a correlation ID, converts node names to lowercase with hyphens, and creates an immutable request snapshot. Use when starting a new node implementation pipeline or when receiving a raw node name that needs standardization.
---

# Node Normalize

Normalize incoming node implementation requests before processing.

## When to use this skill

Use this skill when:
- Starting a new node implementation pipeline
- Receiving a raw node name from user input
- Need to generate a unique correlation ID for tracking
- Need to standardize node naming for filesystem compatibility

## How to normalize a node name

1. Convert the input name to lowercase
2. Replace spaces and underscores with hyphens
3. Remove special characters (keep only alphanumeric and hyphens)
4. Remove consecutive hyphens
5. Trim leading/trailing hyphens

## Examples

Input to Output:
- "Telegram Bot" becomes telegram-bot
- "shopify_api" becomes shopify-api
- "AWS S3" becomes aws-s3
- "  My--Custom_Node  " becomes my-custom-node

## Correlation ID format

Generate a UUID v4 correlation ID for pipeline tracking in the format node-{uuid4}.

Example: node-a1b2c3d4-e5f6-7890-abcd-ef1234567890

## Request snapshot

Create an immutable snapshot containing:
- Original node name (before normalization)
- Normalized node name
- Timestamp (ISO 8601)
- Source references (if provided)
- Correlation ID

## Guidelines

- Never modify the original input in place
- Always log the correlation ID at creation
- Snapshot must be immutable after creation
- Empty or whitespace-only names should fail with clear error
