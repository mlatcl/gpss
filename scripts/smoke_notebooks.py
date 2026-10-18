#!/usr/bin/env python3
"""Execute GPSS lecture notebooks end-to-end for smoke testing.

CI-oriented defaults:
  - matplotlib Agg backend
  - mock stdin (pods license, catapult distance, …)
  - short-circuit ipywidgets.interact / notutils.display_plots (avoid hangs)
  - cap GPy / DeepGP optimize iterations
  - blank incomplete exercise cells that are not valid Python

Usage (from repo root)::

    python scripts/smoke_notebooks.py
    python scripts/smoke_notebooks.py --only 01 02
    python scripts/smoke_notebooks.py --notebooks-dir _notebooks --results-dir _notebooks/test-results
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
import time
import traceback
from copy import deepcopy
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

# Injected as the first code cell of every notebook under test.
PRELUDE = r"""
import builtins
import numpy as np

if not hasattr(np, "NaN"):
    np.NaN = np.nan


def _mock_input(prompt=""):
    p = str(prompt).lower()
    if "distance" in p:
        print(f"[mock input] {prompt!r} -> 50.0")
        return "50.0"
    if (
        (not prompt)
        or ("yes" in p)
        or ("proceed" in p)
        or ("continue" in p)
        or ("[y/n]" in p)
        or ("[yes/no]" in p)
    ):
        print(f"[mock input] {prompt!r} -> y")
        return "y"
    print(f"[mock input] {prompt!r} -> 1.0")
    return "1.0"


builtins.input = _mock_input
try:
    ip = get_ipython()
    if ip is not None and getattr(ip, "kernel", None) is not None:
        ip.kernel._allow_stdin = True
        ip.kernel.raw_input = _mock_input
except Exception as e:
    print("stdin patch skipped", e)

import matplotlib

matplotlib.use("Agg")

# Lecture notebooks write SVGs under these relative dirs (cwd = notebooks dir).
from pathlib import Path as _Path

for _d in (
    "./datasets",
    "./deepgp",
    "./deepnn",
    "./dimred",
    "./gp",
    "./gplvm",
    "./kern",
    "./ml",
    "./simulation",
    "./uq",
):
    _Path(_d).mkdir(parents=True, exist_ok=True)


# Avoid ipywidgets.interact deadlocks under nbclient (lecture 02).
def _once_interact(func, **kwargs):
    call = {}
    for k, v in kwargs.items():
        if hasattr(v, "value"):
            call[k] = v.value
        elif (
            isinstance(v, tuple)
            and len(v) >= 2
            and all(isinstance(x, (int, float)) for x in v[:3] if not isinstance(x, bool))
        ):
            call[k] = v[0]
        else:
            call[k] = v
    try:
        return func(**call)
    except Exception as e:
        print("[smoke] interact once failed:", e)


try:
    import ipywidgets

    ipywidgets.interact = _once_interact
except Exception as e:
    print("ipywidgets patch skipped", e)

try:
    import notutils

    notutils.display_plots = lambda *a, **k: print(
        "[smoke] skip display_plots", a[:1] if a else ""
    )
    if hasattr(notutils, "display_prediction"):

        def _skip_pred(*a, **k):
            print("[smoke] skip display_prediction")

        notutils.display_prediction = _skip_pred
except Exception as e:
    print("notutils patch skipped", e)


def _cap_optimize(cls, method_name="optimize", max_iters=40):
    if not hasattr(cls, method_name):
        return
    orig = getattr(cls, method_name)

    def wrapped(self, *args, **kwargs):
        if "max_iters" in kwargs and kwargs["max_iters"] is not None:
            kwargs["max_iters"] = min(int(kwargs["max_iters"]), max_iters)
        else:
            kwargs["max_iters"] = max_iters
        if "messages" in kwargs:
            kwargs["messages"] = False
        if "max_f_eval" in kwargs and kwargs["max_f_eval"] is not None:
            kwargs["max_f_eval"] = min(int(kwargs["max_f_eval"]), max_iters)
        return orig(self, *args, **kwargs)

    setattr(cls, method_name, wrapped)


try:
    import GPy

    _cap_optimize(GPy.core.gp.GP, "optimize", 40)
except Exception as e:
    print("GPy patch skipped", e)

try:
    import deepgp

    if hasattr(deepgp, "DeepGP"):
        _cap_optimize(deepgp.DeepGP, "optimize", 25)
        if hasattr(deepgp.DeepGP, "staged_optimize"):
            orig = deepgp.DeepGP.staged_optimize

            def staged(self, *args, **kwargs):
                kwargs["messages"] = False
                if "iters" in kwargs:
                    it = kwargs["iters"]
                    if isinstance(it, (list, tuple)):
                        kwargs["iters"] = tuple(min(int(x), 15) for x in it)
                return orig(self, *args, **kwargs)

            deepgp.DeepGP.staged_optimize = staged
except Exception as e:
    print("deepgp patch skipped", e)
"""


def blank_incomplete_exercises(nb: nbformat.NotebookNode) -> None:
    for cell in nb.cells:
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source", "")
        if isinstance(src, list):
            src = "".join(src)
        if "Write code for you answer" not in src and "Write your answer to Exercise" not in src:
            continue
        try:
            ast.parse(src)
        except SyntaxError:
            cell["source"] = "# skipped incomplete exercise cell for smoke test\npass\n"


def prepare(nb: nbformat.NotebookNode) -> nbformat.NotebookNode:
    nb = deepcopy(nb)
    blank_incomplete_exercises(nb)
    nb.cells.insert(0, nbformat.v4.new_code_cell(PRELUDE))
    return nb


def list_notebooks(nb_dir: Path, only: list[str] | None) -> list[str]:
    names = sorted(p.name for p in nb_dir.glob("[0-9][0-9]-*.ipynb"))
    if not only:
        return names
    selected = []
    for token in only:
        token = token.strip()
        matches = [n for n in names if n.startswith(token) or n == token]
        if not matches:
            raise SystemExit(f"No notebook matches --only {token!r} under {nb_dir}")
        for m in matches:
            if m not in selected:
                selected.append(m)
    return selected


def run_one(
    name: str,
    nb_dir: Path,
    out_dir: Path,
    default_timeout: int,
    lecture02_timeout: int,
) -> dict:
    path = nb_dir / name
    print(f"\n======== {name} ========", flush=True)
    t0 = time.time()
    try:
        nb = nbformat.read(path, as_version=4)
        nb = prepare(nb)
        timeout = lecture02_timeout if name.startswith("02-") else default_timeout
        client = NotebookClient(
            nb,
            timeout=timeout,
            kernel_name="python3",
            resources={"metadata": {"path": str(nb_dir)}},
            allow_errors=False,
            allow_stdin=True,
        )
        client.execute()
        elapsed = time.time() - t0
        print(f"OK ({elapsed:.1f}s)", flush=True)
        (out_dir / f"{name}.ok").write_text(f"OK {elapsed:.1f}s\n")
        fail = out_dir / f"{name}.fail"
        if fail.exists():
            fail.unlink()
        return {"name": name, "status": "OK", "elapsed": elapsed, "error": ""}
    except CellExecutionError as e:
        elapsed = time.time() - t0
        msg = str(e)
        print(f"FAIL ({elapsed:.1f}s)\n{msg[:4000]}", flush=True)
        (out_dir / f"{name}.fail").write_text(msg)
        return {"name": name, "status": "FAIL", "elapsed": elapsed, "error": msg}
    except Exception:
        elapsed = time.time() - t0
        msg = traceback.format_exc()
        print(f"ERROR ({elapsed:.1f}s)\n{msg[:4000]}", flush=True)
        (out_dir / f"{name}.fail").write_text(msg)
        return {"name": name, "status": "ERROR", "elapsed": elapsed, "error": msg}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--notebooks-dir",
        type=Path,
        default=Path("_notebooks"),
        help="Directory containing NN-*.ipynb lecture notebooks",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("_notebooks/test-results"),
        help="Where to write .ok/.fail markers and summary JSON",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        default=None,
        help="Restrict to notebooks whose names start with these prefixes (e.g. 01 13)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Per-notebook cell execution timeout in seconds (default 900)",
    )
    parser.add_argument(
        "--timeout-02",
        type=int,
        default=600,
        help="Timeout for lecture 02 (widget-heavy; default 600 with smoke patches)",
    )
    parser.add_argument(
        "--summary-name",
        default="summary.json",
        help="Summary JSON filename under --results-dir",
    )
    args = parser.parse_args(argv)

    repo_root = Path.cwd()
    nb_dir = (repo_root / args.notebooks_dir).resolve()
    out_dir = (repo_root / args.results_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    mpl_dir = out_dir / "mpl"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("JUPYTER_PLATFORM_DIRS", "1")
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))

    if not nb_dir.is_dir():
        print(f"Notebooks directory not found: {nb_dir}", file=sys.stderr)
        return 2

    order = list_notebooks(nb_dir, args.only)
    print("Notebooks:", order, flush=True)

    results = []
    for name in order:
        result = run_one(name, nb_dir, out_dir, args.timeout, args.timeout_02)
        results.append(result)
        (out_dir / args.summary_name).write_text(json.dumps(results, indent=2) + "\n")

    print("\n==== SUMMARY ====")
    for r in results:
        print(f"{r['status']:5} {r['elapsed']:7.1f}s  {r['name']}")
    n_ok = sum(r["status"] == "OK" for r in results)
    print(f"{n_ok}/{len(results)} passed")
    return 0 if n_ok == len(results) and results else 1


if __name__ == "__main__":
    raise SystemExit(main())
