"""
Shared pytest fixtures.

Injects a deterministic StubDataProvider into the application's module-level services so
tests exercise analysis logic without requiring a live real-data source. Production code
itself never uses this stub and refuses to fabricate data when no source is configured.
"""

import pytest

from tests.stub_provider import StubDataProvider


def _install_stub_provider():
    provider = StubDataProvider()

    # Router-level module singletons
    from app.api.v1 import emiten as emiten_api
    from app.api.v1 import compare as compare_api
    from app.api.v1 import screener as screener_api
    from app.api.v1 import market as market_api

    for module in (emiten_api, compare_api, screener_api, market_api):
        if hasattr(module, "emiten_service"):
            module.emiten_service.provider = provider
        if hasattr(module, "screener_service"):
            module.screener_service.emiten_service.provider = provider
        if hasattr(module, "comparison_service"):
            module.comparison_service.emiten_service.provider = provider
        if hasattr(module, "market_service"):
            module.market_service.emiten_service.provider = provider

    return provider


@pytest.fixture(autouse=True)
def stub_data_source(monkeypatch):
    """Automatically route all EmitenService instances to the stub provider during tests."""
    provider = _install_stub_provider()

    # Make any newly constructed EmitenService default to the stub as well.
    from app.services import emiten_service as emiten_service_module

    original_init = emiten_service_module.EmitenService.__init__

    default_provider = provider

    def patched_init(self, provider=None):
        original_init(self, provider or default_provider)

    monkeypatch.setattr(emiten_service_module.EmitenService, "__init__", patched_init)
    yield provider
