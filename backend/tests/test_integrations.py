import asyncio
import json
from unittest.mock import patch

import httpx
from app.integrations import Observation, Providers, Settings
from elevenlabs.client import ElevenLabs
from openai import AsyncOpenAI


def test_elevenlabs_adapter_uses_real_sdk_signed_url_with_mock_http():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"signed_url": "wss://mock.elevenlabs.test/conversation"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        sdk = ElevenLabs(api_key="test-key", httpx_client=transport)
        settings = Settings(
            _env_file=None,
            elevenlabs_api_key="test-key",
            elevenlabs_interviewer_agent_id="agent_test",
        )
        with patch("app.integrations.ElevenLabs", return_value=sdk) as constructor:
            assert (
                Providers(settings).signed_url("interviewer")
                == "wss://mock.elevenlabs.test/conversation"
            )
    constructor.assert_called_once_with(api_key="test-key", timeout=20)
    assert requests[0].url.path == "/v1/convai/conversation/get-signed-url"
    assert requests[0].url.params["agent_id"] == "agent_test"
    assert requests[0].headers["xi-api-key"] == "test-key"


def test_openai_adapter_uses_real_sdk_structured_parse_with_mock_http():
    requests = []
    observed = {
        "summary": "The report shows software version 2.4.0.",
        "visible_case_id": "B",
        "confidence": "medium",
        "uncertain": ["Expert reasoning is not visible"],
    }

    def respond(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "status": "completed",
                "model": "gpt-4.1-mini",
                "parallel_tool_calls": False,
                "tool_choice": "auto",
                "tools": [],
                "output": [
                    {
                        "id": "msg_test",
                        "type": "message",
                        "role": "assistant",
                        "status": "completed",
                        "content": [
                            {"type": "output_text", "annotations": [], "text": json.dumps(observed)}
                        ],
                    }
                ],
            },
        )

    async def run():
        sdk = AsyncOpenAI(
            api_key="test-key",
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)),
        )
        with patch("app.integrations.AsyncOpenAI", return_value=sdk):
            result = await Providers(Settings(_env_file=None, openai_api_key="test-key")).observe(
                "data:image/jpeg;base64,/9j/2Q=="
            )
        assert isinstance(result, Observation)
        assert result.model_dump() == observed
        assert sdk.is_closed()

    asyncio.run(run())
    assert requests[0].url.path == "/v1/responses"
    body = json.loads(requests[0].content)
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["strict"] is True
    assert body["store"] is False
    assert body["input"][0]["content"][1]["type"] == "input_image"
    assert "untrusted data" in body["instructions"]


def test_settings_repr_does_not_expose_api_keys():
    settings = Settings(
        _env_file=None,
        openai_api_key="private-openai-value",
        elevenlabs_api_key="private-elevenlabs-value",
    )
    assert "private-openai-value" not in repr(settings)
    assert "private-elevenlabs-value" not in repr(settings)
