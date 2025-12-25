"""Skill validator - Validates skill implementation."""
import importlib
import inspect
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agentic_system.runtime import Skill, SkillSpec, ExecutionContext


def to_snake_case(name: str) -> str:
    """Convert name to snake_case."""
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def to_pascal_case(name: str) -> str:
    """Convert name to PascalCase."""
    return ''.join(word.capitalize() for word in name.split('_'))


def validate_skill(skill_name: str) -> None:
    """
    Validate a skill implementation.
    
    Checks:
    - Skill class exists and inherits from Skill
    - Required methods are implemented (spec, input_model, output_model, _execute)
    - Input/Output models are Pydantic BaseModel subclasses
    - Spec is properly configured
    - Documentation exists
    
    Args:
        skill_name: Name of the skill to validate
    """
    snake_name = to_snake_case(skill_name)
    pascal_name = to_pascal_case(snake_name)
    class_name = f"{pascal_name}Skill"
    
    print(f"🔍 Validating skill: {snake_name}")
    print("=" * 60)
    
    errors = []
    warnings = []
    
    # 1. Check if skill file exists
    root = Path(__file__).parent.parent.parent.parent
    skill_file = root / "src" / "agentic_system" / "skills" / f"{snake_name}.py"
    
    if not skill_file.exists():
        errors.append(f"❌ Skill file not found: {skill_file}")
        print("\n".join(errors))
        return
    
    print(f"✅ Skill file exists: {skill_file}")
    
    # 2. Try to import the skill
    try:
        module = importlib.import_module(f"agentic_system.skills.{snake_name}")
        print(f"✅ Skill module imports successfully")
    except Exception as e:
        errors.append(f"❌ Failed to import skill: {e}")
        print("\n".join(errors))
        return
    
    # 3. Check if skill class exists
    if not hasattr(module, class_name):
        errors.append(f"❌ Skill class '{class_name}' not found in module")
        print("\n".join(errors))
        return
    
    skill_class = getattr(module, class_name)
    print(f"✅ Skill class '{class_name}' found")
    
    # 4. Check inheritance
    if not issubclass(skill_class, Skill):
        errors.append(f"❌ {class_name} does not inherit from Skill base class")
    else:
        print(f"✅ Skill inherits from Skill base class")
    
    # 5. Instantiate skill
    try:
        skill_instance = skill_class()
        print(f"✅ Skill instantiates successfully")
    except Exception as e:
        errors.append(f"❌ Failed to instantiate skill: {e}")
        print("\n".join(errors))
        return
    
    # 6. Check required methods
    required_methods = ['spec', 'input_model', 'output_model', '_execute']
    for method in required_methods:
        if not hasattr(skill_instance, method):
            errors.append(f"❌ Missing required method: {method}")
        else:
            print(f"✅ Method '{method}' implemented")
    
    # 7. Validate spec()
    try:
        spec = skill_instance.spec()
        if not isinstance(spec, SkillSpec):
            errors.append(f"❌ spec() must return SkillSpec, got {type(spec)}")
        else:
            print(f"✅ spec() returns SkillSpec")
            print(f"   - name: {spec.name}")
            print(f"   - version: {spec.version}")
            print(f"   - side_effect: {spec.side_effect}")
            print(f"   - timeout_s: {spec.timeout_s}")
            print(f"   - idempotent: {spec.idempotent}")
            
            # Check if name matches convention
            if spec.name != snake_name:
                warnings.append(f"⚠️  Spec name '{spec.name}' doesn't match file name '{snake_name}'")
    except Exception as e:
        errors.append(f"❌ spec() failed: {e}")
    
    # 8. Validate input_model()
    try:
        input_model = skill_instance.input_model()
        if not (inspect.isclass(input_model) and issubclass(input_model, BaseModel)):
            errors.append(f"❌ input_model() must return Pydantic BaseModel class, got {input_model}")
        else:
            print(f"✅ input_model() returns Pydantic BaseModel: {input_model.__name__}")
            # Show fields
            if hasattr(input_model, 'model_fields'):
                fields = input_model.model_fields
                print(f"   Fields: {', '.join(fields.keys())}")
    except Exception as e:
        errors.append(f"❌ input_model() failed: {e}")
    
    # 9. Validate output_model()
    try:
        output_model = skill_instance.output_model()
        if not (inspect.isclass(output_model) and issubclass(output_model, BaseModel)):
            errors.append(f"❌ output_model() must return Pydantic BaseModel class, got {output_model}")
        else:
            print(f"✅ output_model() returns Pydantic BaseModel: {output_model.__name__}")
            # Show fields
            if hasattr(output_model, 'model_fields'):
                fields = output_model.model_fields
                print(f"   Fields: {', '.join(fields.keys())}")
    except Exception as e:
        errors.append(f"❌ output_model() failed: {e}")
    
    # 10. Check _execute signature
    try:
        sig = inspect.signature(skill_instance._execute)
        params = list(sig.parameters.keys())
        if params != ['input_data', 'context']:
            warnings.append(f"⚠️  _execute signature unusual: {params} (expected ['input_data', 'context'])")
        else:
            print(f"✅ _execute() has correct signature")
    except Exception as e:
        warnings.append(f"⚠️  Could not inspect _execute signature: {e}")
    
    # 11. Check test file exists
    test_file = root / "tests" / "unit" / f"test_{snake_name}_skill.py"
    if not test_file.exists():
        warnings.append(f"⚠️  Test file not found: {test_file}")
    else:
        print(f"✅ Test file exists: {test_file}")
    
    # 12. Check documentation exists
    doc_file = root / "skills" / snake_name / "SKILL.md"
    if not doc_file.exists():
        warnings.append(f"⚠️  Documentation not found: {doc_file}")
    else:
        print(f"✅ Documentation exists: {doc_file}")
    
    # 13. Check if skill is registered
    try:
        from agentic_system.runtime.registry import get_skill_registry
        registry = get_skill_registry()
        if spec.name in registry._skills:
            print(f"✅ Skill is registered in skill registry")
        else:
            warnings.append(f"⚠️  Skill not registered in skill registry (run: make register-skill NAME={snake_name})")
    except Exception as e:
        warnings.append(f"⚠️  Could not check registration: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    if errors:
        print("\n❌ ERRORS:")
        for error in errors:
            print(f"  {error}")
    
    if warnings:
        print("\n⚠️  WARNINGS:")
        for warning in warnings:
            print(f"  {warning}")
    
    if not errors and not warnings:
        print("✅ All checks passed! Skill is ready to use.")
    elif not errors:
        print("\n✅ No blocking errors. Skill should work but has warnings.")
    else:
        print(f"\n❌ Found {len(errors)} error(s). Please fix before using.")
    
    print("\nNext steps:")
    if errors:
        print("  1. Fix errors listed above")
        print(f"  2. Run: make validate-skill NAME={snake_name}")
    else:
        print(f"  1. Run: make test-skill NAME={snake_name}")
        if f"⚠️  Skill not registered" in str(warnings):
            print(f"  2. Run: make register-skill NAME={snake_name}")
        print(f"  3. Try skill: make skill-example NAME={snake_name}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python skill_validator.py <skill_name>")
        sys.exit(1)
    
    skill_name = sys.argv[1]
    validate_skill(skill_name)
