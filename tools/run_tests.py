"""Run every test without pytest:  python tools/run_tests.py

With pytest installed, `python -m pytest` runs the same tests (they are plain
functions with `assert`). This runner just lets you check quickly anywhere.
"""
import importlib
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

passed, failed = 0, []
for path in sorted((ROOT / "tests").glob("test_*.py")):
    module = importlib.import_module(f"tests.{path.stem}")
    for name in sorted(n for n in dir(module) if n.startswith("test_")):
        start = time.time()
        try:
            getattr(module, name)()
            passed += 1
            print(f"PASS  {path.stem}::{name}  ({time.time() - start:.1f}s)")
        except Exception:
            failed.append(f"{path.stem}::{name}")
            print(f"FAIL  {path.stem}::{name}")
            traceback.print_exc()
print(f"\n{passed} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
