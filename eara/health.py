"""Read-only health facade shared by GUI and CLI."""
from eara.platforms import default_services
from eara.platforms.base import PlatformServices, ServiceHealth


def inspect_services(services: PlatformServices | None = None) -> ServiceHealth:
    provider = default_services() if services is None else services
    return provider.inspect_services()
