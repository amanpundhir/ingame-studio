#!/usr/bin/env python
"""InGame Studio - Master Unified Test Runner & Verification Suite.

Executes all 5 test tiers across the stack:
  Tier 1: Telemetry Generator & Kinematics Bounds
  Tier 2: JSONSchema Draft-07 Data Contracts
  Tier 3: Tactical Math, PDR, CCI, and Spatial Metrics
  Tier 4: 4-Agent Causal Reasoning, Verifier Grounding, and Persona Engine
  Tier 5: FastAPI Streaming Server, WebSockets, and Frontend Build Bundle
"""

import os
import sys
import time
import subprocess
import os


def run_test_suite() -> int:
    print("=" * 80)
    print("   INGAME STUDIO - MASTER AUTOMATED TEST SUITE & VICTORY AUDIT   ")
    print("=" * 80)
    start_time = time.time()

    # Locate python in .venv
    venv_python = os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        probe = subprocess.run([venv_python, "-c", "import sys"], capture_output=True, text=True)
        if probe.returncode != 0:
            print("Workspace virtualenv launcher is stale; using the active Python runtime.")
            venv_python = sys.executable
    else:
        venv_python = sys.executable

    cmd = [venv_python, "-m", "pytest", "-v", "--durations=5"]
    env = os.environ.copy()
    # Some managed desktop runtimes provide pytest in the workspace venv's
    # site-packages while its launcher points to a Python install that moved.
    site_packages = os.path.join(os.path.dirname(__file__), ".venv", "Lib", "site-packages")
    if os.path.isdir(site_packages):
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = site_packages + (os.pathsep + existing_pythonpath if existing_pythonpath else "")

    print(f"\n[1/2] Executing Full Workspace Pytest Suite...")
    print(f"Command: {' '.join(cmd)}\n")

    res = subprocess.run(cmd, capture_output=False, env=env)
    duration = time.time() - start_time

    print("\n" + "=" * 80)
    if res.returncode == 0:
        print(f" [PASS] 100% OF AUTOMATED TESTS PASSED CLEANLY IN {duration:.2f}s")
        print("=" * 80)
        return 0
    else:
        print(f" [FAIL] TEST FAILURES ENCOUNTERED (Exit Code: {res.returncode})")
        print("=" * 80)
        return res.returncode


if __name__ == "__main__":
    sys.exit(run_test_suite())
