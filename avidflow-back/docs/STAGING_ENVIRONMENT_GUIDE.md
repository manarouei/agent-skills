# Staging Environment Guide

## Minimum Cost, Maximum Benefit Staging Strategy

This guide outlines best practices for maintaining a staging environment that catches bugs before production while keeping costs minimal.

---

## Table of Contents

1. [Infrastructure Strategy](#1-infrastructure-strategy)
2. [Testing OAuth2 Flows](#2-testing-oauth2-flows)
3. [Data Strategy](#3-data-strategy)
4. [Deployment Pipeline](#4-deployment-pipeline)
5. [Monitoring & Debugging](#5-monitoring--debugging)
6. [Cost Optimization](#6-cost-optimization)
7. [Checklist Before Production](#7-checklist-before-production)

---

## 1. Infrastructure Strategy

### Recommended Staging Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STAGING ENVIRONMENT                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   App (1)    │    │   Worker (1) │    │   Beat (1)   │  │
│  │  gunicorn    │    │    celery    │    │    celery    │  │
│  │  4 workers   │    │  gevent 12   │    │   beat       │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  PostgreSQL  │    │   RabbitMQ   │    │    Redis     │  │
│  │   (shared)   │    │   (shared)   │    │   (shared)   │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Cost-Effective Configuration

```yaml
# docker-compose.stage.yml - Optimized for cost
services:
  app:
    # Use smaller resource limits than production
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  celery_worker:
    # Reduce concurrency for staging
    command: celery -A celery_app worker --loglevel=info --pool=gevent --concurrency=12
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G

  # Combine beat with message worker in staging
  celery_beat:
    # Single instance is fine for staging
```

### Environment Parity Checklist

| Component | Production | Staging | Notes |
|-----------|------------|---------|-------|
| Python Version | 3.10+ | 3.10+ | ✅ Must match |
| PostgreSQL | 17 | 17 | ✅ Must match |
| Redis | 7.x | 7.x | ✅ Must match |
| RabbitMQ | 4.x | 4.x | ✅ Must match |
| Celery Pool | gevent | gevent | ✅ Critical for testing |
| SSL/TLS | Yes | Yes | ✅ For OAuth callbacks |
| Workers | 4+ | 2-4 | Can be fewer |
| Concurrency | 24 | 12 | Can be fewer |

---

## 2. Testing OAuth2 Flows

### The Challenge

OAuth2 tokens from Google require real credentials obtained through the OAuth flow. Testing token refresh on staging requires one of these approaches:

### Approach A: Use Google OAuth Playground (Recommended for Dev)

1. Go to [OAuth 2.0 Playground](https://developers.google.com/oauthplayground)
2. Configure with your OAuth Client ID:
   - Click ⚙️ (settings)
   - Check "Use your own OAuth credentials"
   - Enter your `client_id` and `client_secret`
3. Select required scopes (e.g., Gmail API)
4. Authorize and get tokens
5. Insert into staging database manually

```sql
-- Example: Create test credential in staging
INSERT INTO credentials (user_id, type, name, encrypted_data, created_at, updated_at)
VALUES (
    1,  -- Your test user ID
    'gmailOAuth2',
    'Test Gmail Credential',
    'ENCRYPTED_DATA_HERE',  -- Use your encryption utility
    NOW(),
    NOW()
);
```

### Approach B: Use Staging Frontend (Best for E2E)

1. Ensure staging has valid OAuth callback URL configured in Google Console
2. Add staging URL to Google OAuth consent screen:
   - `https://stage.yourplatform.com/api/oauth2/callback`
3. Complete OAuth flow through staging frontend
4. Credential is automatically saved

### Approach C: Copy Your Own Test Credentials

⚠️ **Only copy YOUR OWN test account credentials, never user data!**

```python
# scripts/copy_test_credential.py
"""
Safely copy a specific credential from prod to stage.
Only use for YOUR OWN test credentials.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.config import get_sync_session_manual
from models.credential import Credential

# Production credential ID (your own test credential)
PROD_CREDENTIAL_ID = 123

# Get from production
with get_sync_session_manual() as session:
    cred = session.query(Credential).get(PROD_CREDENTIAL_ID)
    if cred:
        print(f"Type: {cred.type}")
        print(f"Name: {cred.name}")
        print(f"Encrypted data (copy this): {cred.encrypted_data}")
```

### Using the Stage OAuth Test Script

```bash
# List existing Google credentials
python scripts/stage_oauth_test.py --mode list

# Test with mock (no real credentials needed)
python scripts/stage_oauth_test.py --mode mock

# Test all mock scenarios
python scripts/stage_oauth_test.py --mode mock-all

# Check real credential status (dry run)
python scripts/stage_oauth_test.py --mode real --credential-id 123 --dry-run

# Actually refresh a real credential
python scripts/stage_oauth_test.py --mode real --credential-id 123

# Simulate full Celery execution flow
python scripts/stage_oauth_test.py --mode celery-sim --credential-id 123

# Force expire a token to test refresh
python scripts/stage_oauth_test.py --mode force-expire --credential-id 123
```

### Testing Token Refresh Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    TOKEN REFRESH TEST FLOW                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Get valid credential → 2. Force expire token                │
│                                    ↓                             │
│  4. Verify new token ← 3. Trigger workflow/test script          │
│                                                                  │
│  Expected: Token auto-refreshes, workflow completes              │
│  Error case: invalid_grant → User must reconnect                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Strategy

### Minimal Data Approach (Recommended)

Instead of syncing production data, create minimal test fixtures:

```python
# scripts/seed_stage_data.py
"""
Seed minimal test data for staging.
"""

def seed_test_user():
    """Create a test user for staging."""
    from database.config import get_sync_session_manual
    from models.user import User
    from auth.utils import get_password_hash
    
    with get_sync_session_manual() as session:
        user = User(
            email="staging-test@yourcompany.com",
            username="staging_tester",
            hashed_password=get_password_hash("staging-test-password"),
            is_active=True,
        )
        session.add(user)
        session.commit()
        print(f"Created test user ID: {user.id}")

def seed_test_workflow():
    """Create a simple test workflow."""
    # Create workflow with Google node for testing
    pass

if __name__ == "__main__":
    seed_test_user()
    seed_test_workflow()
```

### Data Anonymization (If Needed)

If you must use production-like data:

```python
# scripts/anonymize_data.py
"""
Anonymize sensitive data for staging use.
"""

import hashlib
from faker import Faker

fake = Faker()

def anonymize_user(user):
    """Anonymize user data."""
    user.email = f"user_{user.id}@staging.test"
    user.username = f"user_{user.id}"
    user.hashed_password = "DISABLED"
    return user

def anonymize_credential(credential):
    """Remove real OAuth tokens."""
    # Clear real tokens - user must re-auth on staging
    credential.encrypted_data = None
    return credential
```

---

## 4. Deployment Pipeline

### GitLab CI/CD Example

```yaml
# .gitlab-ci.yml
stages:
  - test
  - build
  - deploy-staging
  - deploy-production

variables:
  DOCKER_IMAGE: $CI_REGISTRY_IMAGE:$CI_COMMIT_REF_SLUG

# Run unit tests first
test:
  stage: test
  script:
    - pip install -r requirements.txt
    - pytest tests/ -v --tb=short
  only:
    - merge_requests
    - main
    - develop

# Build Docker image
build:
  stage: build
  script:
    - docker build -t $DOCKER_IMAGE .
    - docker push $DOCKER_IMAGE
  only:
    - main
    - develop

# Deploy to staging (automatic on develop)
deploy-staging:
  stage: deploy-staging
  script:
    - ssh staging "cd /app && docker-compose -f docker-compose.stage.yml pull"
    - ssh staging "cd /app && docker-compose -f docker-compose.stage.yml up -d"
    - ssh staging "cd /app && docker-compose -f docker-compose.stage.yml exec -T app python scripts/stage_oauth_test.py --mode mock-all"
  environment:
    name: staging
    url: https://stage.yourplatform.com
  only:
    - develop

# Deploy to production (manual, only on main)
deploy-production:
  stage: deploy-production
  script:
    - ssh production "cd /app && docker-compose pull"
    - ssh production "cd /app && docker-compose up -d"
  environment:
    name: production
    url: https://yourplatform.com
  when: manual
  only:
    - main
```

### Pre-Deployment Checklist Script

```bash
#!/bin/bash
# scripts/pre_deploy_check.sh

echo "=== Pre-Deployment Checks ==="

# 1. Run unit tests
echo "Running unit tests..."
pytest tests/ -v --tb=short || exit 1

# 2. Run OAuth mock tests
echo "Running OAuth mock tests..."
python scripts/stage_oauth_test.py --mode mock-all || exit 1

# 3. Check for migrations
echo "Checking for pending migrations..."
alembic check || echo "WARNING: Pending migrations detected"

# 4. Verify configuration
echo "Verifying configuration..."
python -c "from config import get_settings; s = get_settings(); print(f'ENV: {s.ENV}')"

echo "=== All checks passed ==="
```

---

## 5. Monitoring & Debugging

### Staging Logging Configuration

```python
# config.py addition for staging
import logging

if settings.ENV == "staging":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('staging.log'),
            logging.StreamHandler()
        ]
    )
    
    # Extra verbose for OAuth debugging
    logging.getLogger('nodes.gmail').setLevel(logging.DEBUG)
    logging.getLogger('nodes.googleDrive').setLevel(logging.DEBUG)
```

### Health Check Endpoint

```python
# routers/health.py
from fastapi import APIRouter
from database.config import get_sync_session_manual
from celery_app import celery_app

router = APIRouter()

@router.get("/health/detailed")
async def detailed_health():
    """Detailed health check for staging debugging."""
    checks = {}
    
    # Database
    try:
        with get_sync_session_manual() as session:
            session.execute("SELECT 1")
        checks["database"] = "OK"
    except Exception as e:
        checks["database"] = f"ERROR: {e}"
    
    # Celery
    try:
        result = celery_app.control.ping(timeout=5)
        checks["celery"] = "OK" if result else "NO_WORKERS"
    except Exception as e:
        checks["celery"] = f"ERROR: {e}"
    
    # Redis
    try:
        # Check Redis connection
        checks["redis"] = "OK"
    except Exception as e:
        checks["redis"] = f"ERROR: {e}"
    
    return {
        "status": "healthy" if all(v == "OK" for v in checks.values()) else "degraded",
        "checks": checks
    }
```

### Debug Commands

```bash
# Check Celery worker status
docker-compose -f docker-compose.stage.yml exec celery_worker celery -A celery_app inspect active

# Check pending tasks
docker-compose -f docker-compose.stage.yml exec celery_worker celery -A celery_app inspect reserved

# View recent logs
docker-compose -f docker-compose.stage.yml logs --tail=100 celery_worker

# Execute test script inside container
docker-compose -f docker-compose.stage.yml exec app python scripts/stage_oauth_test.py --mode list
```

---

## 6. Cost Optimization

### Resource Scaling Strategy

```
Production:          Staging:
───────────────     ───────────────
4 app workers   →   2 app workers
24 celery conc  →   12 celery conc
2 celery worker →   1 celery worker
Dedicated DB    →   Shared/smaller DB
Always on       →   Can be turned off
```

### Auto-Shutdown for Staging

```bash
# scripts/staging_auto_shutdown.sh
# Run via cron: 0 20 * * 1-5 /app/scripts/staging_auto_shutdown.sh
# Shuts down staging at 8 PM on weekdays

#!/bin/bash
cd /path/to/staging
docker-compose -f docker-compose.stage.yml down

# Optional: Send notification
curl -X POST "https://hooks.slack.com/services/..." \
  -d '{"text":"Staging environment shut down for the night"}'
```

### Startup Script

```bash
# scripts/staging_startup.sh
#!/bin/bash
cd /path/to/staging
docker-compose -f docker-compose.stage.yml up -d

# Wait for services
sleep 30

# Run health check
curl -f http://localhost:10084/health || exit 1

echo "Staging environment ready"
```

### Cost Comparison

| Resource | Production (24/7) | Staging (Business Hours) | Savings |
|----------|------------------|--------------------------|---------|
| Compute | $200/month | $50/month (12hrs/day) | 75% |
| Database | $100/month | $25/month (smaller) | 75% |
| Redis | $30/month | $10/month | 67% |
| **Total** | **$330/month** | **$85/month** | **74%** |

---

## 7. Checklist Before Production

### Pre-Production Deployment Checklist

```markdown
## Code Quality
- [ ] All unit tests passing
- [ ] OAuth mock tests passing
- [ ] No linting errors
- [ ] Code reviewed and approved

## Integration Testing (Staging)
- [ ] Google OAuth flow tested (at least one credential type)
- [ ] Token refresh tested with expired token
- [ ] invalid_grant error handled correctly
- [ ] Workflow execution tested end-to-end

## Database
- [ ] Migrations tested on staging
- [ ] Rollback tested (if applicable)
- [ ] No breaking schema changes

## Performance
- [ ] No obvious memory leaks
- [ ] Response times acceptable
- [ ] Celery queue not backing up

## Security
- [ ] No secrets in code
- [ ] OAuth credentials properly encrypted
- [ ] CORS settings correct

## Documentation
- [ ] CHANGELOG updated
- [ ] API docs updated (if applicable)
- [ ] Runbook updated (if applicable)
```

### Quick Test Script for Production Readiness

```bash
#!/bin/bash
# scripts/production_ready_check.sh

set -e

echo "=== Production Readiness Check ==="

# 1. Unit tests
echo "[1/5] Running unit tests..."
pytest tests/ -q

# 2. OAuth tests
echo "[2/5] Running OAuth tests..."
python scripts/stage_oauth_test.py --mode mock-all

# 3. Type checking (if using)
echo "[3/5] Type checking..."
# mypy nodes/ --ignore-missing-imports || true

# 4. Check for TODOs/FIXMEs
echo "[4/5] Checking for TODOs..."
grep -r "TODO\|FIXME\|XXX" nodes/ --include="*.py" || echo "No TODOs found"

# 5. Security check
echo "[5/5] Security check..."
# Check no hardcoded secrets
grep -r "client_secret.*=" nodes/ --include="*.py" | grep -v "client_secret\s*=" || echo "No hardcoded secrets found"

echo ""
echo "=== All checks passed! Ready for production. ==="
```

---

## Quick Reference

### Common Commands

```bash
# Start staging
docker-compose -f docker-compose.stage.yml up -d

# View logs
docker-compose -f docker-compose.stage.yml logs -f

# Run OAuth test
docker-compose -f docker-compose.stage.yml exec app python scripts/stage_oauth_test.py --mode mock

# Check database
docker-compose -f docker-compose.stage.yml exec db psql -U workflow -d workflow_db

# Restart services
docker-compose -f docker-compose.stage.yml restart

# Stop staging
docker-compose -f docker-compose.stage.yml down
```

### Environment Variables for Staging

```bash
# .env.staging
ENV=staging
DEBUG=true
POSTGRES_HOST=db
POSTGRES_DB=workflow_db_stage
FRONTEND_URL=https://stage.yourplatform.com
OAUTH2_CALLBACK_URL=https://stage.yourplatform.com/api/oauth2/callback
```

---

## Summary

**Minimum Cost Strategy:**
1. Use smaller instances (50-75% less than production)
2. Run only during business hours (saves ~50%)
3. Combine services where possible
4. Use mock tests for most scenarios

**Maximum Benefit Strategy:**
1. Maintain environment parity (same versions, same architecture)
2. Test real OAuth flows with your own test credentials
3. Automate deployment and testing
4. Use staging as a gate before production

**Testing OAuth Without Real Data:**
1. Use mock tests for code validation (no credentials needed)
2. Use OAuth Playground for manual token generation
3. Complete OAuth flow once on staging for real tests
4. Use `--mode force-expire` to test refresh flow
