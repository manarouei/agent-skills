#!/usr/bin/env python3
"""
Unit Tests for Dynamic Node Access System
==========================================

NOTE (2024-12 Update):
======================
Node visibility filtering has been DISABLED (enable_filtering: false).
All users can now see all nodes regardless of subscription.

These tests now validate:
1. PlanConfigLoader - YAML loading
2. DynamicNodeAccessService - Plan resolution (still works internally)
3. Filtering is disabled - all users get all access
4. Plan info methods still work correctly

Run: python tests/test_dynamic_node_access.py
"""

import sys
import os
import unittest
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==============================================================================
# Mock Objects
# ==============================================================================

@dataclass
class MockSubscription:
    """Mock Subscription for testing"""
    id: int = 1
    plan_type: str = "custom"
    node_overrides: Optional[Dict[str, Any]] = None
    is_active: bool = True
    is_expired: bool = False
    
    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired


class MockUser:
    """Mock User for testing"""
    
    def __init__(self, user_id: str, subscription: Optional[MockSubscription] = None):
        self.id = user_id
        self._subscription = subscription
        self.subscriptions = [subscription] if subscription else []
    
    @property
    def active_subscription(self) -> Optional[MockSubscription]:
        if self._subscription and self._subscription.is_valid:
            return self._subscription
        return None


@dataclass
class MockDynamicNode:
    """Mock DynamicNode for testing"""
    id: int
    type: str
    name: str


# ==============================================================================
# PlanConfigLoader Tests
# ==============================================================================

class TestPlanConfigLoader(unittest.TestCase):
    """Tests for PlanConfigLoader"""
    
    def setUp(self):
        from services.dynamic_node_access import PlanConfigLoader
        PlanConfigLoader._instance = None
        PlanConfigLoader._config = None
    
    def test_loads_config_from_file(self):
        """Test loading config from node_plans.yaml"""
        from services.dynamic_node_access import PlanConfigLoader
        
        config = PlanConfigLoader.get_config()
        
        self.assertIsNotNone(config)
        self.assertIn("free", config.plans)
        self.assertIn("custom", config.plans)
    
    def test_singleton_pattern(self):
        """Test ConfigLoader is singleton"""
        from services.dynamic_node_access import PlanConfigLoader
        
        loader1 = PlanConfigLoader()
        loader2 = PlanConfigLoader()
        
        self.assertIs(loader1, loader2)
    
    def test_node_sets_loaded(self):
        """Test node sets are loaded from config"""
        from services.dynamic_node_access import PlanConfigLoader
        
        config = PlanConfigLoader.get_config()
        
        self.assertIn("core", config.node_sets)
        self.assertIn("google", config.node_sets)
        self.assertIn("ai", config.node_sets)


# ==============================================================================
# DynamicNodeAccessService Tests
# ==============================================================================

class TestDynamicNodeAccessService(unittest.TestCase):
    """Tests for DynamicNodeAccessService"""
    
    def test_resolve_free_plan_nodes(self):
        """Test resolving nodes for free plan"""
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        nodes = service._resolve_plan_nodes("free")
        
        # Free plan should include core nodes
        self.assertIn("start", nodes)
        self.assertIn("end", nodes)
        self.assertIn("if", nodes)
    
    def test_custom_plan_inherits_free(self):
        """Test custom plan inherits from free"""
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        free_nodes = service._resolve_plan_nodes("free")
        custom_nodes = service._resolve_plan_nodes("custom")
        
        # Custom should have at least what free has
        self.assertTrue(free_nodes.issubset(custom_nodes))
    
    def test_user_without_subscription_gets_free(self):
        """Test user without subscription gets free plan nodes"""
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        user = MockUser("user1", subscription=None)
        
        plan = service.get_plan_for_user(user)
        
        self.assertEqual(plan, "free")
    
    def test_user_with_subscription_gets_plan_type(self):
        """Test user with subscription gets their plan type"""
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        subscription = MockSubscription(plan_type="custom")
        user = MockUser("user1", subscription=subscription)
        
        plan = service.get_plan_for_user(user)
        
        self.assertEqual(plan, "custom")
    
    def test_custom_plan_with_node_overrides(self):
        """
        Test custom plan uses node_overrides.nodes
        
        NOTE: With filtering DISABLED, all users get wildcard access {"*"}
        """
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        subscription = MockSubscription(
            plan_type="custom",
            node_overrides={"nodes": ["ai_agent", "deepseek", "openai"]}
        )
        user = MockUser("user1", subscription=subscription)
        
        accessible = service.get_user_accessible_nodes(user)
        
        # With filtering disabled, should get wildcard access
        self.assertEqual(accessible, {"*"})
    
    def test_add_override(self):
        """
        Test add override grants additional nodes
        
        NOTE: With filtering DISABLED, all users get wildcard access {"*"}
        """
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        subscription = MockSubscription(
            plan_type="free",
            node_overrides={"add": ["special_node"]}
        )
        user = MockUser("user1", subscription=subscription)
        
        accessible = service.get_user_accessible_nodes(user)
        
        # With filtering disabled, should get wildcard access
        self.assertEqual(accessible, {"*"})
    
    def test_remove_override(self):
        """
        Test remove override revokes nodes
        
        NOTE: With filtering DISABLED, all users get wildcard access {"*"}
        """
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        subscription = MockSubscription(
            plan_type="free",
            node_overrides={"remove": ["gmail"]}  # Remove a free node
        )
        user = MockUser("user1", subscription=subscription)
        
        accessible = service.get_user_accessible_nodes(user)
        
        # With filtering disabled, should get wildcard access
        self.assertEqual(accessible, {"*"})
    
    def test_filter_nodes_for_user(self):
        """
        Test filtering a list of nodes
        
        NOTE: With filtering DISABLED, filter_nodes_for_user returns ALL nodes
        """
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        user = MockUser("user1", subscription=None)  # Free user
        
        all_nodes = [
            MockDynamicNode(1, "start", "Start"),
            MockDynamicNode(2, "end", "End"),
            MockDynamicNode(3, "ai_agent", "AI Agent"),
            MockDynamicNode(4, "deepseek", "DeepSeek"),
        ]
        
        filtered = service.filter_nodes_for_user(user, all_nodes)
        filtered_types = {n.type for n in filtered}
        
        # With filtering disabled, ALL nodes should be returned
        self.assertEqual(len(filtered), len(all_nodes))
        self.assertIn("start", filtered_types)
        self.assertIn("end", filtered_types)
        self.assertIn("ai_agent", filtered_types)
        self.assertIn("deepseek", filtered_types)
    
    def test_can_user_access_node(self):
        """
        Test single node access check
        
        NOTE: With filtering DISABLED, all users can access all nodes
        """
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        free_user = MockUser("user1", subscription=None)
        
        start_node = MockDynamicNode(1, "start", "Start")
        ai_node = MockDynamicNode(2, "ai_agent", "AI Agent")
        
        # With filtering disabled, all nodes are accessible
        self.assertTrue(service.can_user_access_node(free_user, start_node))
        self.assertTrue(service.can_user_access_node(free_user, ai_node))
    
    def test_is_subscribed_user(self):
        """Test subscription status check"""
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        
        free_user = MockUser("user1", subscription=None)
        subscribed_user = MockUser("user2", subscription=MockSubscription())
        
        self.assertFalse(service.is_subscribed_user(free_user))
        self.assertTrue(service.is_subscribed_user(subscribed_user))
    
    def test_get_user_plan_info(self):
        """Test getting detailed plan info"""
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        subscription = MockSubscription(plan_type="custom")
        user = MockUser("user1", subscription=subscription)
        
        info = service.get_user_plan_info(user)
        
        self.assertEqual(info["plan_type"], "custom")
        self.assertTrue(info["is_subscribed"])
        self.assertIn("display_name", info)
        self.assertIn("node_count", info)


# ==============================================================================
# Edge Cases Tests
# ==============================================================================

class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases"""
    
    def test_none_user(self):
        """
        Test handling None user
        
        NOTE: With filtering DISABLED, accessible returns {"*"} for all users
        """
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        
        plan = service.get_plan_for_user(None)
        accessible = service.get_user_accessible_nodes(None)
        
        self.assertEqual(plan, "free")
        # With filtering disabled, returns wildcard
        self.assertEqual(accessible, {"*"})
    
    def test_expired_subscription(self):
        """Test user with expired subscription treated as free"""
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        subscription = MockSubscription(
            plan_type="custom",
            is_expired=True
        )
        user = MockUser("user1", subscription=subscription)
        
        # active_subscription should return None for expired
        self.assertIsNone(user.active_subscription)
        
        plan = service.get_plan_for_user(user)
        self.assertEqual(plan, "free")
    
    def test_empty_node_overrides(self):
        """
        Test empty node_overrides doesn't break
        
        NOTE: With filtering DISABLED, accessible returns {"*"} for all users
        """
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        subscription = MockSubscription(
            plan_type="custom",
            node_overrides={}
        )
        user = MockUser("user1", subscription=subscription)
        
        accessible = service.get_user_accessible_nodes(user)
        
        # With filtering disabled, returns wildcard
        self.assertEqual(accessible, {"*"})
    
    def test_invalid_plan_type_falls_back_to_free(self):
        """Test invalid plan type falls back to free plan (not empty set)"""
        from services.dynamic_node_access import DynamicNodeAccessService
        
        service = DynamicNodeAccessService()
        
        # Unknown plans like "gold", "silver", "bronze" should fall back to free
        for plan_name in ["nonexistent_plan", "gold", "silver", "bronze", "premium"]:
            nodes = service._resolve_plan_nodes(plan_name)
            # Should get free plan nodes, not empty set
            self.assertGreater(len(nodes), 0, f"Plan '{plan_name}' should fall back to free plan")
            self.assertIn("start", nodes)
            self.assertIn("set", nodes)


# ==============================================================================
# Main
# ==============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
