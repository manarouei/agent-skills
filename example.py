#!/usr/bin/env python3
"""
Example script demonstrating direct skill/agent usage (without API/Celery).

This shows how to use the runtime directly for testing or synchronous execution.
"""
import os

# Set test environment
os.environ["AGENTIC_ANTHROPIC_API_KEY"] = os.getenv(
    "AGENTIC_ANTHROPIC_API_KEY", "test-key"
)

from agentic_system.config import get_settings
from agentic_system.observability import setup_logging
from agentic_system.runtime import ExecutionContext, get_skill_registry
from agentic_system.skills import HealthCheckSkill, LLMGatewaySkill, SummarizeSkill


def main():
    """Run example usage of skills."""
    # Setup
    setup_logging()
    settings = get_settings()

    print("🚀 Agentic System - Example Usage")
    print("=" * 50)
    print()

    # Create execution context
    context = ExecutionContext(
        trace_id="example-trace-001",
        job_id="example-job-001",
        agent_id="example",
    )

    # Register skills
    skill_registry = get_skill_registry()
    skill_registry.register(LLMGatewaySkill())
    skill_registry.register(SummarizeSkill())
    skill_registry.register(HealthCheckSkill())

    print("📋 Registered skills:")
    for skill_key in skill_registry.list_skills():
        print(f"  - {skill_key}")
    print()

    # Example 1: HealthCheck skill (no side effects)
    print("Example 1: HealthCheck skill")
    print("-" * 50)
    healthcheck_result = skill_registry.execute(
        name="system.healthcheck",
        input_data={"include_config": True},
        context=context,
    )
    print(f"Status: {healthcheck_result['status']}")
    print(f"Environment: {healthcheck_result.get('environment', 'N/A')}")
    print(f"Model: {healthcheck_result.get('model', 'N/A')}")
    print()

    # Example 2: Summarize skill (requires valid API key)
    if settings.anthropic_api_key.get_secret_value() != "test-key":
        print("Example 2: Summarize skill")
        print("-" * 50)
        print("⚠️  This will make a real API call to Anthropic")
        print()

        text = """
        The quick brown fox jumps over the lazy dog. This is a classic pangram 
        used in typography and font design. It contains every letter of the 
        English alphabet at least once, making it useful for displaying fonts 
        and testing keyboards. The phrase has been used since the late 19th 
        century and remains popular today in the digital age.
        """

        try:
            summarize_result = skill_registry.execute(
                name="text.summarize",
                input_data={
                    "text": text.strip(),
                    "max_words": 30,
                },
                context=context,
            )
            print(f"Summary: {summarize_result['summary']}")
            print()
        except Exception as e:
            print(f"❌ Error: {e}")
            print()
    else:
        print("Example 2: Summarize skill")
        print("-" * 50)
        print("⏭️  Skipped (requires valid AGENTIC_ANTHROPIC_API_KEY)")
        print()

    print("✅ Examples complete!")
    print()
    print("Next steps:")
    print("  - Start the full system: make start-infra && make start-api")
    print("  - Try the API: http://localhost:8000/docs")
    print("  - Read the docs: README.md")


if __name__ == "__main__":
    main()
