"""Tests for CLI commands."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from argparse import Namespace

from agentic_system.cli import cmd_plan, cmd_review, cmd_check_compliance
from agentic_system.runtime.skill import ExecutionContext


class TestCmdPlan:
    """Test cmd_plan function."""
    
    @patch('agentic_system.cli.setup_logging')
    @patch('agentic_system.cli.get_skill_registry')
    def test_plan_without_files(self, mock_registry, mock_logging):
        """Test plan command without FILES parameter."""
        # Setup mock
        mock_skill_registry = Mock()
        mock_skill_registry.execute.return_value = {
            'status': 'needs_clarification',
            'can_proceed': False,
            'questions': [
                {
                    'priority': 'critical',
                    'question': 'Which files am I allowed to modify?',
                    'reason': 'P0-2 Scope Control'
                }
            ],
            'missing_context': ['file_allowlist'],
            'assumptions': [],
            'required_files': []
        }
        mock_registry.return_value = mock_skill_registry
        
        args = Namespace(
            task="Add caching",
            files=None
        )
        
        result = cmd_plan(args)
        
        # Should exit with error since can_proceed is False
        assert result == 1
        
        # Check that execute was called with empty visible_files and empty available_context
        call_args = mock_skill_registry.execute.call_args
        assert call_args[1]['input_data']['visible_files'] == []
        assert call_args[1]['input_data']['available_context'] == {}
    
    @patch('agentic_system.cli.setup_logging')
    @patch('agentic_system.cli.get_skill_registry')
    def test_plan_with_files(self, mock_registry, mock_logging):
        """Test plan command with FILES parameter populates file_allowlist."""
        # Setup mock
        mock_skill_registry = Mock()
        mock_skill_registry.execute.return_value = {
            'status': 'ready',
            'can_proceed': True,
            'questions': [],
            'missing_context': [],
            'assumptions': ['Working with specified files'],
            'required_files': []
        }
        mock_registry.return_value = mock_skill_registry
        
        args = Namespace(
            task="Add caching",
            files="src/file1.py,src/file2.py"
        )
        
        result = cmd_plan(args)
        
        # Should exit with success
        assert result == 0
        
        # Check that execute was called with correct parameters
        call_args = mock_skill_registry.execute.call_args
        input_data = call_args[1]['input_data']
        
        # Visible files should be populated
        assert input_data['visible_files'] == ["src/file1.py", "src/file2.py"]
        
        # Available context should include file_allowlist
        assert 'file_allowlist' in input_data['available_context']
        assert input_data['available_context']['file_allowlist'] == ["src/file1.py", "src/file2.py"]
    
    @patch('agentic_system.cli.setup_logging')
    @patch('agentic_system.cli.get_skill_registry')
    def test_plan_with_single_file(self, mock_registry, mock_logging):
        """Test plan command with single file."""
        mock_skill_registry = Mock()
        mock_skill_registry.execute.return_value = {
            'status': 'ready',
            'can_proceed': True,
            'questions': [],
            'missing_context': [],
            'assumptions': [],
            'required_files': []
        }
        mock_registry.return_value = mock_skill_registry
        
        args = Namespace(
            task="Fix bug",
            files="src/main.py"
        )
        
        result = cmd_plan(args)
        
        assert result == 0
        
        call_args = mock_skill_registry.execute.call_args
        input_data = call_args[1]['input_data']
        
        assert input_data['visible_files'] == ["src/main.py"]
        assert input_data['available_context']['file_allowlist'] == ["src/main.py"]


class TestCmdReview:
    """Test cmd_review function."""
    
    @patch('agentic_system.cli.setup_logging')
    @patch('agentic_system.cli.get_agent_registry')
    def test_review_with_violations(self, mock_agent_registry, mock_logging):
        """Test review command detects violations."""
        mock_registry = Mock()
        mock_agent = Mock()
        mock_agent.run.return_value = {
            'status': 'violations',
            'p0_violations': [
                {'rule': 'P0-5', 'file': 'src/test.py', 'message': 'No test file'}
            ],
            'p1_violations': [],
            'p2_violations': [],
            'passed_checks': []
        }
        mock_registry.get.return_value = mock_agent
        mock_agent_registry.return_value = mock_registry
        
        args = Namespace(files="src/test.py")
        
        result = cmd_review(args)
        
        # Should exit with error due to violations
        assert result == 1
    
    @patch('agentic_system.cli.setup_logging')
    @patch('agentic_system.cli.get_agent_registry')
    def test_review_without_violations(self, mock_agent_registry, mock_logging):
        """Test review command with clean code."""
        mock_registry = Mock()
        mock_agent = Mock()
        mock_agent.run.return_value = {
            'status': 'compliant',
            'summary': 'All checks passed',
            'next_steps': [],
            'result': {
                'p0_violations': [],
                'p1_violations': [],
                'p2_violations': [],
                'passed_checks': ['P0-5', 'P1-6']
            }
        }
        mock_registry.get.return_value = mock_agent
        mock_agent_registry.return_value = mock_registry
        
        args = Namespace(files="src/test.py,tests/test_test.py", pr_description=None)
        
        result = cmd_review(args)
        
        # Should exit successfully
        assert result == 0


class TestCmdCheckCompliance:
    """Test cmd_check_compliance function."""
    
    @patch('agentic_system.cli.setup_logging')
    @patch('agentic_system.cli.get_skill_registry')
    @patch('agentic_system.cli.Path')
    def test_check_compliance_blocking_violations(self, mock_path, mock_registry, mock_logging):
        """Test compliance check with blocking violations."""
        # Mock Path.exists to return True
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_text.return_value = "# test code"
        mock_path.return_value = mock_path_instance
        
        mock_skill_registry = Mock()
        mock_skill_registry.execute.return_value = {
            'compliance_status': 'violations',
            'total_files_modified': 2,
            'total_lines_changed': 50,
            'p0_violations': [
                {'rule_id': 'P0-5', 'file': 'src/main.py', 'message': 'No tests'}
            ],
            'p1_violations': [],
            'p2_suggestions': []
        }
        mock_registry.return_value = mock_skill_registry
        
        args = Namespace(
            pr_files="src/main.py,src/utils.py",
            planned_files=None,
            pr_description=None
        )
        
        result = cmd_check_compliance(args)
        
        # Should exit with error
        assert result == 1
    
    @patch('agentic_system.cli.setup_logging')
    @patch('agentic_system.cli.get_skill_registry')
    @patch('agentic_system.cli.Path')
    def test_check_compliance_clean(self, mock_path, mock_registry, mock_logging):
        """Test compliance check with no violations."""
        # Mock Path.exists to return True
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_text.return_value = "# test code"
        mock_path.return_value = mock_path_instance
        
        mock_skill_registry = Mock()
        mock_skill_registry.execute.return_value = {
            'compliance_status': 'compliant',
            'total_files_modified': 2,
            'total_lines_changed': 50,
            'p0_violations': [],
            'p1_violations': [],
            'p2_suggestions': []
        }
        mock_registry.return_value = mock_skill_registry
        
        args = Namespace(
            pr_files="src/main.py,tests/test_main.py",
            planned_files=None,
            pr_description=None
        )
        
        result = cmd_check_compliance(args)
        
        # Should exit successfully
        assert result == 0
    
    @patch('agentic_system.cli.setup_logging')
    @patch('agentic_system.cli.get_skill_registry')
    @patch('agentic_system.cli.Path')
    def test_check_compliance_non_blocking_violations(self, mock_path, mock_registry, mock_logging):
        """Test compliance check with only P2 violations (non-blocking)."""
        # Mock Path.exists to return True
        mock_path_instance = Mock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.read_text.return_value = "# test code"
        mock_path.return_value = mock_path_instance
        
        mock_skill_registry = Mock()
        mock_skill_registry.execute.return_value = {
            'compliance_status': 'compliant',
            'total_files_modified': 2,
            'total_lines_changed': 30,
            'p0_violations': [],
            'p1_violations': [],
            'p2_suggestions': [
                {'rule_id': 'P2-10', 'file': 'src/main.py', 'message': 'Missing docstring'}
            ]
        }
        mock_registry.return_value = mock_skill_registry
        
        args = Namespace(
            pr_files="src/main.py,tests/test_main.py",
            planned_files=None,
            pr_description=None
        )
        
        result = cmd_check_compliance(args)
        
        # Should exit successfully (P2 warnings don't block)
        assert result == 0
