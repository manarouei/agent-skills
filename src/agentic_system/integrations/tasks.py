"""Celery tasks for agent execution."""
from agentic_system.agents import BoundedAutonomyAgent, SimpleSummarizerAgent
from agentic_system.integrations.celery_app import celery_app
from agentic_system.observability import get_logger, setup_logging
from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_agent_registry, get_skill_registry
from agentic_system.skills import (
    CodeReviewSkill,
    ContextGateSkill,
    HealthCheckSkill,
    LLMGatewaySkill,
    OpenAITranslateSkill,
    SummarizeSkill,
    TranslateSkill,
)
from agentic_system.storage import get_execution_store, JobStatus

# Setup logging
setup_logging()
logger = get_logger(__name__)


def register_skills_and_agents() -> None:
    """Register all skills and agents."""
    skill_registry = get_skill_registry()
    agent_registry = get_agent_registry()

    # Register skills (LLM Gateway MUST be registered first)
    llm_gateway_skill = LLMGatewaySkill()
    skill_registry.register(llm_gateway_skill)

    summarize_skill = SummarizeSkill()
    skill_registry.register(summarize_skill)

    healthcheck_skill = HealthCheckSkill()
    skill_registry.register(healthcheck_skill)

    # Register translate skill
    translate_skill = TranslateSkill()
    skill_registry.register(translate_skill)

    # Register OpenAI translate skill
    openai_translate_skill = OpenAITranslateSkill()
    skill_registry.register(openai_translate_skill)

    # Register bounded autonomy skills
    context_gate_skill = ContextGateSkill()
    skill_registry.register(context_gate_skill)

    code_review_skill = CodeReviewSkill()
    skill_registry.register(code_review_skill)

    # Register agents
    simple_summarizer_agent = SimpleSummarizerAgent()
    agent_registry.register(simple_summarizer_agent)

    bounded_autonomy_agent = BoundedAutonomyAgent()
    agent_registry.register(bounded_autonomy_agent)

    logger.info("Skills and agents registered")


# Register on module import
register_skills_and_agents()


@celery_app.task(name="run_job", bind=True)
def run_job(self, job_id: str) -> dict:
    """
    Execute a job by ID.

    Args:
        job_id: Job ID to execute

    Returns:
        Result dict
    """
    store = get_execution_store()

    # Get job
    job = store.get_job(job_id)
    if job is None:
        logger.error(f"Job not found: {job_id}")
        return {"error": "Job not found"}

    logger.info(
        "Starting job execution",
        extra={
            "job_id": job_id,
            "agent_id": job.agent_id,
            "trace_id": job.trace_id,
        },
    )

    try:
        # Update status to running
        store.set_status(job_id, JobStatus.RUNNING)

        # Create execution context
        context = ExecutionContext(
            trace_id=job.trace_id,
            job_id=job_id,
            agent_id=job.agent_id,
        )

        # Get agent and run
        agent_registry = get_agent_registry()
        agent = agent_registry.get(job.agent_id)

        if agent is None:
            raise ValueError(f"Agent not found: {job.agent_id}")

        result = agent.run(job.input_data, context)

        # Store result
        store.set_result(job_id, result)

        logger.info(
            "Job completed successfully",
            extra={
                "job_id": job_id,
                "trace_id": job.trace_id,
            },
        )

        return result

    except Exception as e:
        logger.error(
            "Job execution failed",
            extra={
                "job_id": job_id,
                "trace_id": job.trace_id,
                "error": str(e),
            },
            exc_info=True,
        )
        store.set_status(job_id, JobStatus.FAILED, error=str(e))
        raise
