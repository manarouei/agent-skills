# Local GPT Troubleshooting Guide

## Current Issue: HTTP 405 Method Not Allowed

The 405 error means the endpoint doesn't accept POST requests or the URL is incorrect.

## OpenWebUI API Endpoints

Based on your screenshots showing OpenWebUI (gpt-oss:120b), here are the correct endpoints:

### Option 1: OpenAI-Compatible API (Most Common)
```
POST http://178.131.134.191:11300/api/chat/completions
```

### Option 2: Alternative OpenAI Format
```
POST http://178.131.134.191:11300/v1/chat/completions
```

### Option 3: OpenWebUI Native API
```
POST http://178.131.134.191:11300/api/chat
```

## How to Test Each Endpoint

### Test with curl:

```bash
# Test Option 1 (OpenWebUI API)
curl -X POST http://178.131.134.191:11300/api/chat/completions \
  -H "Content-Type: application/json" \
  -u "madna@email.com:lavashaj" \
  -d '{
    "model": "gpt-oss:120b",
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.7,
    "max_tokens": 100
  }'

# Test Option 2 (Standard OpenAI)
curl -X POST http://178.131.134.191:11300/v1/chat/completions \
  -H "Content-Type: application/json" \
  -u "madna@email.com:lavashaj" \
  -d '{
    "model": "gpt-oss:120b",
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.7,
    "max_tokens": 100
  }'

# Test Option 3 (OpenWebUI Native)
curl -X POST http://178.131.134.191:11300/api/chat \
  -H "Content-Type: application/json" \
  -u "madna@email.com:lavashaj" \
  -d '{
    "model": "gpt-oss:120b",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

## What to Check in Logs

After running the workflow, check the Celery worker logs for:

```
LOCAL GPT NODE: Starting chat completion
LOCAL GPT: Configuration:
  - Base URL: http://178.131.134.191:11300
  - Auth Type: basic
LOCAL GPT: Full URL: <ACTUAL_URL>
LOCAL GPT: Request payload: <PAYLOAD>
LOCAL GPT: Response status code: 405
```

## Update Node Configuration

Once you find the working endpoint, update the workflow JSON:

```json
{
  "parameters": {
    "baseUrl": "http://178.131.134.191:11300",
    "endpointPath": "/api/chat/completions",  // ← Change this!
    "model": "gpt-oss:120b"
  }
}
```

## Common OpenWebUI Endpoint Patterns

1. **OpenAI-compatible**: `/v1/chat/completions`
2. **OpenWebUI API**: `/api/chat/completions` or `/api/chat`
3. **Alternative**: `/api/v1/chat/completions`

## Debugging Steps

1. **Check Celery logs** for the detailed request/response
2. **Test endpoints** manually with curl
3. **Update endpointPath** in workflow to the working endpoint
4. **Verify authentication** - Basic Auth with username@email.com format

## Expected Log Output (Success)

```
LOCAL GPT: Response status code: 200
LOCAL GPT: Successfully parsed JSON response
LOCAL GPT: Extracted message content (length: XXX)
```

## Next Steps

1. Run the workflow again and watch Celery logs
2. Look for the "Full URL" line to see what URL was actually called
3. Try the curl commands above to find the working endpoint
4. Update the endpointPath parameter to match
