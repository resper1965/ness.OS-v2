"""Public integration exports, loaded only when requested."""

__all__ = [
    "ZabbixClient",
    "generate_postmortem",
]


def __getattr__(name):
    if name == "ZabbixClient":
        from app.integrations.zabbix import ZabbixClient

        return ZabbixClient
    if name == "generate_postmortem":
        from app.integrations.gemini import generate_postmortem

        return generate_postmortem
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
