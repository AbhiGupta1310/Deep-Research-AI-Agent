"""
Test: LLM Model Tiers (models.py)
"""

import os
import pytest
from unittest.mock import patch
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)


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
        assert llm.temperature == pytest.approx(0, abs=1e-6)  # ← fix
        assert "openrouter.ai" in str(llm.openai_api_base)

    def test_mid_llm_initializes(self):
        from app.models import get_mid_llm
        llm = get_mid_llm()
        assert llm is not None
        assert llm.temperature == pytest.approx(0, abs=1e-6)  # ← fix

    def test_premium_llm_initializes(self):
        from app.models import get_premium_llm
        llm = get_premium_llm()
        assert llm is not None
        assert llm.temperature == pytest.approx(0, abs=1e-6)  # ← fix

    def test_cheap_llm_is_singleton(self):
        from app.models import get_cheap_llm
        assert get_cheap_llm() is get_cheap_llm()

    def test_mid_llm_is_singleton(self):
        from app.models import get_mid_llm
        assert get_mid_llm() is get_mid_llm()

    def test_premium_llm_is_singleton(self):
        from app.models import get_premium_llm
        assert get_premium_llm() is get_premium_llm()

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
        from app.models import get_cheap_llm, get_mid_llm, get_premium_llm

        assert get_cheap_llm().model_name == os.getenv("LLM_MODEL_CHEAP")
        assert get_mid_llm().model_name == os.getenv("LLM_MODEL_MID")
        assert get_premium_llm().model_name == os.getenv("LLM_MODEL_PREMIUM")