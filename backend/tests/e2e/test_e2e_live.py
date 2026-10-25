from __future__ import annotations

import os

import pytest


@pytest.mark.live
def test_live_e2e():
    base_url = os.getenv("E2E_BASE_URL")
    if not base_url:
        pytest.skip("E2E_BASE_URL is not set")
    from tools.e2e import main

    assert main([base_url]) == 0
