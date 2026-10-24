import importlib
import os
import pytest


def _module(name, label):
    try:
        return importlib.import_module(name)
    except ImportError:
        pytest.skip(f"{label} implementation is not importable")


@pytest.fixture(params=["stub", "real"])
def engine_impl(request):
    if request.param == "stub":
        return importlib.import_module("backend.app.stubs.engine_stub")
    return _module("speakerplacer", "real engine")


@pytest.fixture(params=["stub", pytest.param("real", marks=pytest.mark.live)])
def products_impl(request):
    if request.param == "real":
        if not os.getenv("SERPAPI_KEY"):
            pytest.skip("real products contract requires SERPAPI_KEY")
        return _module("products", "real products")
    return importlib.import_module("backend.app.stubs.products_stub")


@pytest.fixture
def materials_impl():
    return _module("backend.app.materials", "materials")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: tests that may use an external service")
