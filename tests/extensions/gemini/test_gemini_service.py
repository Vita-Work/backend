from types import SimpleNamespace

import pytest
from src.extensions.gemini.gemini import GeminiCvExtractionService, GeminiIntegrationError


def test_parse_response_wraps_validation_errors() -> None:
    service = GeminiCvExtractionService(
        api_key="test-key",
        model="gemini-test",
    )

    response = SimpleNamespace(parsed={"missing_info": []}, text=None)

    with pytest.raises(GeminiIntegrationError, match="invalid extraction payload"):
        service._parse_response(response=response)
