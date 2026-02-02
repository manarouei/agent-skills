"""
Dynamic Node Access Service
===========================
Per-user node access control based on subscription plans.

IMPORTANT (2025-12 Update):
===========================
Node VISIBILITY is now DISABLED for all users.
- All users (free, paid, new, old) can see ALL available nodes in the UI and APIs.
- The enable_filtering flag in config/node_plans.yaml is set to false.
- This service still exists for backward compatibility but filter_nodes_for_user()
  returns all nodes when filtering is disabled.

Node EXECUTION limits are enforced separately in tasks/workflow.py:
- Users without subscription get a default 2000 node limit.
- Users with subscription use their plan's nodes_limit.
- See SubscriptionCRUD.check_and_consume_nodes_sync() for enforcement logic.

Plans are defined in config/node_plans.yaml:
- "free": Base nodes for users without subscription
- "custom": Nodes defined per-user in subscription.node_overrides

Usage:
    service = DynamicNodeAccessService()
    
    # Get accessible nodes for a user
    nodes = service.get_user_accessible_nodes(user)
    
    # Filter a list of nodes (returns all when filtering disabled)
    filtered = service.filter_nodes_for_user(user, all_nodes)
    
    # Check single node access
    if service.can_user_access_node(user, node):
        ...
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Sequence, TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from database.models import User, DynamicNode, Subscription

logger = logging.getLogger(__name__)


# ==============================================================================
# Configuration Classes
# ==============================================================================

@dataclass
class PlanConfig:
    """Configuration for a single plan"""
    name: str
    display_name: str
    description: str = ""
    inherit: Optional[str] = None
    include_sets: List[str] = field(default_factory=list)
    nodes: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    all_access: bool = False


@dataclass
class NodePlansConfig:
    """Full configuration loaded from node_plans.yaml"""
    version: str = "1.0"
    node_sets: Dict[str, List[str]] = field(default_factory=dict)
    plans: Dict[str, PlanConfig] = field(default_factory=dict)
    unsubscribed_plan: str = "free"
    default_subscription_plan: str = "custom"
    enable_filtering: bool = True
    log_access_denials: bool = False
    cache_ttl_seconds: int = 300
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodePlansConfig":
        """Create config from parsed YAML"""
        defaults = data.get("defaults", {})
        feature_flags = data.get("feature_flags", {})
        
        # Parse node sets
        node_sets = data.get("node_sets", {})
        
        # Parse plans
        plans = {}
        for plan_name, plan_data in data.get("plans", {}).items():
            plans[plan_name] = PlanConfig(
                name=plan_name,
                display_name=plan_data.get("display_name", plan_name),
                description=plan_data.get("description", ""),
                inherit=plan_data.get("inherit"),
                include_sets=plan_data.get("include_sets", []),
                nodes=plan_data.get("nodes", []),
                exclude=plan_data.get("exclude", []),
                all_access=plan_data.get("all_access", False),
            )
        
        return cls(
            version=data.get("version", "1.0"),
            node_sets=node_sets,
            plans=plans,
            unsubscribed_plan=defaults.get("unsubscribed_plan", "free"),
            default_subscription_plan=defaults.get("default_subscription_plan", "custom"),
            enable_filtering=feature_flags.get("enable_filtering", True),
            log_access_denials=feature_flags.get("log_access_denials", False),
            cache_ttl_seconds=feature_flags.get("cache_ttl_seconds", 300),
        )
    
    @classmethod
    def default(cls) -> "NodePlansConfig":
        """Return default config (no filtering)"""
        return cls(enable_filtering=False)


# ==============================================================================
# Config Loader (Singleton with hot-reload)
# ==============================================================================

class PlanConfigLoader:
    """Loads and caches node plans configuration with hot-reload support"""
    
    _instance: Optional["PlanConfigLoader"] = None
    _config: Optional[NodePlansConfig] = None
    _config_path: Optional[Path] = None
    _last_modified: float = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_config(cls, force_reload: bool = False) -> NodePlansConfig:
        """Get cached config or load from file"""
        instance = cls()
        
        if instance._config is None or force_reload:
            instance._load_config()
        else:
            instance._check_and_reload()
        
        return instance._config or NodePlansConfig.default()
    
    @classmethod
    def reload(cls) -> NodePlansConfig:
        """Force reload configuration"""
        return cls.get_config(force_reload=True)
    
    def _get_config_path(self) -> Path:
        """Determine config file path"""
        if self._config_path:
            return self._config_path
        
        possible_paths = [
            Path(__file__).parent.parent / "config" / "node_plans.yaml",
            Path("config/node_plans.yaml"),
            Path("/etc/n8n/node_plans.yaml"),
        ]
        
        for path in possible_paths:
            if path.exists():
                self._config_path = path
                return path
        
        self._config_path = possible_paths[0]
        return self._config_path
    
    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        config_path = self._get_config_path()
        
        try:
            if config_path.exists():
                with open(config_path, "r") as f:
                    data = yaml.safe_load(f) or {}
                self._config = NodePlansConfig.from_dict(data)
                self._last_modified = config_path.stat().st_mtime
                logger.info(f"Loaded node plans config from {config_path}")
            else:
                logger.warning(f"Config file not found: {config_path}, using defaults")
                self._config = NodePlansConfig.default()
        except Exception as e:
            logger.error(f"Error loading node plans config: {e}")
            self._config = NodePlansConfig.default()
    
    def _check_and_reload(self) -> None:
        """Check if config file was modified and reload if needed"""
        config_path = self._get_config_path()
        try:
            if config_path.exists():
                current_mtime = config_path.stat().st_mtime
                if current_mtime > self._last_modified:
                    logger.info("Node plans config changed, reloading...")
                    self._load_config()
        except Exception as e:
            logger.warning(f"Error checking config modification time: {e}")


# ==============================================================================
# Main Service
# ==============================================================================

class DynamicNodeAccessService:
    """
    Service for managing per-user node access based on subscription plans.
    
    Access Logic:
    1. User without subscription → "free" plan nodes
    2. User with subscription → subscription.plan_type nodes
    3. If plan_type is "custom" → free plan + subscription.node_overrides.nodes
    4. Any plan can have additional overrides via node_overrides.add/remove
    """
    
    def __init__(self, config: Optional[NodePlansConfig] = None):
        self._config = config
        self._resolved_plans_cache: Dict[str, Set[str]] = {}
    
    @property
    def config(self) -> NodePlansConfig:
        """Get config (lazy load from file if not provided)"""
        if self._config is None:
            self._config = PlanConfigLoader.get_config()
        return self._config
    
    def _resolve_node_set(self, set_name: str) -> Set[str]:
        """Resolve a node set name to actual node types"""
        return set(self.config.node_sets.get(set_name, []))
    
    def _resolve_plan_nodes(self, plan_name: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """
        Resolve all nodes for a plan, including inheritance.
        Uses visited set to prevent circular inheritance.
        
        Falls back to 'free' plan if plan_name is not found.
        """
        if visited is None:
            visited = set()
        
        # Prevent circular inheritance
        if plan_name in visited:
            logger.warning(f"Circular inheritance detected for plan: {plan_name}")
            return set()
        visited.add(plan_name)
        
        # Check cache
        if plan_name in self._resolved_plans_cache:
            return self._resolved_plans_cache[plan_name].copy()
        
        plan = self.config.plans.get(plan_name)
        if not plan:
            # Fallback to free plan for unknown plan types (e.g., "gold", "silver", "bronze")
            fallback_plan = self.config.unsubscribed_plan  # "free"
            if plan_name != fallback_plan and fallback_plan in self.config.plans:
                logger.warning(f"Plan '{plan_name}' not found, falling back to '{fallback_plan}' plan")
                return self._resolve_plan_nodes(fallback_plan, visited)
            logger.warning(f"Plan '{plan_name}' not found, using empty set")
            return set()
        
        # All access = all nodes
        if plan.all_access:
            return {"*"}
        
        nodes: Set[str] = set()
        
        # 1. Inherit from parent plan
        if plan.inherit:
            nodes |= self._resolve_plan_nodes(plan.inherit, visited)
        
        # 2. Add nodes from include_sets
        for set_name in plan.include_sets:
            nodes |= self._resolve_node_set(set_name)
        
        # 3. Add individual nodes
        nodes |= set(plan.nodes)
        
        # 4. Remove excluded nodes
        nodes -= set(plan.exclude)
        
        # Cache the result
        self._resolved_plans_cache[plan_name] = nodes.copy()
        
        return nodes
    
    def get_plan_for_user(self, user: Optional["User"]) -> str:
        """Determine which plan applies to a user"""
        if user is None:
            return self.config.unsubscribed_plan
        
        subscription = self._get_active_subscription(user)
        if subscription is None:
            return self.config.unsubscribed_plan
        
        # Get plan_type, fallback to default if None or empty
        plan_type = getattr(subscription, 'plan_type', None)
        if not plan_type:  # None or empty string
            return self.config.default_subscription_plan
        return plan_type
    
    def _get_active_subscription(self, user: "User") -> Optional["Subscription"]:
        """Get user's active subscription"""
        if hasattr(user, "active_subscription"):
            return user.active_subscription
        return None
    
    def _get_node_overrides(self, user: "User") -> Dict[str, Any]:
        """Get user's node overrides from subscription"""
        subscription = self._get_active_subscription(user)
        if subscription is None:
            return {}
        return getattr(subscription, 'node_overrides', None) or {}
    
    def get_user_accessible_nodes(self, user: Optional["User"]) -> Set[str]:
        """
        Get all node types accessible to a specific user.
        
        Returns a set of node type strings, or {"*"} for all access.
        """
        if not self.config.enable_filtering:
            return {"*"}
        
        plan_name = self.get_plan_for_user(user)
        
        # Get base nodes from plan
        nodes = self._resolve_plan_nodes(plan_name)
        
        # If all access, return early
        if "*" in nodes:
            return {"*"}
        
        # Apply user-specific overrides
        if user is not None:
            overrides = self._get_node_overrides(user)
            
            # For "custom" plan: node_overrides.nodes is the primary source
            if plan_name == "custom" and "nodes" in overrides:
                custom_nodes = set(overrides.get("nodes", []))
                nodes |= custom_nodes
            
            # For any plan: add/remove overrides
            nodes |= set(overrides.get("add", []))
            nodes -= set(overrides.get("remove", []))
        
        return nodes
    
    def can_user_access_node(self, user: Optional["User"], node: "DynamicNode") -> bool:
        """Check if a user can access a specific node"""
        if not self.config.enable_filtering:
            return True
        
        accessible = self.get_user_accessible_nodes(user)
        
        # All access
        if "*" in accessible:
            return True
        
        node_type = getattr(node, "type", None)
        if node_type is None:
            return False
        
        can_access = node_type in accessible
        
        if not can_access and self.config.log_access_denials:
            logger.debug(f"Access denied for user {getattr(user, 'id', 'anonymous')}: node '{node_type}'")
        
        return can_access
    
    def filter_nodes_for_user(
        self, 
        user: Optional["User"], 
        nodes: Sequence["DynamicNode"]
    ) -> List["DynamicNode"]:
        """Filter a list of nodes based on user's access"""
        if not self.config.enable_filtering:
            return list(nodes)
        
        accessible = self.get_user_accessible_nodes(user)
        
        # All access
        if "*" in accessible:
            return list(nodes)
        
        result = []
        for node in nodes:
            node_type = getattr(node, "type", None)
            if node_type and node_type in accessible:
                result.append(node)
            elif self.config.log_access_denials:
                logger.debug(f"Filtered out node '{node_type}' for user {getattr(user, 'id', 'anonymous')}")
        
        return result
    
    def is_subscribed_user(self, user: Optional["User"]) -> bool:
        """Check if user has an active subscription"""
        if user is None:
            return False
        return self._get_active_subscription(user) is not None
    
    def get_user_plan_info(self, user: Optional["User"]) -> Dict[str, Any]:
        """Get detailed plan info for a user (useful for API responses)"""
        plan_name = self.get_plan_for_user(user)
        plan = self.config.plans.get(plan_name)
        
        return {
            "plan_type": plan_name,
            "display_name": plan.display_name if plan else plan_name,
            "description": plan.description if plan else "",
            "is_subscribed": self.is_subscribed_user(user),
            "node_count": len(self.get_user_accessible_nodes(user)),
            "has_all_access": "*" in self.get_user_accessible_nodes(user),
        }


# ==============================================================================
# Singleton accessor
# ==============================================================================

_service_instance: Optional[DynamicNodeAccessService] = None


def get_dynamic_node_access_service() -> DynamicNodeAccessService:
    """Get singleton instance of DynamicNodeAccessService"""
    global _service_instance
    if _service_instance is None:
        _service_instance = DynamicNodeAccessService()
    return _service_instance


def reload_node_plans_config() -> None:
    """Reload configuration from file"""
    global _service_instance
    PlanConfigLoader.reload()
    _service_instance = None
    logger.info("Node plans configuration reloaded")
