"""Patches de infra para testes unitários.

Mocks os clientes externos (Supabase, Google, OpenAI) para que os módulos
possam ser importados sem variáveis de ambiente reais.
"""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True, scope="session")
def patch_external_clients():
    """Substitui todos os clientes de infra por mocks durante a sessão de testes."""
    with (
        patch("supabase.create_client", return_value=MagicMock()),
        patch("openai.AsyncOpenAI", return_value=MagicMock()),
        patch("langchain_google_genai.ChatGoogleGenerativeAI", return_value=MagicMock()),
        patch("google.generativeai.configure"),
        patch("google.generativeai.GenerativeModel", return_value=MagicMock()),
        patch("googleapiclient.discovery.build", return_value=MagicMock()),
        patch(
            "google.oauth2.service_account.Credentials.from_service_account_file",
            return_value=MagicMock(),
        ),
    ):
        yield
