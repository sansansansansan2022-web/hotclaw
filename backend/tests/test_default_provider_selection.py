"""The manager and specialist Agents must honor the same provider selection."""

from app.agents.profile_agent import ProfileAgent
from app.llm.config import reload_llm_config
from app.llm.gateway import LLMGateway


def test_llm_default_provider_is_shared_by_manager_and_specialists(monkeypatch):
    with monkeypatch.context() as env:
        env.setenv("LLM_DEFAULT_PROVIDER", "deepseek")
        env.setenv("DEFAULT_PROVIDER", "dashscope")
        config = reload_llm_config()
        assert config.default_provider == "deepseek"
        assert ProfileAgent().get_effective_model_config({})["provider_id"] == "deepseek"
        assert LLMGateway(config=config, use_db_config=False).get_default_provider() == "deepseek"
    reload_llm_config()
