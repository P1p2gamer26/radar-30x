import subprocess, sys


def test_redes_demo():
    assert subprocess.run([sys.executable, "-m", "radar.redes"]).returncode == 0
