"""
Translate Skill

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


class TranslateInput(BaseModel):
    """Input schema for Translate skill."""
    
    text: str = Field(..., description="Text to translate")
    target_language: str = Field(
        default="en",
        description="Target language for translation (e.g., 'en', 'es', 'fa', 'ar')"
    )
    source_language: str = Field(
        default="auto",
        description="Source language (use 'auto' for auto-detection)"
    )


class TranslateOutput(BaseModel):
    """Output schema for Translate skill."""
    
    translated_text: str = Field(..., description="The translated text")
    source_language: str | None = Field(
        default=None,
        description="Detected or specified source language"
    )
    target_language: str = Field(..., description="Target language used")


class TranslateSkill(Skill):
    """
    Translate Skill.
    
    TODO: Add detailed skill description.
    
    Context: What problem does this skill solve?
    Contract: What are the input/output guarantees?
    Invariants: What constraints are always maintained?
    Side Effects: What external systems does this interact with?
    
    Example:
        >>> result = skill.execute({
        ...     "text": "Hello, world!"
        ... }, context)
        >>> assert "result" in result
    """
    
    def spec(self) -> SkillSpec:
        """Return skill specification."""
        return SkillSpec(
            name="translate",
            version="1.0.0",
            side_effect=SideEffect.NETWORK,  # Uses LLM API for translation
            timeout_s=60,  # Increased for LLM calls
            idempotent=True,  # Same input always gives same translation
        )
    
    def input_model(self) -> type[BaseModel]:
        """Return input model for validation."""
        return TranslateInput
    
    def output_model(self) -> type[BaseModel]:
        """Return output model for validation."""
        return TranslateOutput
    
    def _execute(
        self,
        input_data: TranslateInput,
        context: ExecutionContext,
    ) -> TranslateOutput:
        """
        Execute translation using LLM gateway.
        
        Args:
            input_data: Validated input data with text and target language
            context: Execution context with trace_id, job_id, agent_id
        
        Returns:
            Validated output data with translated text
        
        Raises:
            SkillError: If translation fails
        """
        logger.info(
            f"Executing {self.spec().name} skill",
            extra={
                "trace_id": context.trace_id,
                "job_id": context.job_id,
                "agent_id": context.agent_id,
            }
        )
        
        # Import registry to call LLM skill
        from agentic_system.runtime.registry import get_skill_registry
        
        registry = get_skill_registry()
        
        # Prepare language names for better prompt clarity
        language_names = {
            "en": "English",
            "es": "Spanish",
            "fa": "Farsi (Persian)",
            "ar": "Arabic",
            "fr": "French",
            "de": "German",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "ru": "Russian",
            "pt": "Portuguese",
            "it": "Italian",
        }
        
        target_lang_name = language_names.get(
            input_data.target_language, 
            input_data.target_language
        )
        
        # Build translation prompt
        if input_data.source_language == "auto":
            prompt = f"""Translate the following text to {target_lang_name}.

Text to translate:
{input_data.text}

Provide ONLY the translation, without any explanations or additional text."""
        else:
            source_lang_name = language_names.get(
                input_data.source_language,
                input_data.source_language
            )
            prompt = f"""Translate the following text from {source_lang_name} to {target_lang_name}.

Text to translate:
{input_data.text}

Provide ONLY the translation, without any explanations or additional text."""
        
        logger.info(
            f"Calling LLM for translation to {target_lang_name}",
            extra={
                "trace_id": context.trace_id,
                "target_language": input_data.target_language,
            }
        )
        
        # Call the LLM gateway skill with correct input format
        llm_result = registry.execute(
            name="llm.anthropic_gateway",
            input_data={
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 2000,  # Sufficient for most translations
                "temperature": 0.3,  # Low temperature for consistent translation
            },
            context=context,
        )
        
        translated_text = llm_result["response"].strip()
        
        logger.info(
            f"Translation completed",
            extra={
                "trace_id": context.trace_id,
                "original_length": len(input_data.text),
                "translated_length": len(translated_text),
            }
        )
        
        return TranslateOutput(
            translated_text=translated_text,
            source_language=input_data.source_language if input_data.source_language != "auto" else None,
            target_language=input_data.target_language,
        )
