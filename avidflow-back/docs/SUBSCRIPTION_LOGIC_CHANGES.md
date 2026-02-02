# Subscription Logic Changes - Node Visibility & Execution Limits

**Date:** December 2024  
**Author:** GitHub Copilot

---

## Summary of Changes

This update modifies the subscription logic to separate **node visibility** from **node execution limits**:

1. **Node Visibility**: Now unrestricted for all users
2. **Node Execution Limits**: Enforced during workflow execution with a default 2000 node quota

---

## 1. Node Visibility Changes (UI/API)

### What Changed
- **Disabled** subscription-based filtering for node listing APIs
- All users (free, paid, new, old) can now see **all available nodes** in the UI and APIs

### Files Modified

#### `config/node_plans.yaml`
```yaml
feature_flags:
  # DISABLED: Node visibility is unrestricted for all users
  enable_filtering: false
```

#### `services/dynamic_node_access.py`
- Updated module docstring to explain visibility is disabled
- When `enable_filtering: false`, the service returns all nodes for any user

#### `routers/node_types.py`
- Updated endpoint documentation to clarify visibility changes
- `node_filter.filter()` now returns all nodes (no-op when filtering disabled)

### Behavior
- `GET /node-types/` returns all node types regardless of user subscription
- `filter_nodes_for_user()` returns all nodes when filtering is disabled
- `can_user_access_node()` returns `True` for all nodes
- `get_user_accessible_nodes()` returns `{"*"}` (wildcard)

---

## 2. Node Execution Limits Changes

### What Changed
- **Re-enabled** node execution limit enforcement in workflow tasks
- **Added** default 2000 node limit for users without an active subscription
- **Auto-creates** a "default" subscription for users without one

### Files Modified

#### `database/crud.py` - `SubscriptionCRUD.check_and_consume_nodes_sync()`

```python
# Default node limit for users without an active subscription
DEFAULT_NODES_LIMIT = 2000

def check_and_consume_nodes_sync(db, user_id, nodes_to_consume):
    """
    Logic:
    1. If user has active subscription → use subscription's nodes_limit
    2. If user has NO subscription → create/use a default subscription with 2000 nodes
    3. Check if user has enough remaining nodes
    4. If yes, increment nodes_used and return success
    5. If no, return failure (execution blocked)
    """
```

#### `tasks/workflow.py` - `execute_workflow()`

```python
# EXECUTION LIMIT ENFORCEMENT
success, subscription = SubscriptionCRUD.check_and_consume_nodes_sync(
    session, user_id, total_nodes
)

if not success:
    # Block execution and return error
    return {
        "status": "error",
        "error_type": "subscription_limit",
        "nodes_required": total_nodes,
        "nodes_available": remaining,
    }
```

### Behavior

| User Type | Node Limit | Behavior |
|-----------|------------|----------|
| New user (no subscription) | 2000 | Auto-created "default" subscription |
| Existing user (no subscription) | 2000 | Auto-created "default" subscription |
| User with active subscription | Plan's `nodes_limit` | Uses existing subscription |
| User with expired subscription | 2000 | Falls back to default |

---

## 3. Database Impact

### No Schema Changes Required
The existing `Subscription` table already has the necessary columns:
- `nodes_used`: Tracks consumed nodes
- `nodes_limit`: Maximum allowed nodes
- `plan_type`: Identifies subscription type (now includes "default")

### New "default" Subscription Type
Users without an active subscription will automatically get a "default" subscription:
```python
Subscription(
    user_id=user_id,
    nodes_used=0,
    nodes_limit=2000,
    plan_type='default',
    is_active=True,
    end_date=datetime(2099, ...),  # Far future
)
```

---

## 4. Test Coverage

New test file: `tests/test_subscription_limits.py`

### Visibility Tests
- ✅ `test_filtering_is_disabled_in_config`
- ✅ `test_user_without_subscription_sees_all_nodes`
- ✅ `test_subscribed_user_sees_all_nodes`
- ✅ `test_no_nodes_hidden_due_to_plan_type`
- ✅ `test_can_access_any_node_when_filtering_disabled`
- ✅ `test_get_user_accessible_nodes_returns_wildcard`

### Execution Limit Tests
- ✅ `test_default_nodes_limit_constant`
- ✅ `test_subscription_remaining_nodes_calculation`
- ✅ `test_nodes_usage_increments_correctly`
- ✅ `test_execution_blocked_when_quota_exceeded`
- ✅ `test_execution_allowed_when_within_quota`

### Edge Cases
- ✅ `test_user_with_expired_subscription_treated_as_unsubscribed`
- ✅ `test_zero_nodes_workflow`
- ✅ `test_workflow_at_exact_limit`
- ✅ `test_workflow_one_over_limit`
- ✅ `test_sequential_node_consumption`

---

## 5. API Response Changes

### Node Types Listing (No Change to Response Format)
```json
GET /node-types/

// All users now receive the complete list of nodes
[
  {"id": 1, "type": "start", "name": "Start", ...},
  {"id": 2, "type": "ai_agent", "name": "AI Agent", ...},
  // ... all nodes
]
```

### Workflow Execution (New Error Response)
```json
POST /workflows/{id}/execute

// When quota exceeded:
{
  "status": "error",
  "error": "Node limit exceeded. Required: 15, Available: 5",
  "error_type": "subscription_limit",
  "nodes_required": 15,
  "nodes_available": 5
}
```

---

## 6. Backward Compatibility

| Scenario | Impact |
|----------|--------|
| Existing users without subscription | Safe: Get 2000 default nodes |
| Existing users with active subscription | No change: Use plan's limit |
| Existing workflows | No change: Continue working |
| Existing execution history | No change: Preserved |

---

## 7. Running Tests

```bash
# Run all subscription limit tests
python -m pytest tests/test_subscription_limits.py -v

# Run specific test classes
python -m pytest tests/test_subscription_limits.py::TestNodeVisibility -v
python -m pytest tests/test_subscription_limits.py::TestExecutionLimits -v
```

---

## 8. Configuration Options

### To Re-enable Visibility Filtering (Not Recommended)
Edit `config/node_plans.yaml`:
```yaml
feature_flags:
  enable_filtering: true  # Re-enables plan-based visibility
```

### To Change Default Node Limit
Edit `database/crud.py`:
```python
class SubscriptionCRUD:
    DEFAULT_NODES_LIMIT = 2000  # Change this value
```

---

## 9. Assumptions

1. All existing code paths that call `check_and_consume_nodes_sync` are in workflow execution context
2. The "default" plan_type is not used by any existing subscriptions
3. Users without any subscription should still be able to execute workflows (up to 2000 nodes)
4. Node counting is based on workflow definition, not actual executed nodes

---

## 10. Future Considerations

- Add user notification when approaching quota limit (e.g., at 80%)
- Add admin API to reset user's default subscription node count
- Consider adding monthly reset for default subscription quotas
- Add metrics/logging for quota exhaustion events
