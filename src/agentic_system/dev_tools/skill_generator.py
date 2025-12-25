"""Skill generator - Creates new skills from template."""
import os
import re
from pathlib import Path


def to_snake_case(name: str) -> str:
    """Convert name to snake_case."""
    # Insert underscore before uppercase letters and convert to lowercase
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def to_pascal_case(name: str) -> str:
    """Convert name to PascalCase."""
    return ''.join(word.capitalize() for word in name.split('_'))


def generate_skill(skill_name: str) -> None:
    """
    Generate a new skill from template.
    
    Args:
        skill_name: Name of the skill (e.g., 'translate' or 'text_classifier')
    """
    # Normalize names
    snake_name = to_snake_case(skill_name)
    pascal_name = to_pascal_case(snake_name)
    
    # Project root
    root = Path(__file__).parent.parent.parent.parent
    
    # Create skill Python file
    skill_file = root / "src" / "agentic_system" / "skills" / f"{snake_name}.py"
    skill_code = f'''"""
{pascal_name} Skill

TODO: Add description of what this skill does.
"""
from pydantic import BaseModel, Field

from agentic_system.observability import get_logger
from agentic_system.runtime import (
    ExecutionContext,
    SideEffect,
    Skill,
    SkillSpec,
)

logger = get_logger(__name__)


class {pascal_name}Input(BaseModel):
    """Input schema for {pascal_name} skill."""
    
    # TODO: Define your input fields
    text: str = Field(..., description="Input text to process")


class {pascal_name}Output(BaseModel):
    """Output schema for {pascal_name} skill."""
    
    # TODO: Define your output fields
    result: str = Field(..., description="Processing result")


class {pascal_name}Skill(Skill):
    """
    {pascal_name} Skill.
    
    TODO: Add detailed skill description.
    
    Context: What problem does this skill solve?
    Contract: What are the input/output guarantees?
    Invariants: What constraints are always maintained?
    Side Effects: What external systems does this interact with?
    
    Example:
        >>> result = skill.execute({{
        ...     "text": "Hello, world!"
        ... }}, context)
        >>> assert "result" in result
    """
    
    def spec(self) -> SkillSpec:
        """Return skill specification."""
        return SkillSpec(
            name="{snake_name}",
            version="1.0.0",
            side_effect=SideEffect.NONE,  # TODO: Change if skill has side effects
            timeout_s=30,
            idempotent=True,  # TODO: Change if skill is not idempotent
        )
    
    def input_model(self) -> type[BaseModel]:
        """Return input model for validation."""
        return {pascal_name}Input
    
    def output_model(self) -> type[BaseModel]:
        """Return output model for validation."""
        return {pascal_name}Output
    
    def _execute(
        self,
        input_data: {pascal_name}Input,
        context: ExecutionContext,
    ) -> {pascal_name}Output:
        """
        Execute {pascal_name} skill.
        
        Args:
            input_data: Validated input data
            context: Execution context with trace_id, job_id, agent_id
        
        Returns:
            Validated output data
        
        Raises:
            SkillError: If skill execution fails
        """
        logger.info(
            f"Executing {{self.spec().name}} skill",
            extra={{
                "trace_id": context.trace_id,
                "job_id": context.job_id,
                "agent_id": context.agent_id,
            }}
        )
        
        # TODO: Implement your skill logic here
        # For now, just echo the input
        result = f"Processed: {{input_data.text}}"
        
        return {pascal_name}Output(result=result)
'''
    
    skill_file.write_text(skill_code)
    print(f"✅ Created: {skill_file}")
    
    # Create test file
    test_file = root / "tests" / "unit" / f"test_{snake_name}_skill.py"
    test_code = f'''"""Tests for {pascal_name}Skill."""
import pytest
from unittest.mock import MagicMock

from agentic_system.runtime import ExecutionContext
from agentic_system.skills.{snake_name} import (
    {pascal_name}Skill,
    {pascal_name}Input,
    {pascal_name}Output,
)


class Test{pascal_name}Skill:
    """Test {pascal_name}Skill."""
    
    @pytest.fixture
    def skill(self):
        """Create skill instance."""
        return {pascal_name}Skill()
    
    @pytest.fixture
    def context(self):
        """Create execution context."""
        return ExecutionContext(
            trace_id="test-trace-123",
            job_id="test-job-456",
            agent_id="test-agent",
        )
    
    def test_skill_spec(self, skill):
        """Test skill spec returns correct metadata."""
        spec = skill.spec()
        assert spec.name == "{snake_name}"
        assert spec.version == "1.0.0"
        # TODO: Update assertions based on your spec
    
    def test_input_model(self, skill):
        """Test input_model returns correct type."""
        assert skill.input_model() == {pascal_name}Input
    
    def test_output_model(self, skill):
        """Test output_model returns correct type."""
        assert skill.output_model() == {pascal_name}Output
    
    def test_execute_basic(self, skill, context):
        """Test basic execution."""
        input_data = {pascal_name}Input(text="Hello, world!")
        result = skill.execute(input_data, context)
        
        assert "result" in result
        assert isinstance(result["result"], str)
    
    def test_execute_with_dict_input(self, skill, context):
        """Test execution with dict input (validates conversion)."""
        input_dict = {{"text": "Test input"}}
        result = skill.execute(input_dict, context)
        
        assert "result" in result
    
    def test_input_validation(self, skill, context):
        """Test input validation catches invalid data."""
        with pytest.raises(Exception):  # Will be SkillValidationError
            skill.execute({{}}, context)  # Missing required field
    
    # TODO: Add more test cases:
    # - Edge cases (empty input, special characters, etc.)
    # - Error conditions
    # - Side effect verification (if applicable)
    # - Performance tests (if needed)
'''
    
    test_file.write_text(test_code)
    print(f"✅ Created: {test_file}")
    
    # Create SKILL.md documentation
    doc_dir = root / "skills" / snake_name
    doc_dir.mkdir(parents=True, exist_ok=True)
    doc_file = doc_dir / "SKILL.md"
    doc_content = f'''# {pascal_name} Skill

**Skill Name:** `{snake_name}`  
**Version:** `1.0.0`  
**Side Effect:** `NONE`  
**Idempotent:** Yes

## Purpose

TODO: Describe what this skill does and why it's useful.

## Input Schema

```python
{{
  "text": "Input text to process"  # TODO: Update with actual fields
}}
```

## Output Schema

```python
{{
  "result": "Processing result"  # TODO: Update with actual fields
}}
```

## Behavior

TODO: Describe the skill's behavior:
1. What processing does it perform?
2. What are the key steps?
3. What external services does it call (if any)?
4. What are the performance characteristics?

## Usage Example

```python
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.runtime import ExecutionContext

skill_registry = get_skill_registry()

context = ExecutionContext(
    trace_id="trace-123",
    job_id="job-456",
    agent_id="my_agent"
)

# Execute skill
result = skill_registry.execute(
    skill_name="{snake_name}",
    input_data={{
        "text": "Hello, world!"
    }},
    context=context,
)

print(result["result"])
```

## Error Handling

TODO: Document error conditions and how they're handled:
- What input validations are performed?
- What exceptions can be raised?
- What are the retry semantics (if any)?

## Testing

Run tests with:
```bash
make test-skill NAME={snake_name}
```

## Notes

TODO: Add any additional notes:
- Known limitations
- Performance considerations
- Future enhancements
- Related skills
'''
    
    doc_file.write_text(doc_content)
    print(f"✅ Created: {doc_file}")
    
    print(f"\n🎉 Skill '{snake_name}' generated successfully!")


def register_skill(skill_name: str) -> None:
    """
    Register skill in the system.
    
    Adds imports to:
    - src/agentic_system/skills/__init__.py
    - src/agentic_system/integrations/tasks.py (skill registry)
    
    Args:
        skill_name: Name of the skill to register
    """
    snake_name = to_snake_case(skill_name)
    pascal_name = to_pascal_case(snake_name)
    class_name = f"{pascal_name}Skill"
    
    root = Path(__file__).parent.parent.parent.parent
    
    # Update skills/__init__.py
    init_file = root / "src" / "agentic_system" / "skills" / "__init__.py"
    init_content = init_file.read_text()
    
    # Add import
    import_line = f"from agentic_system.skills.{snake_name} import {class_name}"
    if import_line not in init_content:
        # Find the last import and add after it
        lines = init_content.split('\n')
        import_idx = -1
        for i, line in enumerate(lines):
            if line.startswith('from agentic_system.skills.'):
                import_idx = i
        
        if import_idx >= 0:
            lines.insert(import_idx + 1, import_line)
            
            # Add to __all__
            all_start = -1
            all_end = -1
            for i, line in enumerate(lines):
                if line.startswith('__all__'):
                    all_start = i
                if all_start >= 0 and line.strip() == ']':
                    all_end = i
                    break
            
            if all_start >= 0 and all_end >= 0:
                # Add to __all__ before the closing bracket
                lines.insert(all_end, f'    "{class_name}",')
            
            init_file.write_text('\n'.join(lines))
            print(f"✅ Updated: {init_file}")
    
    # Update integrations/tasks.py
    tasks_file = root / "src" / "agentic_system" / "integrations" / "tasks.py"
    tasks_content = tasks_file.read_text()
    
    # Add import
    skill_import = f"from agentic_system.skills.{snake_name} import {class_name}"
    if skill_import not in tasks_content:
        # Find skills section and add import
        lines = tasks_content.split('\n')
        import_idx = -1
        for i, line in enumerate(lines):
            if 'from agentic_system.skills' in line:
                import_idx = i
        
        if import_idx >= 0:
            lines.insert(import_idx + 1, skill_import)
            
            # Add to skill registry initialization
            register_line = f'    "{snake_name}": {class_name}(),'
            for i, line in enumerate(lines):
                if 'skill_registry.register(' in line:
                    # Found a registration, add ours after similar ones
                    lines.insert(i, register_line)
                    break
            
            tasks_file.write_text('\n'.join(lines))
            print(f"✅ Updated: {tasks_file}")
    
    print(f"\n✅ Skill '{snake_name}' registered in system!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python skill_generator.py <skill_name>")
        sys.exit(1)
    
    skill_name = sys.argv[1]
    generate_skill(skill_name)
    
    print("\nWould you like to register this skill now? (y/n)")
    response = input().strip().lower()
    if response == 'y':
        register_skill(skill_name)
