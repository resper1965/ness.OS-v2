"""Public integration exports, loaded only when requested."""

__all__ = [
    "ZabbixClient",
    "generate_postmortem",
    "notify_incident_created",
    "notify_postmortem_ready",
]


def __getattr__(name):
    if name == "ZabbixClient":
        from app.integrations.zabbix import ZabbixClient

        return ZabbixClient
    if name == "generate_postmortem":
        from app.integrations.gemini import generate_postmortem

        return generate_postmortem
    if name == "notify_incident_created":
        from app.integrations.n8n import notify_incident_created

        return notify_incident_created
    if name == "notify_postmortem_ready":
        from app.integrations.n8n import notify_postmortem_ready

        return notify_postmortem_ready
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
