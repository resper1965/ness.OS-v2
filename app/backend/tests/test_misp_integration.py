import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.triage_engine import TriageEngine, TriageAction
from app.integrations.misp import search_misp_ioc


@pytest.mark.asyncio
async def test_search_misp_ioc_unconfigured():
    """Quando misp_api_key está vazio, deve retornar found=False sem erro."""
    result = await search_misp_ioc("185.220.101.5")
    assert result["found"] is False
    assert result["match_count"] == 0


@pytest.mark.asyncio
async def test_search_misp_ioc_mocked_success():
    """Testa a resposta parseada do MISP quando um IOC é encontrado."""
    mock_response_data = {
        "response": {
            "Attribute": [
                {
                    "id": "101",
                    "event_id": "505",
                    "value": "185.220.101.5",
                    "Event": {
                        "info": "APT Campaign Cobalt Strike C2",
                        "threat_level_id": "1",
                        "date": "2026-07-20",
                        "Tag": [
                            {"name": "tlp:red"},
                            {
                                "name": 'misp-galaxy:mitre-attack-pattern="Cobalt Strike"'
                            },
                        ],
                    },
                    "Tag": [{"name": "malicious"}],
                }
            ]
        }
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data

    with (
        patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post,
        patch("app.integrations.misp.settings") as mock_settings,
    ):
        mock_settings.misp_url = "https://misp.test.local"
        mock_settings.misp_api_key = "test_key_123"
        mock_settings.misp_verify_cert = False
        mock_post.return_value = mock_resp

        result = await search_misp_ioc("185.220.101.5")

        assert result["found"] is True
        assert result["match_count"] == 1
        assert len(result["events"]) == 1
        assert result["events"][0]["event_id"] == "505"
        assert "APT Campaign Cobalt Strike C2" in result["events"][0]["info"]


def test_triage_engine_with_misp_intel():
    """Testa se o TriageEngine adiciona os +25 pontos adicionais quando o MISP encontra o IOC."""
    engine = TriageEngine()
    alert_data = {
        "level": 10,  # 10 * 4 = 40 pts
        "host": "srv-web-prod",  # prod = +15 pts
        "description": "Suspicious connection to external IP",
    }
    threat_intel = {
        "misp": {
            "query_value": "185.220.101.5",
            "found": True,
            "match_count": 2,
            "events": [{"event_id": "505", "info": "C2 Server"}],
        }
    }

    # Total score esperado: 40 (level) + 15 (prod host) + 25 (misp) = 80 pts (>= 75 -> TRIAGE_L1)
    result = engine.evaluate_alert(
        alert_data, threat_intel=threat_intel, fingerprint="fp_misp_test"
    )

    assert result.risk_score >= 75
    assert result.action in (TriageAction.TRIAGE_L1, TriageAction.TRIAGE_L2)
    assert result.llm_bypassed is False
    assert any("MISP Threat Intel" in reason for reason in result.reasons)
