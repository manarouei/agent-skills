
# Real Execution Test Guide

## Prerequisites

1. **Start Back Project**:
   ```bash
   cd /home/toni/n8n/back
   uvicorn main:app --reload
   ```

2. **Create GitHub Credential** (one-time):
   ```bash
   curl -X POST http://localhost:8000/credentials      -H "Content-Type: application/json"      -H "Authorization: Bearer YOUR_JWT_TOKEN"      -d '{
       "name": "GitHub Test",
       "type": "githubApi",
       "data": {
         "server": "https://api.github.com",
         "accessToken": "'$GITHUB_TOKEN'"
       }
     }'
   ```

3. **Create Workflow**:
   ```bash
   curl -X POST http://localhost:8000/workflows      -H "Content-Type: application/json"      -H "Authorization: Bearer YOUR_JWT_TOKEN"      -d @test_github_workflow.json
   ```

4. **Execute Workflow** (REST API):
   ```bash
   curl -X POST http://localhost:8000/workflows/{workflow_id}/execute      -H "Content-Type: application/json"      -H "Authorization: Bearer YOUR_JWT_TOKEN"      -d '{}'
   ```

5. **Execute Workflow** (WebSocket - Real-time):
   ```javascript
   const ws = new WebSocket('ws://localhost:8000/ws/workflows/execute/{workflow_id}?token=YOUR_JWT_TOKEN');
   
   ws.onmessage = (event) => {
     const data = JSON.parse(event.data);
     console.log('Workflow Event:', data);
   };
   ```

## Expected Results

### 1 Get Repository Info
```json
{
  "name": "n8n",
  "full_name": "n8n-io/n8n",
  "owner": {"login": "n8n-io", "id": 10284570},
  "description": "Free and source-available fair-code licensed workflow automation tool...",
  "html_url": "https://github.com/n8n-io/n8n",
  "stargazers_count": 50000+,
  "forks_count": 7000+
}
```

### 2 Get Authenticated User
```json
{
  "login": "your-username",
  "id": 123456,
  "name": "Your Name",
  "email": "your@email.com",
  "public_repos": 10,
  "followers": 5
}
```

### 3 List Repository Issues (5 items)
```json
[
  {
    "number": 12345,
    "title": "Issue title",
    "state": "open",
    "user": {"login": "author"},
    "created_at": "2025-01-01T00:00:00Z"
  },
  ...
]
```

### 4 Get File Content
```json
{
  "name": "README.md",
  "path": "README.md",
  "content": "base64_encoded_content...",
  "encoding": "base64",
  "size": 12345
}
```

## Monitoring

Check execution logs:
```bash
cd /home/toni/n8n/back
tail -f logs/workflow_execution.log
```

Check Redis pub/sub:
```bash
redis-cli
> SUBSCRIBE workflow:{workflow_id}:*
```

## Troubleshooting

**Credential not found**: Ensure githubApi is registered in `credentials/__init__.py`
**Import error**: Verify GitHub node is in nodepacks or back project nodes directory
**Connection timeout**: Check GITHUB_TOKEN validity and network connectivity
**Parse error**: Validate workflow JSON with `jq . test_github_workflow.json`
