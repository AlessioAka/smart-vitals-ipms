"""Run the notebooks' code cells in plain Python and store the outputs inside them.

    python tools/run_notebooks.py

A stand-in for `jupyter nbconvert --execute`, for machines without Jupyter.
In VS Code you can simply press "Run All" instead. Stops at the first error.
"""
import ast
import base64
import contextlib
import io
import json
import sys
import traceback
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def run_cell(source: str, ns: dict) -> list:
    outputs = []
    buf = io.StringIO()
    tree = ast.parse(source)
    last = tree.body.pop() if tree.body and isinstance(tree.body[-1], ast.Expr) else None
    with contextlib.redirect_stdout(buf):
        exec(compile(tree, "<cell>", "exec"), ns)
        value = eval(compile(ast.Expression(last.value), "<cell>", "eval"), ns) if last else None
    if buf.getvalue():
        outputs.append({"output_type": "stream", "name": "stdout", "text": buf.getvalue().splitlines(True)})
    for num in plt.get_fignums():
        img = io.BytesIO()
        plt.figure(num).savefig(img, format="png", dpi=100, bbox_inches="tight")
        outputs.append({"output_type": "display_data", "metadata": {},
                        "data": {"image/png": base64.b64encode(img.getvalue()).decode(), "text/plain": ["<Figure>"]}})
    plt.close("all")
    if value is not None:
        data = {"text/plain": repr(value).splitlines(True)}
        if hasattr(value, "to_html"):
            data["text/html"] = value.to_html().splitlines(True)
            data["text/plain"] = str(value).splitlines(True)
        outputs.append({"output_type": "execute_result", "metadata": {}, "execution_count": None, "data": data})
    return outputs


for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
    nb = json.loads(path.read_text(encoding="utf-8"))
    ns = {"__name__": "__main__"}
    count = 0
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        count += 1
        try:
            cell["outputs"] = run_cell("".join(cell["source"]), ns)
            cell["execution_count"] = count
        except Exception:
            print(f"FAILED in {path.name}, cell {count}")
            traceback.print_exc()
            sys.exit(1)
    path.write_text(json.dumps(nb, indent=1), encoding="utf-8")
    print(f"ran {path.name}: {count} code cells OK")
