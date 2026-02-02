"""
Node Access Service
==================
Dynamic node filtering based on user subscription status.
Configuration is loaded from config/node_access.yaml.

Design Pattern: Strategy Pattern with Configuration-driven rules
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence, Set, TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from database.models import User, DynamicNode

logger = logging.getLogger(__name__)


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class NodeAccessConfig:
    """Configuration loaded from node_access.yaml"""
    access_mode: str = "blacklist"  # "whitelist" or "blacklist"
    vip_exclusive_nodes: Set[str] = field(default_factory=set)
    base_nodes: Set[str] = field(default_factory=set)
    vip_exclusive_categories: Set[str] = field(default_factory=set)
    enable_vip_filtering: bool = True
    log_access_denials: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeAccessConfig":
        """Create config from dictionary (parsed YAML)"""
        feature_flags = data.get("feature_flags", {})
        return cls(
            access_mode=data.get("access_mode", "blacklist"),
            vip_exclusive_nodes=set(data.get("vip_exclusive_nodes", [])),
            base_nodes=set(data.get("base_nodes", [])),
            vip_exclusive_categories=set(data.get("vip_exclusive_categories", [])),
            enable_vip_filtering=feature_flags.get("enable_vip_filtering", True),
            log_access_denials=feature_flags.get("log_access_denials", False),
        )
    
    @classmethod
    def default(cls) -> "NodeAccessConfig":
        """Return default config (all nodes accessible)"""
        return cls(enable_vip_filtering=False)


class ConfigLoader:
    """Loads and caches node access configuration"""
    
    _instance: Optional["ConfigLoader"] = None
    _config: Optional[NodeAccessConfig] = None
    _config_path: Optional[Path] = None
    _last_modified: float = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_config(cls, force_reload: bool = False) -> NodeAccessConfig:
        """Get cached config or load from file"""
        instance = cls()
        
        if instance._config is None or force_reload:
            instance._load_config()
        else:
            # Check if file was modified (hot-reload support)
            instance._check_and_reload()
        
        return instance._config or NodeAccessConfig.default()
    
    @classmethod
    def reload(cls) -> NodeAccessConfig:
        """Force reload configuration"""
        return cls.get_config(force_reload=True)
    
    def _get_config_path(self) -> Path:
        """Determine config file path"""
        if self._config_path:
            return self._config_path
        
        # Try multiple locations
        possible_paths = [
            Path(__file__).parent.parent / "config" / "node_access.yaml",
            Path("config/node_access.yaml"),
            Path("/etc/n8n/node_access.yaml"),
        ]
        
        for path in possible_paths:
            if path.exists():
                self._config_path = path
                return path
        
        # Return default path even if doesn't exist
        self._config_path = possible_paths[0]
        return self._config_path
    
    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        config_path = self._get_config_path()
        
        try:
            if config_path.exists():
                with open(config_path, "r") as f:
                    data = yaml.safe_load(f) or {}
                self._config = NodeAccessConfig.from_dict(data)
                self._last_modified = config_path.stat().st_mtime
                logger.info(f"Loaded node access config from {config_path}")
            else:
                logger.warning(f"Config file not found: {config_path}, using defaults")
                self._config = NodeAccessConfig.default()
        except Exception as e:
            logger.error(f"Error loading node access config: {e}")
            self._config = NodeAccessConfig.default()
    
    def _check_and_reload(self) -> None:
        """Check if config file was modified and reload if needed"""
        config_path = self._get_config_path()
        try:
            if config_path.exists():
                current_mtime = config_path.stat().st_mtime
                if current_mtime > self._last_modified:
                    logger.info("Node access config changed, reloading...")
                    self._load_config()
        except Exception as e:
            logger.warning(f"Error checking config modification time: {e}")


# ==============================================================================
# Access Strategies (Strategy Pattern)
# ==============================================================================

class NodeAccessStrategy(Protocol):
    """Protocol for node access filtering strategies"""
    
    def can_access(self, node: "DynamicNode") -> bool:
        """Check if a node is accessible"""
        ...
    
    def filter_nodes(self, nodes: Sequence["DynamicNode"]) -> List["DynamicNode"]:
        """Filter list of nodes based on access rules"""
        ...


class BaseUserAccessStrategy:
    """Strategy for free/base tier users - limited access"""
    
    def __init__(self, config: NodeAccessConfig):
        self.config = config
    
    def can_access(self, node: "DynamicNode") -> bool:
        """Check if base user can access this node"""
        if not self.config.enable_vip_filtering:
            return True
        
        node_type = getattr(node, "type", None)
        node_category = getattr(node, "category", None)
        
        # Check category-based restrictions
        if node_category and node_category in self.config.vip_exclusive_categories:
            return False
        
        if self.config.access_mode == "blacklist":
            # Blacklist mode: block nodes in vip_exclusive_nodes
            return node_type not in self.config.vip_exclusive_nodes
        else:
            # Whitelist mode: only allow nodes in base_nodes
            if "*" in self.config.base_nodes:
                # Wildcard: allow all except VIP-exclusive
                return node_type not in self.config.vip_exclusive_nodes
            return node_type in self.config.base_nodes
    
    def filter_nodes(self, nodes: Sequence["DynamicNode"]) -> List["DynamicNode"]:
        """Filter nodes for base user access"""
        result = []
        for node in nodes:
            if self.can_access(node):
                result.append(node)
            elif self.config.log_access_denials:
                logger.debug(f"Access denied for base user: node type '{getattr(node, 'type', 'unknown')}'")
        return result


class VIPUserAccessStrategy:
    """Strategy for VIP/subscribed users - full access"""
    
    def __init__(self, config: NodeAccessConfig):
        self.config = config
    
    def can_access(self, node: "DynamicNode") -> bool:
        """VIP users can access all nodes"""
        return True
    
    def filter_nodes(self, nodes: Sequence["DynamicNode"]) -> List["DynamicNode"]:
        """VIP users see all nodes"""
        return list(nodes)


# ==============================================================================
# Main Service
# ==============================================================================

class NodeAccessService:
    """
    Service for managing node access based on user subscription status.
    
    Usage:
        service = NodeAccessService()
        accessible_nodes = service.get_accessible_nodes(user, all_nodes)
        
        # Or check single node
        if service.can_user_access_node(user, node):
            ...
    """
    
    def __init__(self, config: Optional[NodeAccessConfig] = None):
        self._config = config
    
    @property
    def config(self) -> NodeAccessConfig:
        """Get config (lazy load from file if not provided)"""
        if self._config is None:
            self._config = ConfigLoader.get_config()
        return self._config
    
    def _get_strategy(self, user: Optional["User"]) -> NodeAccessStrategy:
        """Get appropriate access strategy based on user status"""
        if user is None:
            return BaseUserAccessStrategy(self.config)
        
        # Check if user has active subscription
        has_subscription = False
        if hasattr(user, "active_subscription"):
            has_subscription = user.active_subscription is not None
        
        if has_subscription:
            return VIPUserAccessStrategy(self.config)
        return BaseUserAccessStrategy(self.config)
    
    def is_vip_user(self, user: Optional["User"]) -> bool:
        """Check if user has VIP access"""
        if user is None:
            return False
        if hasattr(user, "active_subscription"):
            return user.active_subscription is not None
        return False
    
    def can_user_access_node(self, user: Optional["User"], node: "DynamicNode") -> bool:
        """Check if a user can access a specific node"""
        strategy = self._get_strategy(user)
        return strategy.can_access(node)
    
    def get_accessible_nodes(
        self,
        user: Optional["User"],
        nodes: Sequence["DynamicNode"]
    ) -> List["DynamicNode"]:
        """Filter nodes based on user's access level"""
        strategy = self._get_strategy(user)
        return strategy.filter_nodes(nodes)
    
    def get_vip_exclusive_types(self) -> Set[str]:
        """Get set of VIP-exclusive node types (for UI hints)"""
        return self.config.vip_exclusive_nodes.copy()
    
    def is_node_type_vip_exclusive(self, node_type: str) -> bool:
        """Check if a node type is VIP-exclusive"""
        return node_type in self.config.vip_exclusive_nodes


# ==============================================================================
# Singleton accessor (for convenience)
# ==============================================================================

_service_instance: Optional[NodeAccessService] = None


def get_node_access_service() -> NodeAccessService:
    """Get singleton instance of NodeAccessService"""
    global _service_instance
    if _service_instance is None:
        _service_instance = NodeAccessService()
    return _service_instance


def reload_node_access_config() -> None:
    """Reload configuration from file"""
    global _service_instance
    ConfigLoader.reload()
    _service_instance = None  # Reset to pick up new config
    logger.info("Node access configuration reloaded")
