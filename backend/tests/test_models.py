"""
Test: LLM Model Tiers (models.py)

Verifies that each model tier initializes correctly and uses the right
model name, base_url, and configuration.
"""

from unittest.mock import patch
import pytest


class TestModelTiers:
    """Verify each LLM tier initializes with correct config."""

    def setup_method(self):
        """Reset singletons before each test."""
        import app.models as models
        models._cheap_llm = None
        models._mid_llm = None
        models._premium_llm = None

    def test_cheap_llm_initializes(self):
        from app.models import get_cheap_llm
        llm = get_cheap_llm()
        assert llm is not None
        assert llm.temperature == 0
        assert "openrouter.ai" in str(llm.openai_api_base)

    def test_mid_llm_initializes(self):
        from app.models import get_mid_llm
        llm = get_mid_llm()
        assert llm is not None
        assert llm.temperature == 0

    def test_premium_llm_initializes(self):
        from app.models import get_premium_llm
        llm = get_premium_llm()
        assert llm is not None
        assert llm.temperature == 0

    def test_cheap_llm_is_singleton(self):
        from app.models import get_cheap_llm
        a = get_cheap_llm()
        b = get_cheap_llm()
        assert a is b

    def test_mid_llm_is_singleton(self):
        from app.models import get_mid_llm
        a = get_mid_llm()
        b = get_mid_llm()
        assert a is b

    def test_premium_llm_is_singleton(self):
        from app.models import get_premium_llm
        a = get_premium_llm()
        b = get_premium_llm()
        assert a is b

    def test_different_tiers_are_different_instances(self):
        from app.models import get_cheap_llm, get_mid_llm, get_premium_llm
        cheap = get_cheap_llm()
        mid = get_mid_llm()
        premium = get_premium_llm()
        assert cheap is not mid
        assert mid is not premium
        assert cheap is not premium

    def test_model_names_from_env(self):
        """Verify each tier uses the correct env var model name."""
        import os
        from app.models import get_cheap_llm, get_mid_llm, get_premium_llm

        cheap = get_cheap_llm()
        mid = get_mid_llm()
        premium = get_premium_llm()

        assert cheap.model_name == os.getenv("LLM_MODEL_CHEAP")
        assert mid.model_name == os.getenv("LLM_MODEL_MID")
        assert premium.model_name == os.getenv("LLM_MODEL_PREMIUM")
