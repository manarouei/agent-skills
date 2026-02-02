# VIP Node Access Feature - Production Deployment Guide

## Overview

This feature implements tiered node access:
- **Free users**: See only base nodes (configurable list)
- **VIP users** (with valid subscription): See all nodes

VIP status is determined by `user.active_subscription` which checks:
- User has at least one subscription
- Subscription `is_active = True`
- Subscription `end_date > now()` (not expired)

---

## Files Changed/Created

### 1. NEW FILE: `config/node_access.yaml`
**Purpose**: Configuration file for VIP/base node definitions (hot-reloadable)

```yaml
# Node Access Configuration
access_mode: "whitelist"  # "whitelist" or "blacklist"

# When whitelist: only these nodes available to free users
base_nodes:
  - "start"
  - "end"
  - "set"
  - "if"
  - "switch"
  - "merge"
  - "iterator"
  - "filter"
  - "chat"
  - "telegram"
  - "gmail"
  - "gmail_trigger"
  - "googleCalendar"
  - "googleDocs"
  - "googleSheets"
  - "googleDrive"
  - "googleForm"
  - "http_request"
  - "stickyNote"

vip_exclusive_nodes: []  # Used in blacklist modwhat does it file do here?...e
vip_exclusive_categories: []

feature_flags:
  enable_vip_filtering: true
  log_access_denials: false
```

---

### 2. NEW FILE: `services/node_access.py`
**Purpose**: Core service for node access filtering using Strategy Pattern

**Key Classes**:
- `NodeAccessConfig`: Dataclass for config
- `ConfigLoader`: Singleton that loads/caches YAML config with hot-reload
- `BaseUserAccessStrategy`: Filters nodes for free users
- `VIPUserAccessStrategy`: Returns all nodes for VIP users  
- `NodeAccessService`: Main service class

**No database changes required.**

---

### 3. MODIFIED: `auth/dependencies.py`

#### Change 1: Added imports (line 6, 8)
```python
from sqlalchemy.orm import selectinload  # NEW
from database.models import User, Subscription  # MODIFIED: added Subscription
```

#### Change 2: Eager load subscriptions in `get_current_user()` (around line 49-53)
**Before:**
```python
result = await db.execute(select(User).where(User.id == token_data.sub))
```

**After:**
```python
result = await db.execute(
    select(User)
    .options(selectinload(User.subscriptions))  # Eager load to avoid lazy-load error
    .where(User.id == token_data.sub)
)
```

**Why**: Without eager loading, accessing `user.active_subscription` triggers a lazy-load 
which fails in async context (greenlet error).

#### Change 3: Added new dependencies (after `get_current_active_user`)
```python
# ==============================================================================
# Node Access Dependencies
# ==============================================================================

def get_node_access_service():
    """Dependency that provides the NodeAccessService."""
    from services.node_access import NodeAccessService
    return NodeAccessService()


class NodeAccessFilter:
    """Dependency class for filtering nodes based on user access."""
    
    def __init__(self, current_user: User = Depends(get_current_user)):
        from services.node_access import NodeAccessService
        self.user = current_user
        self.service = NodeAccessService()
    
    def filter(self, nodes):
        """Filter nodes based on user's access level"""
        return self.service.get_accessible_nodes(self.user, nodes)
    
    def can_access(self, node) -> bool:
        """Check if user can access a specific node"""
        return self.service.can_user_access_node(self.user, node)
    
    @property
    def is_vip(self) -> bool:
        """Check if current user is VIP"""
        return self.service.is_vip_user(self.user)
    
    @property
    def vip_exclusive_types(self):
        """Get set of VIP-exclusive node types"""
        return self.service.get_vip_exclusive_types()
```

---

### 4. MODIFIED: `routers/node_types.py`

#### Change 1: Added import (line 6)
```python
from auth.dependencies import get_current_user, NodeAccessFilter  # MODIFIED: added NodeAccessFilter
```

#### Change 2: Modified `list_node_types()` endpoint

**Added parameter:**
```python
node_filter: NodeAccessFilter = Depends(NodeAccessFilter),
```

**Added filtering logic after getting all nodes:**
```python
# Get all nodes from database
all_nodes = await crud.DynamicNodeCRUD.get_all_nodes(db, active_only=active_only)

# Apply VIP/Base access filtering
nodes = node_filter.filter(all_nodes)

logger.debug(
    f"User {current_user.id} ({'VIP' if node_filter.is_vip else 'Base'}): "
    f"{len(nodes)}/{len(all_nodes)} nodes accessible"
)
```

---

### 5. MODIFIED: `models/node.py`

#### Change: Make `icon` and `category` fields optional

**Before:**
```python
category: str
icon: str
```

**After:**
```python
category: Optional[str] = None
icon: Optional[str] = None
```

**Why**: Some nodes in DB have `NULL` icon/category values, causing Pydantic validation errors.

---

### 6. MODIFIED: `commands/sync_nodes.py` (Optional - for syncing nodes to DB)

#### Changes:
1. Fixed async session handling (use `async_sessionmaker` instead of generator)
2. Added duplicate type detection
3. Fixed version type conversion (string "1.0" → int 1)
4. Removed icon setting (FileType field incompatible with strings)

---

## Deployment Steps

### Step 1: Backup
```bash
# Backup current files
cp auth/dependencies.py auth/dependencies.py.bak
cp routers/node_types.py routers/node_types.py.bak
cp models/node.py models/node.py.bak
```

### Step 2: Create new files
```bash
# Create config directory if not exists
mkdir -p config

# Copy node_access.yaml to config/
# Copy services/node_access.py to services/
```

### Step 3: Apply changes to existing files

Apply the changes documented above to:
- `auth/dependencies.py`
- `routers/node_types.py`  
- `models/node.py`

### Step 4: Install dependencies (if not already installed)
```bash
pip install pyyaml  # For YAML config loading
```

### Step 5: Sync nodes to database (if needed)
```bash
python manage.py sync_nodes --force
```

### Step 6: Restart server
```bash
# Restart your FastAPI server
```

---

## Testing

### Test 1: Free user (no subscription)
```bash
curl -X GET 'http://localhost:8000/api/node-types/' \
  -H 'Authorization: Bearer <FREE_USER_TOKEN>'
# Should return ~17-20 nodes (base nodes only)
```

### Test 2: VIP user (valid subscription)
```bash
curl -X GET 'http://localhost:8000/api/node-types/' \
  -H 'Authorization: Bearer <VIP_USER_TOKEN>'
# Should return all nodes (50+)
```

### Test 3: Verify specific user
```python
# In Python shell
from services.node_access import NodeAccessService
service = NodeAccessService()
print(service.is_vip_user(user))  # True/False
```

---

## Configuration

### To change free nodes:
Edit `config/node_access.yaml` - changes auto-reload, no restart needed.

### To disable VIP filtering temporarily:
```yaml
feature_flags:
  enable_vip_filtering: false  # All users see all nodes
```

### To switch to blacklist mode:
```yaml
access_mode: "blacklist"
vip_exclusive_nodes:
  - "ai_agent"
  - "deepseek"
  # ... nodes only VIP can see
```

---

## Rollback

To rollback, restore the backup files:
```bash
cp auth/dependencies.py.bak auth/dependencies.py
cp routers/node_types.py.bak routers/node_types.py
cp models/node.py.bak models/node.py
# Restart server
```

---

## Production Readiness Checklist

- [x] No database migrations required
- [x] Hot-reloadable configuration
- [x] Graceful fallback if config missing
- [x] Eager loading prevents async errors
- [x] Strategy pattern for clean separation
- [x] Logging for debugging
- [x] Backward compatible (existing endpoints unchanged)
- [x] Unit tests (`tests/test_node_access.py` - 39 tests)
- [x] Load testing (`tests/load_test_node_access.py` - performance benchmarks)

---

## Running Tests

### Unit Tests

Run all 39 unit tests:
```bash
# Using unittest (no pytest required)
python tests/test_node_access.py

# Or with pytest if available
pytest tests/test_node_access.py -v
```

Test coverage:
- `TestNodeAccessConfig` - Configuration dataclass tests
- `TestConfigLoader` - YAML loading and hot-reload tests
- `TestBaseUserAccessStrategy` - Free user filtering logic
- `TestVIPUserAccessStrategy` - VIP full access
- `TestNodeAccessService` - Main service tests
- `TestNodeAccessFilter` - FastAPI dependency tests
- `TestNodeAccessIntegration` - End-to-end flow tests
- `TestEdgeCases` - Edge cases and error handling

### Load/Performance Tests

Quick performance test (no dependencies):
```bash
python tests/load_test_node_access.py --quick
```

Full HTTP load test with Locust:
```bash
# Install locust first
pip install locust

# Set auth tokens
export FREE_USER_TOKEN='your-free-user-jwt'
export VIP_USER_TOKEN='your-vip-user-jwt'

# Run with web UI
locust -f tests/load_test_node_access.py --host=http://localhost:8000

# Or headless
locust -f tests/load_test_node_access.py --host=http://localhost:8000 \
    --users 100 --spawn-rate 10 --run-time 60s --headless
```

Performance benchmarks (from quick test):
- Free user filtering: ~0.02ms per call (~48,000 ops/s)
- VIP user (no filter): ~0.001ms per call (~1,150,000 ops/s)
- Filtering overhead: negligible for production use

---

## Architecture Diagram

```
Request → get_current_user() → User (with subscriptions loaded)
                                    ↓
                            NodeAccessFilter
                                    ↓
                            NodeAccessService
                                    ↓
                    ┌───────────────┴───────────────┐
                    ↓                               ↓
            BaseUserStrategy              VIPUserStrategy
            (filter by config)            (return all)
                    ↓                               ↓
                    └───────────────┬───────────────┘
                                    ↓
                            Filtered nodes → Response
```
