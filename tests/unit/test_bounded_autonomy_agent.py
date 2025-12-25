"""Tests for BoundedAutonomyAgent."""
import pytest
from unittest.mock import Mock, patch

from agentic_system.agents.bounded_autonomy import (
    BoundedAutonomyAgent,
    BoundedAutonomyInput,
    BoundedAutonomyOutput
)
from agentic_system.runtime.agent import ExecutionContext


class TestBoundedAutonomyAgent:
    """Test BoundedAutonomyAgent."""
    
    def test_agent_spec(self):
        """Test agent spec returns correct metadata."""
        agent = BoundedAutonomyAgent()
        spec = agent.spec()
        
        assert spec.agent_id == "bounded_autonomy"
        assert spec.version == "1.0.0"
        assert spec.step_limit == 10
        assert "Bounded autonomy enforcement" in spec.description
    
    def test_input_model(self):
        """Test input_model returns correct type."""
        agent = BoundedAutonomyAgent()
        
        assert agent.input_model() == BoundedAutonomyInput
    
    def test_output_model(self):
        """Test output_model returns correct type."""
        agent = BoundedAutonomyAgent()
        
        assert agent.output_model() == BoundedAutonomyOutput
    
    @patch('agentic_system.agents.bounded_autonomy.get_skill_registry')
    def test_run_accepts_pydantic_model(self, mock_get_registry):
        """Test that _run method accepts BoundedAutonomyInput Pydantic model."""
        agent = BoundedAutonomyAgent()
        
        # Setup mock skill registry
        mock_registry = Mock()
        mock_registry.execute.return_value = {
            'status': 'ready',
            'can_proceed': True,
            'questions': [],
            'missing_context': [],
            'assumptions': [],
            'required_files': []
        }
        mock_get_registry.return_value = mock_registry
        
        # Create Pydantic model input
        input_data = BoundedAutonomyInput(
            mode="plan",
            task_description="Test task",
            files=["test.py"]
        )
        
        context = ExecutionContext(
            trace_id="test-trace",
            job_id="test-job",
            agent_id="test-agent"
        )
        
        # This should not raise TypeError about mapping vs BoundedAutonomyInput
        result = agent._run(input_data, context)
        
        # Should return dict
        assert isinstance(result, dict)
        assert 'mode' in result
        assert result['mode'] == 'plan'
    
    @patch('agentic_system.agents.bounded_autonomy.get_skill_registry')
    def test_plan_mode(self, mock_get_registry):
        """Test plan mode execution."""
        agent = BoundedAutonomyAgent()
        
        mock_registry = Mock()
        mock_registry.execute.return_value = {
            'status': 'ready',
            'can_proceed': True,
            'questions': [],
            'missing_context': [],
            'assumptions': ['Test assumption'],
            'required_files': ['test.py']
        }
        mock_get_registry.return_value = mock_registry
        
        input_data = BoundedAutonomyInput(
            mode="plan",
            task_description="Add caching",
            files=["src/cache.py"]
        )
        
        context = ExecutionContext(
            trace_id="test-trace",
            job_id="test-job",
            agent_id="bounded_autonomy"
        )
        
        result = agent._run(input_data, context)
        
        assert result['mode'] == 'plan'
        assert result['status'] == 'ready'
        # The gate_result is wrapped in the 'result' field
        assert result['result']['can_proceed'] is True
    
    @patch('agentic_system.agents.bounded_autonomy.get_skill_registry')
    def test_review_mode(self, mock_get_registry):
        """Test review mode execution."""
        agent = BoundedAutonomyAgent()
        
        mock_registry = Mock()
        mock_registry.execute.return_value = {
            'compliance_status': 'compliant',
            'p0_violations': [],
            'p1_violations': [],
            'p2_violations': [],
            'passed_checks': ['P0-5'],
            'recommendations': []
        }
        mock_get_registry.return_value = mock_registry
        
        input_data = BoundedAutonomyInput(
            mode="review",
            task_description="Review changes",
            files=["src/main.py", "tests/test_main.py"]
        )
        
        context = ExecutionContext(
            trace_id="test-trace",
            job_id="test-job",
            agent_id="bounded_autonomy"
        )
        
        result = agent._run(input_data, context)
        
        assert result['mode'] == 'review'
        assert result['status'] == 'compliant'
        assert len(result['result']['p0_violations']) == 0
    
    @patch('agentic_system.agents.bounded_autonomy.get_skill_registry')
    def test_validate_mode(self, mock_get_registry):
        """Test validate mode execution."""
        agent = BoundedAutonomyAgent()
        
        mock_registry = Mock()
        
        # Validate mode calls both context_gate and code_review
        def execute_side_effect(name, input_data, context):
            if name == "context_gate":
                return {
                    'status': 'ready',
                    'can_proceed': True,
                    'questions': [],
                    'missing_context': [],
                    'assumptions': [],
                    'required_files': []
                }
            elif name == "code_review":
                return {
                    'compliance_status': 'compliant',
                    'p0_violations': [],
                    'p1_violations': [],
                    'p2_violations': [],
                    'passed_checks': ['P0-5', 'P1-6'],
                    'recommendations': []
                }
        
        mock_registry.execute.side_effect = execute_side_effect
        mock_get_registry.return_value = mock_registry
        
        input_data = BoundedAutonomyInput(
            mode="validate",
            task_description="Validate PR",
            files=["src/feature.py", "tests/test_feature.py"],
            modified_files=["src/feature.py", "tests/test_feature.py"],
            file_diffs={"src/feature.py": "diff content"}
        )
        
        context = ExecutionContext(
            trace_id="test-trace",
            job_id="test-job",
            agent_id="bounded_autonomy"
        )
        
        result = agent._run(input_data, context)
        
        assert result['mode'] == 'validate'
        # When violations are found, status should be 'violations', otherwise use plan status
        # In our case, both pass so status should be 'ready' (from plan)
        assert result['status'] in ('ready', 'compliant')
    
    def test_invalid_mode(self):
        """Test that invalid mode raises ValueError."""
        agent = BoundedAutonomyAgent()
        
        input_data = BoundedAutonomyInput(
            mode="invalid_mode",  # type: ignore
            task_description="Test",
            files=[]
        )
        
        context = ExecutionContext(
            trace_id="test-trace",
            job_id="test-job",
            agent_id="bounded_autonomy"
        )
        
        with pytest.raises(ValueError, match="Unknown mode"):
            agent._run(input_data, context)


class TestBoundedAutonomyIntegration:
    """Integration tests for bounded autonomy agent."""
    
    @patch('agentic_system.agents.bounded_autonomy.get_skill_registry')
    def test_end_to_end_plan_to_review(self, mock_get_registry):
        """Test end-to-end workflow from plan to review."""
        agent = BoundedAutonomyAgent()
        
        # Setup mock registry with different responses for plan and review
        mock_registry = Mock()
        
        def execute_side_effect(name, input_data, context):
            if name == "context_gate":
                return {
                    'status': 'ready',
                    'can_proceed': True,
                    'questions': [],
                    'missing_context': [],
                    'assumptions': ['Working with specified files'],
                    'required_files': []
                }
            elif name == "code_review":
                return {
                    'compliance_status': 'compliant',
                    'p0_violations': [],
                    'p1_violations': [],
                    'p2_violations': [],
                    'passed_checks': ['P0-5', 'P1-6'],
                    'recommendations': []
                }
        
        mock_registry.execute.side_effect = execute_side_effect
        mock_get_registry.return_value = mock_registry
        
        context = ExecutionContext(
            trace_id="e2e-test",
            job_id="e2e-job",
            agent_id="bounded_autonomy"
        )
        
        # Step 1: Plan
        plan_input = BoundedAutonomyInput(
            mode="plan",
            task_description="Add feature X",
            files=["src/feature.py"]
        )
        plan_result = agent._run(plan_input, context)
        
        assert plan_result['result']['can_proceed'] is True
        
        # Step 2: Review (after implementation)
        review_input = BoundedAutonomyInput(
            mode="review",
            task_description="Review feature X",
            files=["src/feature.py", "tests/test_feature.py"]
        )
        review_result = agent._run(review_input, context)
        
        assert review_result['status'] == 'compliant'
        assert len(review_result['result']['p0_violations']) == 0
