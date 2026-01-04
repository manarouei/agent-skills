"""Knowledge Base module."""
from .loader import (
    KnowledgeBase,
    KBPattern,
    KBValidationError,
    CANONICAL_CATEGORIES,
    CATEGORY_ALIASES,
    normalize_category,
)

__all__ = [
    "KnowledgeBase",
    "KBPattern",
    "KBValidationError",
    "CANONICAL_CATEGORIES",
    "CATEGORY_ALIASES",
    "normalize_category",
]
