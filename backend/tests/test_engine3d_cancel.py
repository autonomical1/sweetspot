import subprocess
import sys

from backend.app import engine3d


def test_cancel_kills_the_registered_run_and_reports_it():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    engine3d._ACTIVE["r_test"] = process
    assert engine3d.cancel("r_test") is True
    assert process.wait(timeout=10) != 0
    assert engine3d.cancel("r_test") is False
