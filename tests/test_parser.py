"""Tests for StackState envelope → NormalizedAlert."""

from uuid import UUID

from suseobs_mattermost.models.webhook import Envelope
from suseobs_mattermost.services.parser import envelope_to_normalized


def _minimal_open_payload() -> dict:
    return {
        "notificationId": "3e9992c3-f5a9-4c85-a0fb-f8730868cb66",
        "event": {
            "type": "open",
            "state": "CRITICAL",
            "title": "HTTP - response time is above 3 seconds",
            "triggeredTimeMs": 1701247920000,
        },
        "monitor": {
            "name": "HTTP - response time",
            "identifier": (
                "urn:stackpack:kubernetes-v2:shared:monitor:kubernetes-v2:http-response-time"
            ),
            "link": "https://stackstate.example.com/#/monitors/155483794918865",
            "tags": [],
        },
        "component": {
            "identifier": "urn:endpoint:/customer.example.com:192.168.0.123",
            "link": "https://stackstate.example.com/#/components/urn:endpoint:%2Fcustomer.example.com:192.168.0.123",
            "name": "Kafka",
            "type": "service",
            "tags": {"customer": "example_com"},
        },
        "notificationConfiguration": {"name": "example_com_webhook"},
        "metadata": {},
    }


def test_parse_open_event() -> None:
    env = Envelope.model_validate(_minimal_open_payload())
    n = envelope_to_normalized(env, suse_obs_base_url=None)
    assert n.summary == "HTTP - response time is above 3 seconds"
    assert n.severity == "CRITICAL"
    assert "open" in n.status
    assert n.resource_name == "Kafka"
    assert n.resource_type == "service"
    assert n.monitor_name == "HTTP - response time"
    assert "stackstate.example.com" in n.suse_obs_url
    assert n.notification_id == str(UUID("3e9992c3-f5a9-4c85-a0fb-f8730868cb66"))


def test_base_url_override() -> None:
    data = _minimal_open_payload()
    env = Envelope.model_validate(data)
    n = envelope_to_normalized(env, suse_obs_base_url="https://obs.company.example/")
    assert n.suse_obs_url == "https://obs.company.example"


def test_close_event() -> None:
    data = _minimal_open_payload()
    data["event"] = {"type": "close", "reason": "HealthStateResolved"}
    env = Envelope.model_validate(data)
    n = envelope_to_normalized(env, None)
    assert "closed" in n.status.lower()
    assert n.severity == "resolved"
    assert "HealthStateResolved" in n.error_details
