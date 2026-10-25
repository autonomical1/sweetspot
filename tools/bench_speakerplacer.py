"""Time the golden rooms with 1, 2 and 4 workers: python tools/bench_speakerplacer.py [workers ...]"""
import os
import subprocess
import sys

counts = sys.argv[1:] or ["1", "2", "4"]
for count in counts:
    env = {**os.environ, "SPEAKERPLACER_WORKERS": count, "PYTHONPATH": "."}
    print(f"--- SPEAKERPLACER_WORKERS={count}")
    subprocess.run([sys.executable, "tools/golden_speakerplacer.py", "check"], env=env, check=False)
