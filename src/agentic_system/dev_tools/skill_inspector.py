"""Skill inspector - Show detailed skill information."""
import importlib
from pathlib import Path

from agentic_system.runtime.registry import get_skill_registry


def to_snake_case(name: str) -> str:
    """Convert name to snake_case."""
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def to_pascal_case(name: str) -> str:
    """Convert name to PascalCase."""
    return ''.join(word.capitalize() for word in name.split('_'))


def inspect_skill(skill_name: str) -> None:
    """
    Show detailed information about a skill.
    
    Args:
        skill_name: Name of the skill to inspect
    """
    # Import and register all skills first
    from agentic_system.integrations.tasks import register_skills_and_agents
    register_skills_and_agents()
    
    snake_name = to_snake_case(skill_name)
    
    print(f"\n{'=' * 70}")
    print(f"SKILL INFORMATION: {snake_name}")
    print('=' * 70)
    
    # Get from registry
    try:
        registry = get_skill_registry()
        
        # Try exact match first
        if snake_name in registry._skills:
            skill_key = snake_name
        else:
            # Try to find partial match (e.g., "summarize" matches "text.summarize")
            matches = [k for k in registry._skills.keys() if snake_name in k or k.endswith(f".{snake_name}")]
            if not matches:
                print(f"❌ Skill '{snake_name}' not found in registry")
                print(f"\nAvailable skills:")
                for name in sorted(registry._skills.keys()):
                    print(f"  - {name}")
                return
            elif len(matches) > 1:
                print(f"❌ Multiple skills match '{snake_name}':")
                for name in matches:
                    print(f"  - {name}")
                print(f"\nPlease be more specific.")
                return
            else:
                skill_key = matches[0]
        
        skill = registry._skills[skill_key]
        spec = skill.spec()
        
        # Basic info
        print(f"\n📦 SPECIFICATION")
        print(f"{'─' * 70}")
        print(f"Name:        {spec.name}")
        print(f"Version:     {spec.version}")
        print(f"Side Effect: {spec.side_effect.value}")
        print(f"Timeout:     {spec.timeout_s}s")
        print(f"Idempotent:  {spec.idempotent}")
        
        # Input/Output models
        input_model = skill.input_model()
        output_model = skill.output_model()
        
        print(f"\n📥 INPUT MODEL: {input_model.__name__}")
        print(f"{'─' * 70}")
        if hasattr(input_model, 'model_fields'):
            for field_name, field_info in input_model.model_fields.items():
                required = "required" if field_info.is_required() else "optional"
                field_type = field_info.annotation
                description = field_info.description or "No description"
                print(f"  • {field_name}: {field_type} ({required})")
                print(f"    {description}")
        
        print(f"\n📤 OUTPUT MODEL: {output_model.__name__}")
        print(f"{'─' * 70}")
        if hasattr(output_model, 'model_fields'):
            for field_name, field_info in output_model.model_fields.items():
                required = "required" if field_info.is_required() else "optional"
                field_type = field_info.annotation
                description = field_info.description or "No description"
                print(f"  • {field_name}: {field_type} ({required})")
                print(f"    {description}")
        
        # Docstring
        if skill.__doc__:
            print(f"\n📝 DESCRIPTION")
            print(f"{'─' * 70}")
            # Clean up docstring
            doc_lines = [line.strip() for line in skill.__doc__.strip().split('\n')]
            for line in doc_lines:
                if line:
                    print(f"  {line}")
        
        # File locations
        root = Path(__file__).parent.parent.parent.parent
        skill_file = root / "src" / "agentic_system" / "skills" / f"{snake_name}.py"
        test_file = root / "tests" / "unit" / f"test_{snake_name}_skill.py"
        doc_file = root / "skills" / snake_name / "SKILL.md"
        
        print(f"\n📁 FILES")
        print(f"{'─' * 70}")
        print(f"Implementation: {skill_file}")
        print(f"                {'✅ exists' if skill_file.exists() else '❌ missing'}")
        print(f"Tests:          {test_file}")
        print(f"                {'✅ exists' if test_file.exists() else '❌ missing'}")
        print(f"Documentation:  {doc_file}")
        print(f"                {'✅ exists' if doc_file.exists() else '❌ missing'}")
        
        # Usage example
        print(f"\n💡 USAGE EXAMPLE")
        print(f"{'─' * 70}")
        print(f"""
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.runtime import ExecutionContext

# Get skill registry
registry = get_skill_registry()

# Create execution context
context = ExecutionContext(
    trace_id="trace-123",
    job_id="job-456",
    agent_id="my_agent"
)

# Execute skill
result = registry.execute(
    skill_name="{snake_name}",
    input_data={{
        # Add your input fields here based on {input_model.__name__}
    }},
    context=context,
)

print(result)
""")
        
        # Related commands
        print(f"\n🔧 RELATED COMMANDS")
        print(f"{'─' * 70}")
        print(f"  make test-skill NAME={snake_name}       # Run tests")
        print(f"  make skill-docs NAME={snake_name}       # Show documentation")
        print(f"  make validate-skill NAME={snake_name}   # Validate implementation")
        if doc_file.exists():
            print(f"  cat {doc_file}  # Read full docs")
        
        print(f"\n{'=' * 70}\n")
        
    except Exception as e:
        print(f"❌ Error inspecting skill: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python skill_inspector.py <skill_name>")
        sys.exit(1)
    
    skill_name = sys.argv[1]
    inspect_skill(skill_name)
