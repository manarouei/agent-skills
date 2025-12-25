"""Tests for configuration settings."""
import json
import pytest
from pydantic import ValidationError

from agentic_system.config.settings import Settings, get_settings, reset_settings


class TestSettings:
    """Test Settings configuration."""
    
    def test_settings_without_api_key(self, monkeypatch):
        """Test that Settings can be initialized without anthropic_api_key (for Copilot usage)."""
        # Clear any existing API key
        monkeypatch.delenv("AGENTIC_ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        
        # Should not raise an error - api_key is now optional
        settings = Settings()
        
        assert settings.anthropic_api_key is None
        # Note: env might be set to 'test' in conftest.py
        assert settings.env in ("development", "test")
        assert settings.log_level == "INFO"
    
    def test_settings_with_api_key(self, monkeypatch):
        """Test that Settings accepts anthropic_api_key when provided."""
        test_key = "sk-ant-test-key-123"
        monkeypatch.setenv("AGENTIC_ANTHROPIC_API_KEY", test_key)
        
        settings = Settings()
        
        assert settings.anthropic_api_key is not None
        assert settings.anthropic_api_key.get_secret_value() == test_key
    
    def test_settings_default_values(self, monkeypatch):
        """Test default values are set correctly."""
        monkeypatch.delenv("AGENTIC_ANTHROPIC_API_KEY", raising=False)
        
        settings = Settings()
        
        # Core settings (env might be 'test' in test environment)
        assert settings.env in ("development", "test")
        assert settings.log_level == "INFO"
        
        # Redis settings (test environment uses db 1)
        assert settings.redis_url in ("redis://localhost:6379/0", "redis://localhost:6379/1")
        
        # RabbitMQ settings
        assert settings.rabbitmq_url == "amqp://guest:guest@localhost:5672//"
        
        # Anthropic settings
        assert settings.anthropic_base_url == "https://api.anthropic.com"
        assert settings.anthropic_version == "2023-06-01"
        assert settings.anthropic_default_model == "claude-3-5-sonnet-20241022"
        
        # LLM budget controls
        assert settings.llm_max_tokens_cap == 4096
        assert settings.llm_default_max_cost_usd is None
        
        # Runtime limits
        assert settings.default_skill_timeout_s == 30
        assert settings.default_agent_step_limit == 10
        
        # Celery settings
        assert settings.celery_task_time_limit == 300
        assert settings.celery_task_soft_time_limit == 270
    
    def test_settings_env_prefix(self, monkeypatch):
        """Test that AGENTIC_ prefix works for environment variables."""
        monkeypatch.setenv("AGENTIC_ENV", "production")
        monkeypatch.setenv("AGENTIC_LOG_LEVEL", "DEBUG")
        monkeypatch.delenv("AGENTIC_ANTHROPIC_API_KEY", raising=False)
        
        settings = Settings()
        
        assert settings.env == "production"
        assert settings.log_level == "DEBUG"
    
    def test_llm_max_tokens_cap_validation(self, monkeypatch):
        """Test that llm_max_tokens_cap must be positive."""
        monkeypatch.setenv("AGENTIC_LLM_MAX_TOKENS_CAP", "0")
        monkeypatch.delenv("AGENTIC_ANTHROPIC_API_KEY", raising=False)
        
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        
        assert "llm_max_tokens_cap must be positive" in str(exc_info.value)
    
    def test_get_llm_pricing_default(self, monkeypatch):
        """Test default LLM pricing."""
        monkeypatch.delenv("AGENTIC_ANTHROPIC_API_KEY", raising=False)
        
        settings = Settings()
        pricing = settings.get_llm_pricing()
        
        assert "claude-3-5-sonnet-20241022" in pricing
        assert pricing["claude-3-5-sonnet-20241022"]["input_per_1k"] == 0.003
        assert pricing["claude-3-5-sonnet-20241022"]["output_per_1k"] == 0.015
        
        assert "claude-3-5-haiku-20241022" in pricing
        assert pricing["claude-3-5-haiku-20241022"]["input_per_1k"] == 0.001
        
        assert "claude-3-opus-20240229" in pricing
        assert pricing["claude-3-opus-20240229"]["input_per_1k"] == 0.015
    
    def test_get_llm_pricing_custom(self, monkeypatch):
        """Test custom LLM pricing from JSON."""
        custom_pricing = {
            "custom-model": {
                "input_per_1k": 0.01,
                "output_per_1k": 0.02
            }
        }
        monkeypatch.setenv("AGENTIC_LLM_PRICING_JSON", json.dumps(custom_pricing))
        monkeypatch.delenv("AGENTIC_ANTHROPIC_API_KEY", raising=False)
        
        settings = Settings()
        pricing = settings.get_llm_pricing()
        
        # Should have both default and custom pricing
        assert "claude-3-5-sonnet-20241022" in pricing
        assert "custom-model" in pricing
        assert pricing["custom-model"]["input_per_1k"] == 0.01
    
    def test_get_llm_pricing_invalid_json(self, monkeypatch):
        """Test that invalid JSON falls back to defaults."""
        monkeypatch.setenv("AGENTIC_LLM_PRICING_JSON", "invalid json")
        monkeypatch.delenv("AGENTIC_ANTHROPIC_API_KEY", raising=False)
        
        settings = Settings()
        pricing = settings.get_llm_pricing()
        
        # Should fall back to defaults
        assert "claude-3-5-sonnet-20241022" in pricing
    
    def test_get_settings_singleton(self, monkeypatch):
        """Test that get_settings returns singleton instance."""
        monkeypatch.delenv("AGENTIC_ANTHROPIC_API_KEY", raising=False)
        
        reset_settings()
        settings1 = get_settings()
        settings2 = get_settings()
        
        assert settings1 is settings2
    
    def test_reset_settings(self, monkeypatch):
        """Test that reset_settings clears the singleton."""
        monkeypatch.delenv("AGENTIC_ANTHROPIC_API_KEY", raising=False)
        
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()
        
        assert settings1 is not settings2
