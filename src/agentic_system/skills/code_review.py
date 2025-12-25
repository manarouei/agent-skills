"""
Code Review Skill

Validates code changes against bounded autonomy rules (P0/P1/P2).
Checks scope control, hallucination prevention, contract preservation, and test coverage.
"""

import re
from typing import Any
from pydantic import BaseModel, Field

from agentic_system.runtime import Skill, SkillSpec, SideEffect, ExecutionContext


class CodeReviewInput(BaseModel):
    """Input for code review skill."""
    
    modified_files: list[str] = Field(
        ...,
        description="List of file paths that were modified"
    )
    file_diffs: dict[str, str] = Field(
        ...,
        description="Map of file path to diff content"
    )
    planned_files: list[str] | None = Field(
        None,
        description="List of files that were planned to be modified (for scope check)"
    )
    pr_description: str | None = Field(
        None,
        description="PR description text"
    )
    check_imports: bool = Field(
        True,
        description="Whether to check for import statements that might be hallucinated"
    )


class Violation(BaseModel):
    """A single rule violation."""
    
    rule_id: str = Field(..., description="Rule identifier (e.g., P0-2)")
    severity: str = Field(..., description="P0 (blocking), P1 (warning), P2 (suggestion)")
    file: str | None = Field(None, description="File where violation occurs")
    message: str = Field(..., description="Description of the violation")


class CodeReviewOutput(BaseModel):
    """Output from code review skill."""
    
    compliance_status: str = Field(
        ...,
        description="Overall status: 'compliant', 'warnings', 'violations'"
    )
    p0_violations: list[Violation] = Field(
        default_factory=list,
        description="Blocking P0 violations"
    )
    p1_violations: list[Violation] = Field(
        default_factory=list,
        description="P1 warnings"
    )
    p2_suggestions: list[Violation] = Field(
        default_factory=list,
        description="P2 optional suggestions"
    )
    total_files_modified: int = Field(..., description="Count of modified files")
    total_lines_changed: int = Field(0, description="Approximate lines changed")
    recommendations: list[str] = Field(
        default_factory=list,
        description="Specific recommendations for improvement"
    )


class CodeReviewSkill(Skill):
    """
    Code Review Skill for bounded autonomy compliance.
    
    Context: Validates code changes against P0/P1/P2 rules defined in /docs/LLM_RULES.md.
    Contract: Input is file list + diffs, output is compliance report with violations.
    Invariants: P0 violations always block; P1 are warnings; P2 are suggestions.
    Side Effects: Read-only analysis of code changes.
    
    Example:
        >>> result = skill.execute({
        ...     "modified_files": ["src/skills/new.py"],
        ...     "file_diffs": {"src/skills/new.py": "..."}
        ... }, context)
        >>> assert result["compliance_status"] in ["compliant", "warnings", "violations"]
    """
    
    def spec(self) -> SkillSpec:
        """Return skill specification."""
        return SkillSpec(
            name="code_review",
            version="1.0.0",
            side_effect=SideEffect.NONE,
            timeout_s=60,
            idempotent=True,
        )
    
    def input_model(self) -> type[BaseModel]:
        """Return input model for validation."""
        return CodeReviewInput
    
    def output_model(self) -> type[BaseModel]:
        """Return output model for validation."""
        return CodeReviewOutput
    
    def _execute(self, input_data: CodeReviewInput, context: ExecutionContext) -> CodeReviewOutput:
        """Execute code review checks."""
        violations_p0: list[Violation] = []
        violations_p1: list[Violation] = []
        suggestions_p2: list[Violation] = []
        recommendations: list[str] = []
        
        total_lines = 0
        
        # P0-2: Scope Control - check if unplanned files were modified
        if input_data.planned_files is not None:
            unplanned = set(input_data.modified_files) - set(input_data.planned_files)
            if unplanned:
                violations_p0.append(Violation(
                    rule_id="P0-2",
                    severity="P0",
                    file=None,
                    message=f"Scope violation: Unplanned files modified: {', '.join(unplanned)}"
                ))
                recommendations.append("Only modify files in the approved allowlist")
        
        # Analyze each modified file
        for file_path in input_data.modified_files:
            diff_content = input_data.file_diffs.get(file_path, "")
            total_lines += self._count_changed_lines(diff_content)
            
            # P0-3: Check for potential hallucinated imports
            if input_data.check_imports:
                suspicious_imports = self._check_suspicious_imports(diff_content)
                if suspicious_imports:
                    violations_p0.append(Violation(
                        rule_id="P0-3",
                        severity="P0",
                        file=file_path,
                        message=f"Potentially hallucinated imports: {', '.join(suspicious_imports)}"
                    ))
                    recommendations.append(f"Verify that imports in {file_path} actually exist")
            
            # P0-5: Check for missing tests
            if self._is_code_file(file_path) and not self._is_test_file(file_path):
                has_test = any(
                    self._get_test_file_for(file_path) == test_file
                    for test_file in input_data.modified_files
                )
                if not has_test:
                    violations_p0.append(Violation(
                        rule_id="P0-5",
                        severity="P0",
                        file=file_path,
                        message=f"No test file modified for {file_path}"
                    ))
                    recommendations.append(f"Add/update tests in {self._get_test_file_for(file_path)}")
            
            # P1-6: Check for potential contract breakage
            if self._is_contract_file(file_path):
                contract_changes = self._check_contract_changes(diff_content)
                if contract_changes:
                    violations_p1.append(Violation(
                        rule_id="P1-6",
                        severity="P1",
                        file=file_path,
                        message=f"Potential contract change detected: {contract_changes}"
                    ))
                    recommendations.append("Verify breaking changes have migration plan")
            
            # P1-7: Check for docstrings in new functions/classes
            if self._has_new_definitions(diff_content):
                if not self._has_docstrings(diff_content):
                    violations_p1.append(Violation(
                        rule_id="P1-7",
                        severity="P1",
                        file=file_path,
                        message="New functions/classes without docstrings"
                    ))
                    recommendations.append(f"Add docstrings to new code in {file_path}")
            
            # P1-8: Check for direct LLM API usage
            if self._has_direct_llm_calls(diff_content):
                violations_p1.append(Violation(
                    rule_id="P1-8",
                    severity="P1",
                    file=file_path,
                    message="Direct LLM API call detected (should use LLMGatewaySkill)"
                ))
                recommendations.append("Route LLM calls through skill_registry.execute('llm.anthropic_gateway')")
        
        # P2-9: Check for incremental changes
        if total_lines > 500:
            suggestions_p2.append(Violation(
                rule_id="P2-9",
                severity="P2",
                file=None,
                message=f"Large change ({total_lines} lines). Consider breaking into smaller PRs."
            ))
        
        # Check PR description for symbol citations (P0-4)
        if input_data.pr_description:
            if not self._has_symbol_citations(input_data.pr_description):
                violations_p0.append(Violation(
                    rule_id="P0-4",
                    severity="P0",
                    file=None,
                    message="PR description missing exact symbol citations (ClassName.method_name)"
                ))
                recommendations.append("Add exact symbol citations to PR description")
        
        # Determine compliance status
        if violations_p0:
            status = "violations"
        elif violations_p1:
            status = "warnings"
        else:
            status = "compliant"
        
        return CodeReviewOutput(
            compliance_status=status,
            p0_violations=violations_p0,
            p1_violations=violations_p1,
            p2_suggestions=suggestions_p2,
            total_files_modified=len(input_data.modified_files),
            total_lines_changed=total_lines,
            recommendations=list(set(recommendations))  # Deduplicate
        )
    
    def _count_changed_lines(self, diff: str) -> int:
        """Count added/removed lines in diff."""
        lines = diff.split('\n')
        changed = sum(1 for line in lines if line.startswith(('+', '-')) and not line.startswith(('+++', '---')))
        return changed
    
    def _check_suspicious_imports(self, diff: str) -> list[str]:
        """Check for imports that might be hallucinated."""
        suspicious = []
        # Look for new imports in added lines
        lines = diff.split('\n')
        for line in lines:
            if line.startswith('+') and ('import ' in line or 'from ' in line):
                # Extract import statement
                match = re.search(r'(?:from|import)\s+([\w.]+)', line)
                if match:
                    module = match.group(1)
                    # Flag if it looks like a common hallucination pattern
                    if any(pattern in module for pattern in ['workflow_service', 'queue_service', 'BaseNode']):
                        suspicious.append(module)
        return suspicious
    
    def _is_code_file(self, file_path: str) -> bool:
        """Check if file is a Python code file."""
        return file_path.endswith('.py') and not file_path.endswith('__init__.py')
    
    def _is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file."""
        return '/tests/' in file_path or file_path.startswith('tests/')
    
    def _get_test_file_for(self, file_path: str) -> str:
        """Get expected test file path for a code file."""
        # src/agentic_system/skills/foo.py -> tests/unit/test_foo_skill.py
        if '/skills/' in file_path:
            filename = file_path.split('/')[-1].replace('.py', '')
            return f"tests/unit/test_{filename}_skill.py"
        elif '/agents/' in file_path:
            filename = file_path.split('/')[-1].replace('.py', '')
            return f"tests/unit/test_{filename}_agent.py"
        else:
            filename = file_path.split('/')[-1].replace('.py', '')
            return f"tests/unit/test_{filename}.py"
    
    def _is_contract_file(self, file_path: str) -> bool:
        """Check if file contains public contracts (APIs, models)."""
        return any(pattern in file_path for pattern in [
            '/api/routes/',
            '/runtime/contracts.py',
            '/skills/',
            '/agents/',
            'tasks.py'
        ])
    
    def _check_contract_changes(self, diff: str) -> str | None:
        """Check for potential breaking changes in contracts."""
        lines = diff.split('\n')
        for line in lines:
            # Look for removed/modified class fields or function signatures
            if line.startswith('-') and not line.startswith('---'):
                if re.search(r'(class |def |Field\(|@app\.(get|post|put|delete))', line):
                    return "Potential breaking change in API/model signature"
        return None
    
    def _has_new_definitions(self, diff: str) -> bool:
        """Check if diff includes new function or class definitions."""
        lines = diff.split('\n')
        return any(
            line.startswith('+') and re.search(r'^\+\s*(class |def )', line)
            for line in lines
        )
    
    def _has_docstrings(self, diff: str) -> bool:
        """Check if new definitions have docstrings."""
        lines = diff.split('\n')
        has_def = False
        for i, line in enumerate(lines):
            if line.startswith('+') and re.search(r'^\+\s*(class |def )', line):
                has_def = True
                # Check next few lines for docstring
                for j in range(i + 1, min(i + 5, len(lines))):
                    if '"""' in lines[j] or "'''" in lines[j]:
                        return True
        return not has_def  # If no new defs, pass the check
    
    def _has_direct_llm_calls(self, diff: str) -> bool:
        """Check for direct Anthropic API calls."""
        patterns = [
            r'httpx.*anthropic\.com',
            r'requests.*anthropic\.com',
            r'anthropic\.Client',
            r'from anthropic import',
        ]
        return any(re.search(pattern, diff, re.IGNORECASE) for pattern in patterns)
    
    def _has_symbol_citations(self, text: str) -> bool:
        """Check if text contains symbol citations like ClassName.method_name."""
        # Look for patterns like `ClassName.method()` or ClassName.method in path/to/file
        pattern = r'`?\w+\.\w+\(\)?`?.*in.*\.py|Modified `\w+\.\w+|Added `\w+`'
        return bool(re.search(pattern, text))
