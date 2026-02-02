#!/usr/bin/env python3
"""
Integration tests for Memory nodes (Buffer and Redis).

These tests verify that memory nodes work correctly in a simulated workflow context,
including the LangChain Runnable integration.

Run with: python tests/test_memory_integration.py
"""

import sys
import os
import unittest
import logging
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Test Helpers
# ============================================================================

def create_test_messages(count: int, start_index: int = 0) -> List[Dict[str, Any]]:
    """Create a list of test messages simulating a conversation."""
    messages = []
    for i in range(start_index, start_index + count):
        messages.append({"role": "user", "content": f"User message {i}"})
        messages.append({"role": "assistant", "content": f"Assistant response {i}"})
    return messages


def create_workflow_context() -> Dict[str, Any]:
    """Create a mock workflow execution context."""
    return {
        "workflow_id": "test-workflow-123",
        "execution_id": "exec-456",
        "node_id": "memory-node-1",
        "timestamp": "2025-11-26T10:00:00Z"
    }


# ============================================================================
# Test: __init__.py Imports Work Correctly
# ============================================================================

class TestModuleImports(unittest.TestCase):
    """Verify that module imports work correctly after refactoring."""
    
    def test_node_imports_from_init(self):
        """Node classes should be importable from nodes.memory."""
        from nodes.memory import BufferMemoryNode, RedisMemoryNode
        
        self.assertTrue(callable(BufferMemoryNode))
        self.assertTrue(callable(RedisMemoryNode))
        logger.info("✅ Node classes import correctly from nodes.memory")
    
    def test_manager_imports_directly(self):
        """Manager classes should be importable from specific modules."""
        from nodes.memory.buffer_memory import MemoryManager
        from nodes.memory.redis_memory import RedisMemoryManager, create_redis_memory_manager
        
        self.assertTrue(hasattr(MemoryManager, 'load'))
        self.assertTrue(hasattr(MemoryManager, 'save'))
        self.assertTrue(callable(RedisMemoryManager))
        self.assertTrue(callable(create_redis_memory_manager))
        logger.info("✅ Manager classes import correctly from specific modules")
    
    def test_all_exports_are_nodes_only(self):
        """__all__ should only contain Node classes."""
        from nodes import memory
        
        self.assertEqual(
            set(memory.__all__),
            {'BufferMemoryNode', 'RedisMemoryNode'},
            "__all__ should only contain Node classes"
        )
        logger.info("✅ __all__ exports only Node classes")


# ============================================================================
# Test: Buffer Memory in Workflow Context
# ============================================================================

class TestBufferMemoryWorkflow(unittest.TestCase):
    """Test BufferMemoryNode in a simulated workflow execution."""
    
    def setUp(self):
        """Clear memory store before each test."""
        from nodes.memory.buffer_memory import _STORE
        _STORE._store.clear()
        self.session_id = f"workflow-test-{id(self)}"
    
    def tearDown(self):
        """Clean up after test."""
        from nodes.memory.buffer_memory import MemoryManager
        MemoryManager.clear(self.session_id)
    
    def test_workflow_conversation_flow(self):
        """Simulate a multi-turn conversation in a workflow."""
        from nodes.memory.buffer_memory import MemoryManager
        
        # Turn 1: User asks a question
        turn1_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is Python?"}
        ]
        MemoryManager.save(self.session_id, turn1_messages, context_window=10)
        
        # Turn 1: Assistant responds
        turn1_with_response = turn1_messages + [
            {"role": "assistant", "content": "Python is a programming language."}
        ]
        MemoryManager.save(self.session_id, turn1_with_response, context_window=10)
        
        # Verify Turn 1 is saved
        loaded = MemoryManager.load(self.session_id, context_window=10)
        self.assertEqual(len(loaded), 3)
        
        # Turn 2: User asks follow-up
        turn2_messages = loaded + [
            {"role": "user", "content": "What are its main features?"}
        ]
        MemoryManager.save(self.session_id, turn2_messages, context_window=10)
        
        # Turn 2: Assistant responds
        turn2_with_response = turn2_messages + [
            {"role": "assistant", "content": "Python is known for readability and simplicity."}
        ]
        MemoryManager.save(self.session_id, turn2_with_response, context_window=10)
        
        # Verify full conversation is stored
        final = MemoryManager.load(self.session_id, context_window=10)
        self.assertEqual(len(final), 5)  # system + 2 turns (user+assistant each)
        
        # Verify message order is correct
        self.assertEqual(final[0]["role"], "system")
        self.assertEqual(final[1]["role"], "user")
        self.assertEqual(final[2]["role"], "assistant")
        self.assertEqual(final[3]["role"], "user")
        self.assertEqual(final[4]["role"], "assistant")
        
        logger.info("✅ Multi-turn conversation flow works correctly")
    
    def test_context_window_in_workflow(self):
        """Test context window limiting during workflow execution."""
        from nodes.memory.buffer_memory import MemoryManager
        
        # Create a long conversation
        messages = [{"role": "system", "content": "System prompt"}]
        for i in range(20):
            messages.append({"role": "user", "content": f"Message {i}"})
            messages.append({"role": "assistant", "content": f"Response {i}"})
        
        # Save with context_window=3 (should trigger auto-clear)
        MemoryManager.save(self.session_id, messages, context_window=3, auto_clear_on_full=True)
        
        # Load should return truncated conversation
        loaded = MemoryManager.load(self.session_id, context_window=3)
        
        # Should have system + last turn only (auto-clear behavior)
        self.assertLessEqual(len(loaded), 5)  # system + up to 1 turn worth
        self.assertEqual(loaded[0]["role"], "system")
        
        logger.info("✅ Context window limiting works in workflow")


# ============================================================================
# Test: LangChain Memory Runnable Integration
# ============================================================================

class TestMemoryRunnableIntegration(unittest.TestCase):
    """Test MemoryRunnable works in LCEL chains."""
    
    def setUp(self):
        """Clear memory store before each test."""
        from nodes.memory.buffer_memory import _STORE
        _STORE._store.clear()
        self.session_id = f"runnable-test-{id(self)}"
    
    def tearDown(self):
        """Clean up after test."""
        from nodes.memory.buffer_memory import MemoryManager
        MemoryManager.clear(self.session_id)
    
    def test_memory_runnable_load_save_cycle(self):
        """Test load → save → load cycle with MemoryRunnable."""
        from utils.langchain_memory import MemoryRunnable
        
        memory = MemoryRunnable(
            session_id=self.session_id,
            context_window=5,
            ttl_seconds=3600
        )
        
        # Initial load (empty)
        result = memory.invoke({"action": "load"})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        
        # Save some messages
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        result = memory.invoke({"action": "save", "messages": messages})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)
        
        # Load again - should have messages
        result = memory.invoke({"action": "load"})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 3)
        self.assertEqual(result["messages"][0]["role"], "system")
        
        logger.info("✅ MemoryRunnable load/save cycle works")
    
    def test_memory_runnable_clear(self):
        """Test clearing memory via MemoryRunnable."""
        from utils.langchain_memory import MemoryRunnable
        
        memory = MemoryRunnable(session_id=self.session_id, context_window=5)
        
        # Save messages
        messages = [{"role": "user", "content": "Test"}]
        memory.invoke({"action": "save", "messages": messages})
        
        # Clear
        result = memory.invoke({"action": "clear"})
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)
        
        # Verify cleared
        result = memory.invoke({"action": "load"})
        self.assertEqual(result["count"], 0)
        
        logger.info("✅ MemoryRunnable clear works")
    
    def test_memory_runnable_with_session(self):
        """Test creating new runnable with different session."""
        from utils.langchain_memory import MemoryRunnable
        
        memory1 = MemoryRunnable(session_id="session-1", context_window=5)
        memory2 = memory1.with_session("session-2")
        
        # Save to session 1
        memory1.invoke({"action": "save", "messages": [{"role": "user", "content": "In session 1"}]})
        
        # Session 2 should be empty
        result = memory2.invoke({"action": "load"})
        self.assertEqual(result["count"], 0)
        
        # Session 1 should have message
        result = memory1.invoke({"action": "load"})
        self.assertEqual(result["count"], 1)
        
        # Clean up
        memory1.invoke({"action": "clear"})
        memory2.invoke({"action": "clear"})
        
        logger.info("✅ MemoryRunnable session isolation works")


# ============================================================================
# Test: Redis Memory Runnable (Mocked)
# ============================================================================

class TestRedisMemoryRunnableMocked(unittest.TestCase):
    """Test RedisMemoryRunnable with mocked Redis connection."""
    
    def setUp(self):
        self.session_id = f"redis-test-{id(self)}"
        self.mock_storage = {}
    
    def test_redis_memory_runnable_interface(self):
        """Test RedisMemoryRunnable has correct interface."""
        from utils.langchain_memory import RedisMemoryRunnable
        
        memory = RedisMemoryRunnable(
            session_id=self.session_id,
            context_window=5,
            credentials={"host": "localhost", "port": 6379}
        )
        
        # Verify it has required methods
        self.assertTrue(hasattr(memory, 'invoke'))
        self.assertTrue(hasattr(memory, 'with_session'))
        self.assertTrue(hasattr(memory, 'with_window'))
        
        # Verify properties
        self.assertEqual(memory.session_id, self.session_id)
        self.assertEqual(memory.context_window, 5)
        
        logger.info("✅ RedisMemoryRunnable has correct interface")
    
    def test_redis_memory_runnable_repr(self):
        """Test RedisMemoryRunnable string representation."""
        from utils.langchain_memory import RedisMemoryRunnable
        
        memory = RedisMemoryRunnable(
            session_id="test-session",
            context_window=10,
            ttl_seconds=7200,
            credentials={"host": "redis.example.com"}
        )
        
        repr_str = repr(memory)
        self.assertIn("test-session", repr_str)
        self.assertIn("10", repr_str)
        self.assertIn("7200", repr_str)
        self.assertIn("redis.example.com", repr_str)
        
        logger.info("✅ RedisMemoryRunnable repr works")


# ============================================================================
# Test: Factory Functions
# ============================================================================

class TestFactoryFunctions(unittest.TestCase):
    """Test factory functions for creating memory runnables."""
    
    def test_create_memory_factory(self):
        """Test create_memory factory function."""
        from utils.langchain_memory import create_memory
        
        memory = create_memory(
            session_id="factory-test",
            context_window=8,
            ttl_seconds=1800
        )
        
        self.assertEqual(memory.session_id, "factory-test")
        self.assertEqual(memory.context_window, 8)
        self.assertEqual(memory.ttl_seconds, 1800)
        
        logger.info("✅ create_memory factory works")
    
    def test_create_redis_memory_factory(self):
        """Test create_redis_memory factory function."""
        from utils.langchain_memory import create_redis_memory
        
        memory = create_redis_memory(
            session_id="redis-factory-test",
            context_window=6,
            ttl_seconds=900,
            credentials={"host": "localhost", "port": 6379, "password": "secret"}
        )
        
        self.assertEqual(memory.session_id, "redis-factory-test")
        self.assertEqual(memory.context_window, 6)
        self.assertEqual(memory.ttl_seconds, 900)
        self.assertEqual(memory.credentials["password"], "secret")
        
        logger.info("✅ create_redis_memory factory works")


# ============================================================================
# Test: BufferMemoryNode Class Properties (no instantiation needed)
# ============================================================================

class TestBufferMemoryNodeExecution(unittest.TestCase):
    """Test BufferMemoryNode class-level properties."""
    
    def setUp(self):
        from nodes.memory.buffer_memory import _STORE
        _STORE._store.clear()
    
    def test_node_class_has_required_attributes(self):
        """Test BufferMemoryNode class has required class attributes."""
        from nodes.memory import BufferMemoryNode
        
        # Check class-level attributes (node uses 'description' dict for metadata)
        self.assertTrue(hasattr(BufferMemoryNode, 'properties'))
        self.assertTrue(hasattr(BufferMemoryNode, 'description'))
        self.assertTrue(hasattr(BufferMemoryNode, 'type'))
        
        # description should be a dict containing name
        self.assertIsInstance(BufferMemoryNode.description, dict)
        self.assertIn('name', BufferMemoryNode.description)
        
        logger.info("✅ BufferMemoryNode class has required attributes")
    
    def test_node_class_has_get_runnable_method(self):
        """Test BufferMemoryNode class has get_runnable method."""
        from nodes.memory import BufferMemoryNode
        
        # Should have get_runnable as a method
        self.assertTrue(hasattr(BufferMemoryNode, 'get_runnable'))
        self.assertTrue(callable(getattr(BufferMemoryNode, 'get_runnable', None)))
        
        logger.info("✅ BufferMemoryNode has get_runnable method")
    
    def test_node_properties_structure(self):
        """Test BufferMemoryNode properties have correct structure."""
        from nodes.memory import BufferMemoryNode
        
        props = BufferMemoryNode.properties
        
        # properties is a dict with 'parameters' key
        self.assertIsInstance(props, dict)
        self.assertIn('parameters', props)
        
        params = props['parameters']
        self.assertIsInstance(params, list)
        self.assertGreater(len(params), 0)
        
        # Each parameter should be a dict with name
        for param in params:
            self.assertIsInstance(param, dict)
            self.assertIn('name', param)
        
        logger.info("✅ BufferMemoryNode properties have correct structure")


# ============================================================================
# Test: RedisMemoryNode Class Properties (no instantiation needed)
# ============================================================================

class TestRedisMemoryNodeProperties(unittest.TestCase):
    """Test RedisMemoryNode class-level properties."""
    
    def test_node_class_has_credentials(self):
        """Test RedisMemoryNode class declares credentials requirement."""
        from nodes.memory import RedisMemoryNode
        
        # Properties dict should contain credentials key
        self.assertTrue(hasattr(RedisMemoryNode, 'properties'))
        props = RedisMemoryNode.properties
        
        self.assertIn('credentials', props, "properties should have credentials key")
        
        creds = props['credentials']
        self.assertIsInstance(creds, list)
        self.assertGreater(len(creds), 0, "Should have at least one credential type")
        
        # Check for redis credential
        cred_names = [c.get('name', '') for c in creds]
        self.assertTrue(
            any('redis' in name.lower() for name in cred_names),
            f"Should require redis credential, found: {cred_names}"
        )
        
        logger.info("✅ RedisMemoryNode class has credentials requirement")
    
    def test_node_class_has_properties(self):
        """Test RedisMemoryNode has session configuration properties."""
        from nodes.memory import RedisMemoryNode
        
        # Check class-level properties
        self.assertTrue(hasattr(RedisMemoryNode, 'properties'))
        props = RedisMemoryNode.properties
        
        # Should have parameters key
        self.assertIsInstance(props, dict)
        self.assertIn('parameters', props)
        
        params = props['parameters']
        self.assertIsInstance(params, list)
        self.assertGreater(len(params), 0)
        
        # Check for session-related parameter
        param_names = [p.get('name', '') for p in params]
        self.assertTrue(
            any('session' in name.lower() for name in param_names),
            f"Should have session-related parameter, found: {param_names}"
        )
        
        logger.info("✅ RedisMemoryNode class has session configuration properties")
    
    def test_node_class_has_description(self):
        """Test RedisMemoryNode has name and description."""
        from nodes.memory import RedisMemoryNode
        
        self.assertTrue(hasattr(RedisMemoryNode, 'description'))
        desc = RedisMemoryNode.description
        
        self.assertIsInstance(desc, dict)
        self.assertIn('name', desc)
        self.assertIn('displayName', desc)
        
        # Name should contain "redis" or "memory"
        name = desc['name'].lower() if desc['name'] else ""
        self.assertTrue(
            'redis' in name or 'memory' in name,
            f"Name should indicate Redis memory: {desc['name']}"
        )
        
        logger.info("✅ RedisMemoryNode has name and description")


# ============================================================================
# Main Runner
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("MEMORY NODE INTEGRATION TEST SUITE")
    print("=" * 80)
    print()
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestModuleImports))
    suite.addTests(loader.loadTestsFromTestCase(TestBufferMemoryWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryRunnableIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestRedisMemoryRunnableMocked))
    suite.addTests(loader.loadTestsFromTestCase(TestFactoryFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestBufferMemoryNodeExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestRedisMemoryNodeProperties))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print()
    print("=" * 80)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print()
    
    if result.wasSuccessful():
        print("✅ ALL INTEGRATION TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED!")
        if result.failures:
            print("\nFailures:")
            for test, trace in result.failures:
                print(f"  - {test}: {trace[:200]}...")
        if result.errors:
            print("\nErrors:")
            for test, trace in result.errors:
                print(f"  - {test}: {trace[:200]}...")
    
    sys.exit(0 if result.wasSuccessful() else 1)
