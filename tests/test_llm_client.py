from __future__ import annotations

from super_crypto.autoresearch import llm_client


def test_llm_client_loads_project_dotenv(tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                "LLM_BASE_URL=https://example.test/v1",
                "LLM_API_KEY=test-key",
                "LLM_MODEL=test-model",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(llm_client, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    client = llm_client.AutoResearchLLMClient.from_env()

    assert client is not None
    assert client.base_url == "https://example.test/v1"
    assert client.api_key == "test-key"
    assert client.model == "test-model"

