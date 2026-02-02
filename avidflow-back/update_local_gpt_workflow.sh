#!/bin/bash

# Update the Local GPT node parameters in the existing workflow
# This patches the workflow to use the correct OpenWebUI settings

WORKFLOW_ID="4f452bd8-6866-415a-a2ea-632a58bb5e24"
API_BASE="http://localhost:8000"

# Get your access token first (replace with your actual credentials)
read -p "Enter your email: " EMAIL
read -sp "Enter your password: " PASSWORD
echo

TOKEN=$(curl -s -X POST "$API_BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\": \"$EMAIL\", \"password\": \"$PASSWORD\"}" | jq -r '.access_token')

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ]; then
  echo "❌ Failed to get access token"
  exit 1
fi

echo "✅ Got access token"

# Get the current workflow
WORKFLOW=$(curl -s -X GET "$API_BASE/api/workflows/$WORKFLOW_ID" \
  -H "Authorization: Bearer $TOKEN")

# Update the Local GPT node parameters using jq
UPDATED_WORKFLOW=$(echo "$WORKFLOW" | jq '
  .workflow.nodes |= map(
    if .type == "localGpt" then
      .parameters.authType = "bearer" |
      .parameters.loginEndpoint = "/api/v1/auths/signin" |
      .parameters.endpointPath = "/api/chat/completions"
    else
      .
    end
  )
')

# Save the updated workflow back
curl -X PUT "$API_BASE/api/workflows/$WORKFLOW_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$UPDATED_WORKFLOW" | jq '.'

echo ""
echo "✅ Workflow updated with correct OpenWebUI parameters:"
echo "   - authType: bearer"
echo "   - loginEndpoint: /api/v1/auths/signin"
echo "   - endpointPath: /api/chat/completions"
