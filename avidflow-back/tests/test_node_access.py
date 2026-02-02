#!/usr/bin/env python3
"""
Unit Tests for VIP Node Access Feature
======================================

Tests cover:
1. NodeAccessConfig - Configuration dataclass
2. ConfigLoader - YAML loading and hot-reload
3. BaseUserAccessStrategy - Free user access rules
4. VIPUserAccessStrategy - VIP user access rules
5. NodeAccessService - Main service class
6. NodeAccessFilter dependency - FastAPI integration

Run with: pytest tests/test_node_access.py -v
Or: python tests/test_node_access.py
"""

import sys
import os
import tempfile
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
from unittest.mock import MagicMock, patch, PropertyMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==============================================================================
# Test Fixtures / Mock Objects
# ==============================================================================

@dataclass
class MockDynamicNode:
    """Mock DynamicNode for testing"""
    id: int
    type: str
    name: str
    category: Optional[str] = None
    is_active: bool = True


@dataclass 
class MockSubscription:
    """Mock Subscription for testing"""
    id: int
    is_active: bool = True
    is_expired: bool = False
    
    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired


class MockUser:
    """Mock User for testing with subscription support"""
    
    def __init__(self, user_id: int, subscriptions: Optional[List[MockSubscription]] = None):
        self.id = user_id
        self.subscriptions = subscriptions or []
    
    @property
    def active_subscription(self) -> Optional[MockSubscription]:
        """Returns first valid subscription or None"""
        for sub in self.subscriptions:
            if sub.is_valid:
                return sub
        return None


def create_test_nodes() -> List[MockDynamicNode]:
    """Create a set of test nodes for filtering tests"""
    return [
        MockDynamicNode(1, "start", "Start", "core"),
        MockDynamicNode(2, "end", "End", "core"),
        MockDynamicNode(3, "if", "If", "core"),
        MockDynamicNode(4, "set", "Set", "core"),
        MockDynamicNode(5, "http_request", "HTTP Request", "network"),
        MockDynamicNode(6, "gmail", "Gmail", "communication"),
        MockDynamicNode(7, "telegram", "Telegram", "communication"),
        MockDynamicNode(8, "ai_agent", "AI Agent", "ai"),
        MockDynamicNode(9, "deepseek", "DeepSeek", "ai"),
        MockDynamicNode(10, "openai", "OpenAI", "ai"),
        MockDynamicNode(11, "custom_vip", "Custom VIP", "premium"),
    ]


# ==============================================================================
# NodeAccessConfig Tests
# ==============================================================================

class TestNodeAccessConfig(unittest.TestCase):
    """Tests for NodeAccessConfig dataclass"""
    
    def test_default_values(self):
        """Test default configuration values"""
        from services.node_access import NodeAccessConfig
        
        config = NodeAccessConfig()
        
        self.assertEqual(config.access_mode, "blacklist")
        self.assertEqual(config.vip_exclusive_nodes, set())
        self.assertEqual(config.base_nodes, set())
        self.assertEqual(config.vip_exclusive_categories, set())
        self.assertTrue(config.enable_vip_filtering)
        self.assertFalse(config.log_access_denials)
    
    def test_from_dict_whitelist_mode(self):
        """Test creating config from dict in whitelist mode"""
        from services.node_access import NodeAccessConfig
        
        data = {
            "access_mode": "whitelist",
            "base_nodes": ["start", "end", "if", "set"],
            "vip_exclusive_nodes": [],
            "vip_exclusive_categories": ["premium"],
            "feature_flags": {
                "enable_vip_filtering": True,
                "log_access_denials": True
            }
        }
        
        config = NodeAccessConfig.from_dict(data)
        
        self.assertEqual(config.access_mode, "whitelist")
        self.assertEqual(config.base_nodes, {"start", "end", "if", "set"})
        self.assertEqual(config.vip_exclusive_categories, {"premium"})
        self.assertTrue(config.enable_vip_filtering)
        self.assertTrue(config.log_access_denials)
    
    def test_from_dict_blacklist_mode(self):
        """Test creating config from dict in blacklist mode"""
        from services.node_access import NodeAccessConfig
        
        data = {
            "access_mode": "blacklist",
            "vip_exclusive_nodes": ["ai_agent", "deepseek", "openai"],
            "base_nodes": [],
            "feature_flags": {
                "enable_vip_filtering": True
            }
        }
        
        config = NodeAccessConfig.from_dict(data)
        
        self.assertEqual(config.access_mode, "blacklist")
        self.assertEqual(config.vip_exclusive_nodes, {"ai_agent", "deepseek", "openai"})
        self.assertTrue(config.enable_vip_filtering)
    
    def test_from_dict_empty_data(self):
        """Test creating config from empty dict uses defaults"""
        from services.node_access import NodeAccessConfig
        
        config = NodeAccessConfig.from_dict({})
        
        self.assertEqual(config.access_mode, "blacklist")
        self.assertEqual(config.base_nodes, set())
    
    def test_default_factory(self):
        """Test default() class method"""
        from services.node_access import NodeAccessConfig
        
        config = NodeAccessConfig.default()
        
        self.assertFalse(config.enable_vip_filtering)  # Disabled by default


# ==============================================================================
# ConfigLoader Tests
# ==============================================================================

class TestConfigLoader(unittest.TestCase):
    """Tests for ConfigLoader singleton"""
    
    def setUp(self):
        """Reset ConfigLoader singleton state before each test"""
        from services.node_access import ConfigLoader
        ConfigLoader._instance = None
        ConfigLoader._config = None
        ConfigLoader._config_path = None
        ConfigLoader._last_modified = 0
    
    def test_singleton_pattern(self):
        """Test that ConfigLoader is a singleton"""
        from services.node_access import ConfigLoader
        
        loader1 = ConfigLoader()
        loader2 = ConfigLoader()
        
        self.assertIs(loader1, loader2)
    
    def test_load_config_from_file(self):
        """Test loading configuration from YAML file"""
        from services.node_access import ConfigLoader, NodeAccessConfig
        
        yaml_content = """
access_mode: whitelist
base_nodes:
  - start
  - end
  - gmail
feature_flags:
  enable_vip_filtering: true
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            # Patch the config path
            loader = ConfigLoader()
            loader._config_path = Path(temp_path)
            loader._load_config()
            
            config = loader._config
            self.assertIsNotNone(config)
            self.assertEqual(config.access_mode, "whitelist")
            self.assertEqual(config.base_nodes, {"start", "end", "gmail"})
        finally:
            os.unlink(temp_path)
    
    def test_hot_reload_on_file_change(self):
        """Test that config reloads when file is modified"""
        from services.node_access import ConfigLoader
        
        yaml_content_v1 = """
access_mode: whitelist
base_nodes:
  - start
  - end
"""
        yaml_content_v2 = """
access_mode: whitelist
base_nodes:
  - start
  - end
  - gmail
  - telegram
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content_v1)
            temp_path = f.name
        
        try:
            loader = ConfigLoader()
            loader._config_path = Path(temp_path)
            
            # Load initial config
            config1 = ConfigLoader.get_config(force_reload=True)
            self.assertEqual(len(config1.base_nodes), 2)
            
            # Wait a bit and modify file
            time.sleep(0.1)
            with open(temp_path, 'w') as f:
                f.write(yaml_content_v2)
            
            # Trigger hot-reload check
            config2 = ConfigLoader.get_config()
            self.assertEqual(len(config2.base_nodes), 4)
        finally:
            os.unlink(temp_path)
    
    def test_missing_config_file_uses_defaults(self):
        """Test that missing config file returns default config"""
        from services.node_access import ConfigLoader
        
        loader = ConfigLoader()
        loader._config_path = Path("/nonexistent/path/config.yaml")
        loader._load_config()
        
        config = loader._config
        self.assertIsNotNone(config)
        self.assertFalse(config.enable_vip_filtering)  # Default has filtering disabled
    
    def test_force_reload(self):
        """Test force reload functionality"""
        from services.node_access import ConfigLoader
        
        # Get initial config
        config1 = ConfigLoader.get_config()
        
        # Force reload should return config
        config2 = ConfigLoader.reload()
        
        self.assertIsNotNone(config2)


# ==============================================================================
# BaseUserAccessStrategy Tests
# ==============================================================================

class TestBaseUserAccessStrategy(unittest.TestCase):
    """Tests for BaseUserAccessStrategy (free user filtering)"""
    
    def test_whitelist_mode_allows_base_nodes(self):
        """Test whitelist mode allows only base nodes"""
        from services.node_access import BaseUserAccessStrategy, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start", "end", "if", "set"},
            enable_vip_filtering=True
        )
        strategy = BaseUserAccessStrategy(config)
        
        nodes = create_test_nodes()
        filtered = strategy.filter_nodes(nodes)
        
        # Should only have the 4 base nodes
        filtered_types = {n.type for n in filtered}
        self.assertEqual(filtered_types, {"start", "end", "if", "set"})
    
    def test_whitelist_mode_wildcard(self):
        """Test whitelist mode with wildcard allows all except VIP-exclusive"""
        from services.node_access import BaseUserAccessStrategy, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"*"},  # Wildcard
            vip_exclusive_nodes={"ai_agent", "deepseek"},
            enable_vip_filtering=True
        )
        strategy = BaseUserAccessStrategy(config)
        
        nodes = create_test_nodes()
        filtered = strategy.filter_nodes(nodes)
        
        # Should have all except ai_agent and deepseek
        filtered_types = {n.type for n in filtered}
        self.assertNotIn("ai_agent", filtered_types)
        self.assertNotIn("deepseek", filtered_types)
        self.assertIn("start", filtered_types)
        self.assertIn("openai", filtered_types)
    
    def test_blacklist_mode_blocks_vip_exclusive(self):
        """Test blacklist mode blocks VIP-exclusive nodes"""
        from services.node_access import BaseUserAccessStrategy, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="blacklist",
            vip_exclusive_nodes={"ai_agent", "deepseek", "openai"},
            enable_vip_filtering=True
        )
        strategy = BaseUserAccessStrategy(config)
        
        nodes = create_test_nodes()
        filtered = strategy.filter_nodes(nodes)
        
        # Should have all except the 3 VIP-exclusive nodes
        filtered_types = {n.type for n in filtered}
        self.assertNotIn("ai_agent", filtered_types)
        self.assertNotIn("deepseek", filtered_types)
        self.assertNotIn("openai", filtered_types)
        self.assertIn("start", filtered_types)
        self.assertIn("gmail", filtered_types)
    
    def test_category_based_restriction(self):
        """Test category-based VIP restrictions"""
        from services.node_access import BaseUserAccessStrategy, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="blacklist",
            vip_exclusive_categories={"ai", "premium"},
            enable_vip_filtering=True
        )
        strategy = BaseUserAccessStrategy(config)
        
        nodes = create_test_nodes()
        filtered = strategy.filter_nodes(nodes)
        
        # Should exclude all nodes in "ai" and "premium" categories
        filtered_types = {n.type for n in filtered}
        self.assertNotIn("ai_agent", filtered_types)  # ai category
        self.assertNotIn("deepseek", filtered_types)  # ai category
        self.assertNotIn("openai", filtered_types)  # ai category
        self.assertNotIn("custom_vip", filtered_types)  # premium category
        self.assertIn("gmail", filtered_types)  # communication category
    
    def test_filtering_disabled_allows_all(self):
        """Test that disabled filtering allows all nodes"""
        from services.node_access import BaseUserAccessStrategy, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start"},  # Only one node
            enable_vip_filtering=False  # But filtering is disabled
        )
        strategy = BaseUserAccessStrategy(config)
        
        nodes = create_test_nodes()
        filtered = strategy.filter_nodes(nodes)
        
        # All nodes should pass through
        self.assertEqual(len(filtered), len(nodes))
    
    def test_can_access_single_node(self):
        """Test can_access method for single node"""
        from services.node_access import BaseUserAccessStrategy, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start", "end"},
            enable_vip_filtering=True
        )
        strategy = BaseUserAccessStrategy(config)
        
        start_node = MockDynamicNode(1, "start", "Start")
        ai_node = MockDynamicNode(8, "ai_agent", "AI Agent")
        
        self.assertTrue(strategy.can_access(start_node))
        self.assertFalse(strategy.can_access(ai_node))


# ==============================================================================
# VIPUserAccessStrategy Tests
# ==============================================================================

class TestVIPUserAccessStrategy(unittest.TestCase):
    """Tests for VIPUserAccessStrategy (VIP user - full access)"""
    
    def test_vip_can_access_all_nodes(self):
        """Test VIP strategy returns all nodes"""
        from services.node_access import VIPUserAccessStrategy, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start"},  # Very restrictive
            vip_exclusive_nodes={"ai_agent"},
            enable_vip_filtering=True
        )
        strategy = VIPUserAccessStrategy(config)
        
        nodes = create_test_nodes()
        filtered = strategy.filter_nodes(nodes)
        
        # VIP should get all nodes
        self.assertEqual(len(filtered), len(nodes))
    
    def test_vip_can_access_any_single_node(self):
        """Test VIP can_access returns True for any node"""
        from services.node_access import VIPUserAccessStrategy, NodeAccessConfig
        
        config = NodeAccessConfig(
            vip_exclusive_nodes={"ai_agent", "deepseek"},
            enable_vip_filtering=True
        )
        strategy = VIPUserAccessStrategy(config)
        
        # All nodes should be accessible
        for node in create_test_nodes():
            self.assertTrue(strategy.can_access(node))


# ==============================================================================
# NodeAccessService Tests
# ==============================================================================

class TestNodeAccessService(unittest.TestCase):
    """Tests for NodeAccessService"""
    
    def test_is_vip_user_with_valid_subscription(self):
        """Test VIP detection for user with valid subscription"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(enable_vip_filtering=True)
        service = NodeAccessService(config=config)
        
        # User with valid subscription
        vip_user = MockUser(1, [MockSubscription(1, is_active=True, is_expired=False)])
        
        self.assertTrue(service.is_vip_user(vip_user))
    
    def test_is_vip_user_with_expired_subscription(self):
        """Test VIP detection for user with expired subscription"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(enable_vip_filtering=True)
        service = NodeAccessService(config=config)
        
        # User with expired subscription
        expired_user = MockUser(2, [MockSubscription(1, is_active=True, is_expired=True)])
        
        self.assertFalse(service.is_vip_user(expired_user))
    
    def test_is_vip_user_with_inactive_subscription(self):
        """Test VIP detection for user with inactive subscription"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(enable_vip_filtering=True)
        service = NodeAccessService(config=config)
        
        # User with inactive subscription
        inactive_user = MockUser(3, [MockSubscription(1, is_active=False, is_expired=False)])
        
        self.assertFalse(service.is_vip_user(inactive_user))
    
    def test_is_vip_user_without_subscription(self):
        """Test VIP detection for user without subscription"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(enable_vip_filtering=True)
        service = NodeAccessService(config=config)
        
        # User without subscription
        free_user = MockUser(4, [])
        
        self.assertFalse(service.is_vip_user(free_user))
    
    def test_is_vip_user_none(self):
        """Test VIP detection for None user"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        service = NodeAccessService()
        
        self.assertFalse(service.is_vip_user(None))
    
    def test_get_accessible_nodes_for_free_user(self):
        """Test node filtering for free user"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start", "end", "if", "set"},
            enable_vip_filtering=True
        )
        service = NodeAccessService(config=config)
        
        free_user = MockUser(1, [])
        nodes = create_test_nodes()
        
        accessible = service.get_accessible_nodes(free_user, nodes)
        
        self.assertEqual(len(accessible), 4)
        accessible_types = {n.type for n in accessible}
        self.assertEqual(accessible_types, {"start", "end", "if", "set"})
    
    def test_get_accessible_nodes_for_vip_user(self):
        """Test node filtering for VIP user"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start", "end"},  # Very restrictive
            enable_vip_filtering=True
        )
        service = NodeAccessService(config=config)
        
        vip_user = MockUser(1, [MockSubscription(1, is_active=True, is_expired=False)])
        nodes = create_test_nodes()
        
        accessible = service.get_accessible_nodes(vip_user, nodes)
        
        # VIP gets all nodes
        self.assertEqual(len(accessible), len(nodes))
    
    def test_can_user_access_node(self):
        """Test single node access check"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="blacklist",
            vip_exclusive_nodes={"ai_agent"},
            enable_vip_filtering=True
        )
        service = NodeAccessService(config=config)
        
        free_user = MockUser(1, [])
        vip_user = MockUser(2, [MockSubscription(1)])
        ai_node = MockDynamicNode(8, "ai_agent", "AI Agent")
        start_node = MockDynamicNode(1, "start", "Start")
        
        # Free user can't access VIP node
        self.assertFalse(service.can_user_access_node(free_user, ai_node))
        self.assertTrue(service.can_user_access_node(free_user, start_node))
        
        # VIP user can access everything
        self.assertTrue(service.can_user_access_node(vip_user, ai_node))
        self.assertTrue(service.can_user_access_node(vip_user, start_node))
    
    def test_get_vip_exclusive_types(self):
        """Test getting VIP exclusive types"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(
            vip_exclusive_nodes={"ai_agent", "deepseek", "openai"}
        )
        service = NodeAccessService(config=config)
        
        exclusive = service.get_vip_exclusive_types()
        
        self.assertEqual(exclusive, {"ai_agent", "deepseek", "openai"})
    
    def test_is_node_type_vip_exclusive(self):
        """Test checking if node type is VIP exclusive"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(
            vip_exclusive_nodes={"ai_agent", "deepseek"}
        )
        service = NodeAccessService(config=config)
        
        self.assertTrue(service.is_node_type_vip_exclusive("ai_agent"))
        self.assertTrue(service.is_node_type_vip_exclusive("deepseek"))
        self.assertFalse(service.is_node_type_vip_exclusive("start"))
        self.assertFalse(service.is_node_type_vip_exclusive("gmail"))


# ==============================================================================
# NodeAccessFilter Dependency Tests
# ==============================================================================

class TestNodeAccessFilter(unittest.TestCase):
    """Tests for NodeAccessFilter FastAPI dependency"""
    
    def test_filter_method(self):
        """Test filter method delegates to service"""
        from auth.dependencies import NodeAccessFilter
        from services.node_access import NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start", "end"},
            enable_vip_filtering=True
        )
        
        # Create filter with mock user (free)
        free_user = MockUser(1, [])
        filter_instance = NodeAccessFilter.__new__(NodeAccessFilter)
        filter_instance.user = free_user
        filter_instance.service = MagicMock()
        filter_instance.service.get_accessible_nodes.return_value = [
            MockDynamicNode(1, "start", "Start"),
            MockDynamicNode(2, "end", "End")
        ]
        
        nodes = create_test_nodes()
        result = filter_instance.filter(nodes)
        
        filter_instance.service.get_accessible_nodes.assert_called_once()
        self.assertEqual(len(result), 2)
    
    def test_can_access_method(self):
        """Test can_access method delegates to service"""
        from auth.dependencies import NodeAccessFilter
        
        free_user = MockUser(1, [])
        filter_instance = NodeAccessFilter.__new__(NodeAccessFilter)
        filter_instance.user = free_user
        filter_instance.service = MagicMock()
        filter_instance.service.can_user_access_node.return_value = True
        
        node = MockDynamicNode(1, "start", "Start")
        result = filter_instance.can_access(node)
        
        filter_instance.service.can_user_access_node.assert_called_once_with(free_user, node)
        self.assertTrue(result)
    
    def test_is_vip_property(self):
        """Test is_vip property delegates to service"""
        from auth.dependencies import NodeAccessFilter
        
        vip_user = MockUser(1, [MockSubscription(1)])
        filter_instance = NodeAccessFilter.__new__(NodeAccessFilter)
        filter_instance.user = vip_user
        filter_instance.service = MagicMock()
        filter_instance.service.is_vip_user.return_value = True
        
        self.assertTrue(filter_instance.is_vip)
        filter_instance.service.is_vip_user.assert_called_once_with(vip_user)


# ==============================================================================
# Integration Tests
# ==============================================================================

class TestNodeAccessIntegration(unittest.TestCase):
    """Integration tests for the full node access flow"""
    
    def test_full_flow_free_user(self):
        """Test complete flow for free user"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start", "end", "if", "set", "http_request", "gmail", "telegram"},
            enable_vip_filtering=True
        )
        service = NodeAccessService(config=config)
        
        free_user = MockUser(1, [])
        all_nodes = create_test_nodes()
        
        # Get accessible nodes
        accessible = service.get_accessible_nodes(free_user, all_nodes)
        
        # Verify counts
        self.assertEqual(len(all_nodes), 11)
        self.assertEqual(len(accessible), 7)
        
        # Verify specific nodes
        accessible_types = {n.type for n in accessible}
        self.assertIn("start", accessible_types)
        self.assertIn("gmail", accessible_types)
        self.assertNotIn("ai_agent", accessible_types)
        self.assertNotIn("deepseek", accessible_types)
    
    def test_full_flow_vip_user(self):
        """Test complete flow for VIP user"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start", "end"},  # Very restrictive
            enable_vip_filtering=True
        )
        service = NodeAccessService(config=config)
        
        vip_user = MockUser(1, [MockSubscription(1, is_active=True, is_expired=False)])
        all_nodes = create_test_nodes()
        
        # VIP gets all nodes
        accessible = service.get_accessible_nodes(vip_user, all_nodes)
        self.assertEqual(len(accessible), len(all_nodes))
    
    def test_subscription_state_transitions(self):
        """Test node access changes with subscription state changes"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="blacklist",
            vip_exclusive_nodes={"ai_agent", "deepseek"},
            enable_vip_filtering=True
        )
        service = NodeAccessService(config=config)
        
        all_nodes = create_test_nodes()
        ai_node = MockDynamicNode(8, "ai_agent", "AI Agent")
        
        # User starts as free
        user = MockUser(1, [])
        accessible = service.get_accessible_nodes(user, all_nodes)
        self.assertNotIn(ai_node.type, {n.type for n in accessible})
        
        # User gets subscription
        user.subscriptions = [MockSubscription(1, is_active=True, is_expired=False)]
        accessible = service.get_accessible_nodes(user, all_nodes)
        self.assertIn(ai_node.type, {n.type for n in accessible})
        
        # Subscription expires
        user.subscriptions = [MockSubscription(1, is_active=True, is_expired=True)]
        accessible = service.get_accessible_nodes(user, all_nodes)
        self.assertNotIn(ai_node.type, {n.type for n in accessible})


# ==============================================================================
# Edge Cases Tests
# ==============================================================================

class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling"""
    
    def test_empty_nodes_list(self):
        """Test filtering empty nodes list"""
        from services.node_access import NodeAccessService, NodeAccessConfig
        
        service = NodeAccessService()
        user = MockUser(1, [])
        
        result = service.get_accessible_nodes(user, [])
        
        self.assertEqual(result, [])
    
    def test_node_without_type_attribute(self):
        """Test handling node without type attribute"""
        from services.node_access import BaseUserAccessStrategy, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start"},
            enable_vip_filtering=True
        )
        strategy = BaseUserAccessStrategy(config)
        
        # Node without type
        broken_node = MagicMock(spec=[])  # No type attribute
        
        # Should not crash, just return False
        self.assertFalse(strategy.can_access(broken_node))
    
    def test_node_with_none_category(self):
        """Test handling node with None category"""
        from services.node_access import BaseUserAccessStrategy, NodeAccessConfig
        
        config = NodeAccessConfig(
            access_mode="blacklist",
            vip_exclusive_categories={"premium"},
            enable_vip_filtering=True
        )
        strategy = BaseUserAccessStrategy(config)
        
        # Node with None category
        node = MockDynamicNode(1, "test", "Test", category=None)
        
        # Should be accessible (no category restriction applies)
        self.assertTrue(strategy.can_access(node))
    
    def test_multiple_subscriptions_uses_first_valid(self):
        """Test user with multiple subscriptions uses first valid one"""
        from services.node_access import NodeAccessService
        
        service = NodeAccessService()
        
        # User with mixed subscriptions
        user = MockUser(1, [
            MockSubscription(1, is_active=False, is_expired=False),  # Inactive
            MockSubscription(2, is_active=True, is_expired=True),   # Expired
            MockSubscription(3, is_active=True, is_expired=False),  # Valid!
        ])
        
        # Should be VIP because third subscription is valid
        self.assertTrue(service.is_vip_user(user))
    
    def test_config_with_overlapping_rules(self):
        """Test config with node in both base and VIP exclusive"""
        from services.node_access import BaseUserAccessStrategy, NodeAccessConfig
        
        # Edge case: node in both lists (whitelist mode)
        config = NodeAccessConfig(
            access_mode="whitelist",
            base_nodes={"start", "ai_agent"},  # ai_agent in base
            vip_exclusive_nodes={"ai_agent"},  # but also VIP exclusive
            enable_vip_filtering=True
        )
        strategy = BaseUserAccessStrategy(config)
        
        # In whitelist mode, base_nodes takes precedence
        ai_node = MockDynamicNode(8, "ai_agent", "AI Agent")
        self.assertTrue(strategy.can_access(ai_node))


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
