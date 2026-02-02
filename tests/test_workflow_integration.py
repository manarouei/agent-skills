"""
Integration test for workflow_runtime with core node pack.

Verifies end-to-end workflow execution works.
"""

import pytest


class TestWorkflowExecutorIntegration:
    """Integration tests for WorkflowExecutor with real nodes."""
    
    def test_simple_workflow_execution(self):
        """Test executing a simple workflow with ManualTrigger -> Set -> NoOp."""
        from src.workflow_runtime import WorkflowDefinition, WorkflowExecutor
        from src.workflow_runtime.executor import DefaultNodeExecutor
        from nodepacks.core.nodes import ManualTriggerNode, SetNode, NoOpNode
        
        # Create executor with registered nodes
        node_executor = DefaultNodeExecutor()
        node_executor.register_node("n8n-nodes-base.manualTrigger", ManualTriggerNode)
        node_executor.register_node("n8n-nodes-base.set", SetNode)
        node_executor.register_node("n8n-nodes-base.noOp", NoOpNode)
        
        # Define a simple workflow
        workflow = WorkflowDefinition(
            id="test-workflow-1",
            name="Test Workflow",
            nodes=[
                {
                    "name": "Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "parameters": {},
                },
                {
                    "name": "Set Data",
                    "type": "n8n-nodes-base.set",
                    "parameters": {
                        "mode": "raw",
                        "jsonData": '{"message": "Hello", "count": 42}',
                    },
                },
                {
                    "name": "Pass Through",
                    "type": "n8n-nodes-base.noOp",
                    "parameters": {},
                },
            ],
            connections={
                "Trigger": {"main": [[{"node": "Set Data", "type": "main", "index": 0}]]},
                "Set Data": {"main": [[{"node": "Pass Through", "type": "main", "index": 0}]]},
            },
        )
        
        # Execute
        executor = WorkflowExecutor(node_executor=node_executor)
        result = executor.execute(workflow)
        
        # Verify
        assert result.is_success
        assert result.workflow_id == "test-workflow-1"
        assert len(result.node_results) == 3
        assert result.node_results["Trigger"].is_success
        assert result.node_results["Set Data"].is_success
        assert result.node_results["Pass Through"].is_success
        
        # Check output data
        assert len(result.output_data) == 1
        assert result.output_data[0]["json"]["message"] == "Hello"
        assert result.output_data[0]["json"]["count"] == 42
    
    def test_workflow_with_code_node(self):
        """Test Code node executing custom Python."""
        from src.workflow_runtime import WorkflowDefinition, WorkflowExecutor
        from src.workflow_runtime.executor import DefaultNodeExecutor
        from nodepacks.core.nodes import ManualTriggerNode, SetNode, CodeNode
        
        # Create executor
        node_executor = DefaultNodeExecutor()
        node_executor.register_node("n8n-nodes-base.manualTrigger", ManualTriggerNode)
        node_executor.register_node("n8n-nodes-base.set", SetNode)
        node_executor.register_node("n8n-nodes-base.code", CodeNode)
        
        # Define workflow with code transformation
        workflow = WorkflowDefinition(
            id="test-workflow-code",
            name="Code Test",
            nodes=[
                {
                    "name": "Start",
                    "type": "n8n-nodes-base.manualTrigger",
                    "parameters": {},
                },
                {
                    "name": "Set Numbers",
                    "type": "n8n-nodes-base.set",
                    "parameters": {
                        "mode": "raw",
                        "jsonData": '{"numbers": [1, 2, 3, 4, 5]}',
                    },
                },
                {
                    "name": "Transform",
                    "type": "n8n-nodes-base.code",
                    "parameters": {
                        "mode": "runOnceForAllItems",
                        "code": "[{'json': {'sum': sum(item['json']['numbers']), 'count': len(item['json']['numbers'])}} for item in items]",
                    },
                },
            ],
            connections={
                "Start": {"main": [[{"node": "Set Numbers", "type": "main", "index": 0}]]},
                "Set Numbers": {"main": [[{"node": "Transform", "type": "main", "index": 0}]]},
            },
        )
        
        # Execute
        executor = WorkflowExecutor(node_executor=node_executor)
        result = executor.execute(workflow)
        
        # Verify
        assert result.is_success
        assert len(result.output_data) == 1
        assert result.output_data[0]["json"]["sum"] == 15  # 1+2+3+4+5
        assert result.output_data[0]["json"]["count"] == 5
    
    def test_workflow_with_disabled_node(self):
        """Test that disabled nodes are skipped."""
        from src.workflow_runtime import WorkflowDefinition, WorkflowExecutor
        from src.workflow_runtime.executor import DefaultNodeExecutor
        from nodepacks.core.nodes import ManualTriggerNode, SetNode, NoOpNode
        
        node_executor = DefaultNodeExecutor()
        node_executor.register_node("n8n-nodes-base.manualTrigger", ManualTriggerNode)
        node_executor.register_node("n8n-nodes-base.set", SetNode)
        node_executor.register_node("n8n-nodes-base.noOp", NoOpNode)
        
        workflow = WorkflowDefinition(
            id="test-disabled",
            name="Disabled Node Test",
            nodes=[
                {
                    "name": "Start",
                    "type": "n8n-nodes-base.manualTrigger",
                    "parameters": {},
                },
                {
                    "name": "Disabled Set",
                    "type": "n8n-nodes-base.set",
                    "parameters": {"mode": "raw", "jsonData": '{"should": "not appear"}'},
                    "disabled": True,
                },
                {
                    "name": "End",
                    "type": "n8n-nodes-base.noOp",
                    "parameters": {},
                },
            ],
            connections={
                "Start": {"main": [[{"node": "Disabled Set", "type": "main", "index": 0}]]},
                "Disabled Set": {"main": [[{"node": "End", "type": "main", "index": 0}]]},
            },
        )
        
        executor = WorkflowExecutor(node_executor=node_executor)
        result = executor.execute(workflow)
        
        # Should succeed but with disabled node skipped
        assert result.is_success
        from src.workflow_runtime.graph import NodeStatus
        assert result.node_results["Disabled Set"].status == NodeStatus.SKIPPED
    
    def test_compiled_graph_topological_order(self):
        """Test that CompiledGraph computes correct execution order."""
        from src.workflow_runtime import WorkflowDefinition
        from src.workflow_runtime.graph import CompiledGraph
        
        # Diamond pattern: A -> B, A -> C, B -> D, C -> D
        workflow = WorkflowDefinition(
            id="diamond",
            name="Diamond",
            nodes=[
                {"name": "A", "type": "test"},
                {"name": "B", "type": "test"},
                {"name": "C", "type": "test"},
                {"name": "D", "type": "test"},
            ],
            connections={
                "A": {"main": [
                    [{"node": "B", "type": "main", "index": 0}],
                    [{"node": "C", "type": "main", "index": 0}],
                ]},
                "B": {"main": [[{"node": "D", "type": "main", "index": 0}]]},
                "C": {"main": [[{"node": "D", "type": "main", "index": 0}]]},
            },
        )
        
        graph = CompiledGraph(workflow)
        order = graph.execution_order
        
        # A must come before B and C
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        # B and C must come before D
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")
    
    def test_node_registry_integration(self):
        """Test NodeRegistry with core pack."""
        from src.node_registry import NodeRegistry
        from nodepacks.core.manifest import register_nodes
        
        registry = NodeRegistry()
        manifest, node_classes = register_nodes()
        registry.register_pack(manifest, node_classes)
        
        # Verify nodes are registered
        assert registry.has_node("n8n-nodes-base.manualTrigger")
        assert registry.has_node("n8n-nodes-base.set")
        assert registry.has_node("n8n-nodes-base.code")
        
        # Verify can create nodes
        trigger = registry.create_node("n8n-nodes-base.manualTrigger")
        assert trigger is not None
        assert trigger.type == "n8n-nodes-base.manualTrigger"


class TestNodeSDK:
    """Tests for the node SDK."""
    
    def test_base_node_execute_contract(self):
        """Test that BaseNode execute() returns correct format."""
        from nodepacks.core.nodes import ManualTriggerNode
        
        node = ManualTriggerNode()
        result = node.execute()
        
        # Should be List[List[NodeExecutionData]]
        assert isinstance(result, list)
        assert len(result) == 1  # One output branch
        assert isinstance(result[0], list)
        assert len(result[0]) == 1  # One item
        assert "json" in result[0][0]
    
    def test_node_execution_context(self):
        """Test NodeExecutionContext provides correct values."""
        from src.node_sdk.basenode import NodeExecutionContext
        from nodepacks.core.nodes import SetNode
        
        context = NodeExecutionContext(
            parameters={
                "mode": "raw",
                "jsonData": '{"test": "value"}',
            },
            credentials={},
            input_data=[{"json": {"existing": "data"}}],
        )
        
        node = SetNode()
        node.set_context(context)
        
        result = node.execute()
        
        assert result[0][0]["json"]["test"] == "value"
