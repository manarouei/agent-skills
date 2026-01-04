"""Tests for Knowledge Base loader."""

import json
import pytest
from pathlib import Path

from runtime.kb import KnowledgeBase, KBPattern, KBValidationError


class TestKBPattern:
    """Tests for KBPattern dataclass."""
    
    def test_create_pattern(self):
        """Test creating a KB pattern."""
        pattern = KBPattern(
            id="test-001",
            name="Test Pattern",
            category="auth",  # Use canonical category
            description="A test pattern",
            pattern={"type": "auth", "auth_type": "api_key"},
            examples=[{"input": "API call", "output": "Bearer token", "notes": ""}],
            confidence="high",
            sources=["Test source"],
        )
        
        assert pattern.id == "test-001"
        assert pattern.category == "auth"
        assert pattern.confidence == "high"
    
    def test_from_dict(self):
        """Test creating pattern from dict."""
        data = {
            "id": "dict-001",
            "name": "Dict Pattern",
            "category": "pagination",
            "description": "From dict",
            "pattern": {"type": "pagination", "style": "cursor"},
            "examples": [{"input": "ex1", "output": "ex2"}],
            "confidence": "medium",
            "sources": ["source1"],
            "created_at": "2025-01-15T00:00:00Z",
            "approved_by": "human",
        }
        
        pattern = KBPattern.from_dict(data)
        
        assert pattern.id == "dict-001"
        assert pattern.category == "pagination"
        assert len(pattern.examples) == 1
        assert pattern.approved_by == "human"


class TestKnowledgeBase:
    """Tests for KnowledgeBase loader."""
    
    @pytest.fixture
    def kb_with_patterns(self, tmp_path):
        """Create a KB with test patterns."""
        patterns_dir = tmp_path / "patterns"
        patterns_dir.mkdir()
        
        # Create auth patterns (canonical category)
        auth_patterns = [
            {
                "id": "auth-001",
                "name": "API Key Auth",
                "category": "auth",  # Canonical category
                "description": "API key header auth",
                "pattern": {"type": "auth", "auth_type": "api_key"},
                "examples": [{"input": "Stripe API", "output": "Bearer {key}"}],
                "confidence": "high",
                "sources": ["RFC"],
            }
        ]
        (patterns_dir / "auth.json").write_text(json.dumps(auth_patterns))
        
        # Create pagination patterns
        page_patterns = [
            {
                "id": "page-001",
                "name": "Cursor Pagination",
                "category": "pagination",
                "description": "Cursor-based pagination",
                "pattern": {"type": "pagination", "style": "cursor"},
                "examples": [{"input": "Slack API", "output": "next_cursor"}],
                "confidence": "high",
                "sources": ["API docs"],
            },
            {
                "id": "page-002",
                "name": "Offset Pagination",
                "category": "pagination",
                "description": "Offset/limit pagination",
                "pattern": {"type": "pagination", "style": "offset"},
                "examples": [{"input": "REST APIs", "output": "offset += limit"}],
                "confidence": "high",
                "sources": ["Common patterns"],
            },
        ]
        (patterns_dir / "pagination.json").write_text(json.dumps(page_patterns))
        
        return KnowledgeBase(tmp_path)
    
    def test_load_all(self, kb_with_patterns):
        """Test loading all patterns."""
        patterns = kb_with_patterns.load_all()
        
        assert len(patterns) == 3
        assert all(isinstance(p, KBPattern) for p in patterns)
    
    def test_get_by_category(self, kb_with_patterns):
        """Test getting patterns by category."""
        auth = kb_with_patterns.get_by_category("auth")  # Canonical category
        page = kb_with_patterns.get_by_category("pagination")
        
        assert len(auth) == 1
        assert len(page) == 2
        assert auth[0].id == "auth-001"
    
    def test_get_by_category_empty(self, kb_with_patterns):
        """Test getting patterns for nonexistent category."""
        patterns = kb_with_patterns.get_by_category("nonexistent")
        
        assert patterns == []
    
    def test_get_by_id(self, kb_with_patterns):
        """Test getting pattern by ID."""
        pattern = kb_with_patterns.get_by_id("page-001")
        
        assert pattern is not None
        assert pattern.name == "Cursor Pagination"
    
    def test_get_by_id_not_found(self, kb_with_patterns):
        """Test getting nonexistent pattern by ID."""
        pattern = kb_with_patterns.get_by_id("nonexistent")
        
        assert pattern is None
    
    def test_empty_kb(self, tmp_path):
        """Test KB with no patterns directory."""
        kb = KnowledgeBase(tmp_path)
        
        patterns = kb.load_all()
        
        assert patterns == []
    
    def test_caching(self, kb_with_patterns):
        """Test that patterns are cached after first load."""
        # First load
        patterns1 = kb_with_patterns.load_all()
        # Second load should use cache
        patterns2 = kb_with_patterns.load_all()
        
        # Same objects (cached)
        assert patterns1 is patterns2
    
    def test_get_categories(self, kb_with_patterns):
        """Test getting all categories."""
        # Load patterns first
        kb_with_patterns.load_all()
        categories = kb_with_patterns.get_categories()
        
        assert "auth" in categories  # Canonical category
        assert "pagination" in categories


class TestKBValidation:
    """Tests for KB pattern validation."""
    
    def test_validate_valid_entry(self, tmp_path):
        """Test validating a valid pattern entry."""
        kb = KnowledgeBase(tmp_path)
        
        valid_entry = {
            "id": "valid-001",
            "name": "Valid Pattern",
            "category": "auth",  # Use canonical category
            "description": "A valid pattern",
            "pattern": {"type": "auth", "auth_type": "api_key"},
            "examples": [{"input": "example", "output": "result"}],
            "confidence": "high",
            "sources": ["source"],
        }
        
        result = kb.validate_entry(valid_entry)
        
        assert result.valid is True
        assert result.errors == []
    
    def test_validate_missing_required_field(self, tmp_path):
        """Test validating pattern with missing required field."""
        kb = KnowledgeBase(tmp_path)
        
        invalid_entry = {
            "id": "invalid-001",
            "name": "Missing Category",
            # Missing: category, description, pattern, examples, confidence, sources
        }
        
        result = kb.validate_entry(invalid_entry)
        
        assert result.valid is False
        assert len(result.errors) > 0
    
    def test_validate_invalid_confidence(self, tmp_path):
        """Test validating pattern with invalid confidence value."""
        kb = KnowledgeBase(tmp_path)
        
        invalid_entry = {
            "id": "invalid-002",
            "name": "Bad Confidence",
            "category": "auth",  # Use canonical category
            "description": "desc",
            "pattern": {"type": "auth", "auth_type": "api_key"},
            "examples": [{"input": "ex", "output": "out"}],
            "confidence": "super-high",  # Invalid - must be high/medium/low
            "sources": ["src"],
        }
        
        result = kb.validate_entry(invalid_entry)
        
        assert result.valid is False
        assert any("confidence" in e.lower() for e in result.errors)

    def test_validate_invalid_category(self, tmp_path):
        """Test validating pattern with invalid category."""
        kb = KnowledgeBase(tmp_path)
        
        invalid_entry = {
            "id": "invalid-003",
            "name": "Bad Category",
            "category": "unknown_category",  # Invalid category
            "description": "desc",
            "pattern": {"type": "auth", "auth_type": "api_key"},
            "examples": [{"input": "ex", "output": "out"}],
        }
        
        result = kb.validate_entry(invalid_entry)
        
        assert result.valid is False
        assert any("category" in e.lower() for e in result.errors)

    def test_category_normalization(self, tmp_path):
        """Test that legacy categories are normalized to canonical."""
        from runtime.kb.loader import normalize_category
        
        # Legacy → canonical mapping
        assert normalize_category("authentication") == "auth"
        assert normalize_category("type_conversion") == "ts_to_python"
        assert normalize_category("async_to_sync") == "ts_to_python"
        
        # Canonical stays canonical
        assert normalize_category("auth") == "auth"
        assert normalize_category("pagination") == "pagination"

    def test_load_with_invalid_pattern_fails(self, tmp_path):
        """Test that loading invalid patterns raises KBValidationError."""
        patterns_dir = tmp_path / "patterns"
        patterns_dir.mkdir()
        
        # Create invalid pattern (missing required fields)
        invalid_patterns = [
            {
                "id": "bad-001",
                # Missing: name, category, description, pattern
            }
        ]
        (patterns_dir / "invalid.json").write_text(json.dumps(invalid_patterns))
        
        kb = KnowledgeBase(tmp_path)
        
        with pytest.raises(KBValidationError):
            kb.load_all()


class TestProductionKB:
    """Tests for the production KB patterns (in runtime/kb/patterns/)."""
    
    def test_load_production_kb(self):
        """Test loading the production knowledge base."""
        # Use the real KB directory
        kb_dir = Path(__file__).parent.parent / "runtime" / "kb"
        kb = KnowledgeBase(kb_dir)
        
        patterns = kb.load_all()
        
        # Should have patterns from auth, pagination, and ts_python_idioms
        assert len(patterns) > 0
    
    def test_production_patterns_valid(self):
        """Test that all production patterns are valid."""
        kb_dir = Path(__file__).parent.parent / "runtime" / "kb"
        kb = KnowledgeBase(kb_dir)
        
        patterns = kb.load_all()
        
        for pattern in patterns:
            # All required fields should be present
            assert pattern.id
            assert pattern.name
            assert pattern.category
            assert pattern.description
            assert pattern.pattern
            assert pattern.examples  # Can be list of dicts or list of strings
            # confidence and sources are optional in new format
            if pattern.confidence:
                assert pattern.confidence in ("high", "medium", "low")
    
    def test_production_auth_patterns(self):
        """Test auth patterns in production KB."""
        kb_dir = Path(__file__).parent.parent / "runtime" / "kb"
        kb = KnowledgeBase(kb_dir)
        
        # New format uses 'auth' category, not 'authentication'
        auth_patterns = kb.get_by_category("auth")
        
        # Should have BaseCredential, OAuth2, API Key patterns
        assert len(auth_patterns) >= 3
        
        ids = [p.id for p in auth_patterns]
        assert "auth-001" in ids  # BaseCredential
        assert "auth-002" in ids  # OAuth2
        assert "auth-003" in ids  # Service-specific OAuth
    
    def test_production_pagination_patterns(self):
        """Test pagination patterns in production KB."""
        kb_dir = Path(__file__).parent.parent / "runtime" / "kb"
        kb = KnowledgeBase(kb_dir)
        
        page_patterns = kb.get_by_category("pagination")
        
        # Should have cursor, offset, link header patterns
        assert len(page_patterns) >= 3
    
    def test_production_ts_python_idioms(self):
        """Test TypeScript→Python idioms in production KB."""
        kb_dir = Path(__file__).parent.parent / "runtime" / "kb"
        kb = KnowledgeBase(kb_dir)
        
        # These are spread across categories
        patterns = kb.load_all()
        
        # Find TS→Python conversion patterns
        ts_patterns = [p for p in patterns if "ts-py" in p.id]
        
        assert len(ts_patterns) >= 5
