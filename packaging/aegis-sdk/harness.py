#!/usr/bin/env python3
"""The SDK's own harness — one command for everything a standalone package needs.

    python packaging/aegis-sdk/harness.py all          # everything below
    python packaging/aegis-sdk/harness.py tests        # the SDK's test set
    python packaging/aegis-sdk/harness.py typecheck    # per-file mypy ratchet
    python packaging/aegis-sdk/harness.py build        # wheel, + core-leak check
    python packaging/aegis-sdk/harness.py lint         # ruff over the SDK only
    python packaging/aegis-sdk/harness.py list-tests   # what `tests` would run

WHY IT LIVES BESIDE THE PACKAGING
---------------------------------
It TRAVELS. This file is carried into the standalone SDK repository as-is, and
that repository's CI is one call to `all`. A harness living in a maintenance
script directory would have to be rewritten at split time, which is the point at
which nobody has budget to rewrite anything. Every path it needs is resolved
from its own location, so the same file works in both trees.

It also deliberately does not touch the surrounding project's own type gate.
That gate has a different target and decides a different merge; widening a
shared gate is a change with blast radius, and the SDK needs a ratchet it OWNS
anyway. The two are independent by design.

THE TEST SET IS DERIVED, NEVER HAND-LISTED
------------------------------------------
`list-tests` walks `tests/` with `ast` and selects every file that IMPORTS
`aegis_sdk`. A hand-written list is the defect: it drifts the moment someone
adds a test, and then reports a clean sweep the gate will not agree with. Note
this is narrower than a grep for the string `aegis_sdk`, which also matches
static sweeps that merely NAME the package in a docstring or a pattern -- those
are checks on the surrounding project, not SDK tests.

`list-tests --travelling` asks the SEPARATE question of which of those files may
be published, which is a conjunction and not a filter. See the comment above
`travelling_test_files()`: three of the selected files reach private modules,
and reading the run-here selector as an export boundary would publish them.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
SDK_SRC = REPO_ROOT / "src" / "aegis_sdk"
TESTS_ROOT = REPO_ROOT / "tests"
BASELINE = HERE / "mypy_baseline_by_file.json"

# NOTE for anyone reading this file's history. It carried an `EXCLUDE_KAIZEN`
# flag filtering an orchestration subpackage and its tests out of every step
# while that package's disposition was under review. The review concluded on
# 2026-09-07 and the package left the SDK. The flag is removed rather than set
# to False, because there is no longer a tree for it to exclude and a dead
# filter reads as an open question.
#
# Read the OLD numbers in CI.md accordingly: they were measured with that filter
# ON, so they never covered the package and did not fall when it left.


# --------------------------------------------------------------- test selection


def _top_level_imports(path: Path) -> set[str] | None:
    """Absolute imported module names, or None if the file will not parse."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return None
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            mods.add(node.module)
    return mods


def _reaches(mods: set[str], pkg: str) -> bool:
    return any(m == pkg or m.startswith(pkg + ".") for m in mods)


def sdk_test_files() -> list[Path]:
    """Every test file that IMPORTS aegis_sdk. AST, not grep."""
    out: list[Path] = []
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        if "__pycache__" in path.parts:
            continue
        mods = _top_level_imports(path)
        if mods is not None and _reaches(mods, "aegis_sdk"):
            out.append(path)
    return out


# THE SELECTION PREDICATE ABOVE IS NOT A BOUNDARY, AND MUST NOT BE USED AS ONE.
#
# "imports aegis_sdk" answers WHAT TO RUN HERE. It does not answer WHAT MAY
# LEAVE, and the two are different questions with different failure modes. A
# test may import the client AND the platform: it is a perfectly good test in
# this repository and it is a leak in a partner-facing one, because carrying it
# carries private module paths in its own import statements.
#
# Measured 2026-09-08 over the 89 files `sdk_test_files()` selects: THREE import
# the private package directly. Reading the selector as a boundary would have
# published all three. So the export predicate is the CONJUNCTION below, and it
# is stated as a positive requirement rather than as a filter — a filter reads
# as removable, and this one is load-bearing.
#
# It is deliberately keyed on `tests.` as well as the private package. A helper
# under `tests/` is umbrella test-support that no standalone tree contains, so a
# file importing one cannot even collect there; catching it here turns a
# confusing collection error in someone else's repository into a fact stated in
# this one.
PRIVATE_PKG = "aegis"
SUPPORT_PKG = "tests"


def travelling_test_files() -> tuple[list[Path], list[tuple[Path, list[str]]]]:
    """(may leave, must not leave) over the SDK test set.

    A file may leave only when every one of these holds:
      * it imports `aegis_sdk`                    (it is an SDK test at all)
      * it is gate tier                           (no PG/Redis/browser needed)
      * it imports NOTHING under `aegis`          (no private source)
      * it imports NOTHING under `tests`          (no umbrella test-support)

    The second return value is every EXCLUDED file paired with the imports that
    excluded it, so the boundary is reported rather than silently applied.
    """
    keep: list[Path] = []
    held: list[tuple[Path, list[str]]] = []
    for path in sdk_test_files():
        if _tier_of(path) != "gate":
            held.append((path, ["<infra tier>"]))
            continue
        mods = _top_level_imports(path) or set()
        blocking = sorted(
            m for m in mods
            if m == PRIVATE_PKG or m.startswith(PRIVATE_PKG + ".")
            or m == SUPPORT_PKG or m.startswith(SUPPORT_PKG + ".")
        )
        (held.append((path, blocking)) if blocking else keep.append(path))
    return keep, held


# Tiering mirrors the boundary the surrounding project already documents, and is
# not a way to drop a failing scope: the infra roots below need Postgres, Redis
# or a browser, so they run separately when that infrastructure is available.
#
# ⚠ THE INFRA TIER IS RED and has been since before this harness existed: two
# tests exercising the `nexus` subpackage fail deterministically (they reproduce
# in 3s in isolation, so this is not load contention). `tests --tier infra` runs
# them and reports the red. The tier split makes that state VISIBLE; it does not
# make it green. Those files are ALSO outside `travelling_test_files()`, so the
# red is not exported along with the harness.
INFRA_TIER_ROOTS = ("tests/integration", "tests/e2e", "tests/performance")


def _tier_of(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).as_posix()
    return "infra" if rel.startswith(INFRA_TIER_ROOTS) else "gate"


def _select(tier: str) -> list[Path]:
    files = sdk_test_files()
    if tier == "all":
        return files
    return [f for f in files if _tier_of(f) == tier]


def cmd_list_tests(args: argparse.Namespace) -> int:
    if args.travelling:
        keep, held = travelling_test_files()
        for f in keep:
            print(f.relative_to(REPO_ROOT).as_posix())
        if args.porcelain:
            return 0
        blocked = [(f, why) for f, why in held if why != ["<infra tier>"]]
        print(
            f"\n{len(keep)} file(s) may leave  |  {len(held)} held back "
            f"({len(held) - len(blocked)} infra tier, {len(blocked)} reach "
            f"private or umbrella-only modules)",
            file=sys.stderr,
        )
        for f, why in blocked:
            print(f"  HELD {f.relative_to(REPO_ROOT).as_posix()}  <- {', '.join(why)}",
                  file=sys.stderr)
        return 0

    files = sdk_test_files()
    gate = [f for f in files if _tier_of(f) == "gate"]
    infra = [f for f in files if _tier_of(f) == "infra"]
    for f in _select(args.tier):
        print(f.relative_to(REPO_ROOT).as_posix())
    print(
        f"\n{len(files)} test file(s) import aegis_sdk"
        f"  |  gate tier: {len(gate)}   infra tier: {len(infra)}",
        file=sys.stderr,
    )
    return 0


def cmd_tests(args: argparse.Namespace) -> int:
    files = _select(args.tier)
    skipped = len(sdk_test_files()) - len(files)
    if skipped:
        print(
            f"note: {skipped} file(s) in the other tier are NOT run here "
            f"(tier={args.tier}); use --tier all to include them.",
            file=sys.stderr,
        )
    if not files:
        print(
            "ERROR: zero SDK test files selected. That is a broken selector, not "
            "a clean tree -- a sweep that selects nothing cannot fail.",
            file=sys.stderr,
        )
        return 1
    # `-p no:timeout` mirrors this repository's own gate; the schema plugin then
    # re-registers the retained ini keys so disabling enforcement does not
    # produce warning noise. That plugin is umbrella test-support and does NOT
    # travel, so it is added ONLY when it is actually importable. Naming it
    # unconditionally would make the standalone gate fail at start-up with
    # `no module named tests.pytest_timeout_schema` — a fatal error about a
    # cosmetic concern, in the one tree where nobody can fix it.
    cmd = [
        sys.executable, "-m", "pytest",
        *[str(f) for f in files],
        "-q", "-p", "no:timeout",
    ]
    if (REPO_ROOT / "tests" / "pytest_timeout_schema.py").is_file():
        cmd += ["-p", "tests.pytest_timeout_schema"]
    cmd += ["-n", str(args.jobs), "--dist", "loadfile"]
    print(f"$ {' '.join(cmd[:6])} ... ({len(files)} files)", file=sys.stderr)
    return subprocess.run(cmd, cwd=REPO_ROOT, check=False).returncode


# ------------------------------------------------------------------- typecheck


def _mypy_counts() -> dict[str, int]:
    """{relative path: error count} from a real mypy run over the SDK."""
    targets = [str(SDK_SRC.relative_to(REPO_ROOT))]
    # MYPYPATH is set here rather than as `mypy_path` in the config, because that
    # setting resolves against the directory holding the CONFIG FILE — which is
    # this packaging directory in one tree and the repository root in the other,
    # so one written value cannot be right in both. Computed from the harness's
    # own location it is right in both by construction. It matters: dropping it
    # entirely put TEN files over budget, resolving `aegis_sdk` through whatever
    # the interpreter had installed rather than through the tree being checked.
    env = {**os.environ, "MYPYPATH": str(SDK_SRC.parent)}
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "mypy", "--config-file", str(_sdk_config()), *targets],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False, env=env,
    )
    if proc.returncode not in (0, 1):
        print(f"mypy exited {proc.returncode} -- not a verdict:\n{proc.stderr}", file=sys.stderr)
        raise SystemExit(2)
    counts: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        if ": error:" not in line:
            continue
        path = line.split(":", 1)[0]
        if not path.startswith("src/aegis_sdk/"):
            continue  # mypy follows imports; only OUR tree is ratcheted
        counts[path] = counts.get(path, 0) + 1
    return counts


def cmd_typecheck(args: argparse.Namespace) -> int:
    """Per-file ratchet: a file may improve, never regress.

    A single global total would let one file improve while another rots, which
    is what a per-file map prevents. Deliberately the same shape as the type
    ratchet the surrounding project already trusts, but with its own target and
    its own baseline so the two gates never constrain each other.
    """
    if not list(SDK_SRC.rglob("*.py")):
        print(f"ERROR: {SDK_SRC} holds zero .py files -- a clean run here would "
              "be vacuous. Fix the path.", file=sys.stderr)
        return 1

    counts = _mypy_counts()
    if args.update_baseline:
        BASELINE.write_text(json.dumps(dict(sorted(counts.items())), indent=2) + "\n")
        print(f"baseline written: {len(counts)} file(s), {sum(counts.values())} error(s)")
        return 0

    if not BASELINE.is_file():
        print(f"ERROR: no baseline at {BASELINE}. Run `typecheck --update-baseline` "
              "once, review the diff, and commit it.", file=sys.stderr)
        return 1
    baseline: dict[str, int] = json.loads(BASELINE.read_text())

    over = [(p, c, baseline.get(p, 0)) for p, c in sorted(counts.items()) if c > baseline.get(p, 0)]
    if over:
        print("TYPE REGRESSION -- these files exceed their budget:", file=sys.stderr)
        for p, c, b in over:
            print(f"  {p}: {c} errors, budget {b}", file=sys.stderr)
        print("\nFix the new errors. Raising a budget is BLOCKED: the ratchet only "
              "goes down. Weakening the check that caught something is not a fix "
              "for the thing it caught.", file=sys.stderr)
        return 1

    improved = [(p, baseline[p], counts.get(p, 0)) for p in baseline if counts.get(p, 0) < baseline[p]]
    total, budget = sum(counts.values()), sum(baseline.values())
    print(f"type gate OK: {total} error(s) against a {budget} budget across "
          f"{len(counts)} file(s)")
    if improved:
        print(f"{len(improved)} file(s) improved -- run `--update-baseline` to bank it:")
        for p, b, c in improved[:10]:
            print(f"  {p}: {b} -> {c}")
    return 0


# ----------------------------------------------------------------------- build


def _sdk_config() -> Path:
    """The descriptor carrying the SDK's OWN ruff/mypy/pytest settings.

    Passed EXPLICITLY to both tools rather than left to discovery, and that is
    the whole point of it. Discovery resolves against the working directory, so
    the same `ruff check src/aegis_sdk` picks up this project's root settings
    here and each tool's DEFAULTS in a standalone tree — a gate that answers
    differently in the two places is worse than no gate, because only one of the
    two answers is ever looked at.
    """
    return _build_root() / "pyproject.toml"


def _build_root() -> Path:
    """The directory holding the pyproject that builds `aegis_sdk`.

    HERE in this repository, where the descriptor sits beside this file and
    reaches the package through a symlink. REPO_ROOT in a standalone tree, where
    the descriptor is at the root and `packages = ["src/aegis_sdk"]` is a plain
    relative path. Resolved rather than assumed: `cwd=HERE` was hardcoded, which
    is the one place this harness did NOT in fact "compute every path from its
    own location", and it fails with `no pyproject.toml` after a split — the
    step most likely to be run first and least likely to be suspected.
    """
    for candidate in (HERE, REPO_ROOT):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return HERE


def cmd_build(_args: argparse.Namespace) -> int:
    root = _build_root()
    out = root / "dist"
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(out)],
        cwd=root, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        print(proc.stdout + proc.stderr, file=sys.stderr)
        return proc.returncode
    wheels = sorted(out.glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        print("ERROR: build reported success and produced no wheel.", file=sys.stderr)
        return 1
    wheel = wheels[-1]
    names = zipfile.ZipFile(wheel).namelist()
    core = [n for n in names if n.startswith("aegis/") or "/aegis/" in n]
    py = [n for n in names if n.endswith(".py")]
    if core:
        print(f"CORE CODE IN THE SDK WHEEL ({len(core)} entries): {core[:10]}", file=sys.stderr)
        return 1
    if len(py) < 50:
        print(f"ERROR: only {len(py)} .py files in the wheel. A nearly-empty wheel "
              "trivially satisfies 'no core code' and proves nothing.", file=sys.stderr)
        return 1
    if not any(n.endswith("aegis_sdk/py.typed") for n in names):
        print("ERROR: py.typed missing -- consumers' type checkers will treat the "
              "whole SDK as Any.", file=sys.stderr)
        return 1
    print(f"wheel OK: {wheel.name}  {wheel.stat().st_size // 1024}K  "
          f"{len(py)} .py  py.typed present  0 core entries")
    return 0


# --------------------------------------------------------------- install check


def cmd_install_check(args: argparse.Namespace) -> int:
    """Install the built wheel into a CLEAN venv and prove core is unreachable.

    This is the check the whole exercise is FOR. Every other step reasons about
    the archive; this one reasons about what a person actually ends up with.
    "No `aegis/` paths in the zip" and "`import aegis` fails after installing"
    are different claims, and only the second is the requirement.

    Needs the network (it resolves httpx/pydantic from an index), so it is NOT
    part of `all` and NOT part of the gate. Run it before handing the wheel to
    anyone outside the team.
    """
    import shutil
    import tempfile
    import venv

    wheels = sorted((_build_root() / "dist").glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if not wheels:
        print("no wheel in dist/ -- run `build` first", file=sys.stderr)
        return 1
    wheel = wheels[-1]

    # `uv` first. stdlib `venv` runs `ensurepip`, which SIGABRTs on the
    # uv-managed CPython this repo standardises on -- measured, exit 1 with
    # `<Signals.SIGABRT: 6>`. The fallback stays for a plain system Python.
    uv = shutil.which("uv")

    with tempfile.TemporaryDirectory() as td:
        env = Path(td) / "venv"
        bindir = "Scripts" if os.name == "nt" else "bin"
        if uv:
            mk = subprocess.run(  # noqa: S603
                [uv, "venv", str(env)],
                capture_output=True, text=True, timeout=300,
                env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(env)}, check=False,
            )
            if mk.returncode != 0:
                print(f"uv venv failed:\n{mk.stderr}", file=sys.stderr)
                return 1
        else:
            venv.EnvBuilder(with_pip=True, clear=True).create(env)
        py = env / bindir / "python"

        spec = f"{wheel}[kaizen]" if args.with_kaizen else str(wheel)
        cmd = (
            [uv, "pip", "install", "--python", str(py), spec]
            if uv
            else [str(py), "-m", "pip", "install", "--quiet", spec]
        )
        proc = subprocess.run(  # noqa: S603
            cmd, capture_output=True, text=True, timeout=900,
            env={**os.environ, "UV_PROJECT_ENVIRONMENT": str(env)}, check=False,
        )
        if proc.returncode != 0:
            print(f"install failed:\n{proc.stdout}\n{proc.stderr}", file=sys.stderr)
            return 1

        probe = (
            "import importlib.util as u, json, sys;"
            "core = u.find_spec('aegis') is not None;"
            "sdk = u.find_spec('aegis_sdk') is not None;"
            "imported = None;"
            "\ntry:\n import aegis_sdk; imported = aegis_sdk.__version__"
            "\nexcept Exception as e: imported = f'{type(e).__name__}: {e}'"
            "\nprint(json.dumps({'core': core, 'sdk': sdk, 'imported': imported}))"
        )
        out = subprocess.run(  # noqa: S603
            [str(py), "-c", probe], capture_output=True, text=True, timeout=300, check=False
        )
        try:
            res = json.loads(out.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            print(f"probe produced no verdict -- UNDETERMINED, not a pass:\n"
                  f"{out.stdout}\n{out.stderr}", file=sys.stderr)
            return 2

        if res["core"]:
            print("FAIL: `aegis` (core) is IMPORTABLE after installing the SDK "
                  "wheel. This is the exact thing the SDK exists to prevent.",
                  file=sys.stderr)
            return 1
        if not res["sdk"]:
            print("FAIL: `aegis_sdk` is not importable -- the wheel installed "
                  "nothing useful.", file=sys.stderr)
            return 1
        print(f"clean-venv install OK: core unreachable, aegis_sdk present, "
              f"`import aegis_sdk` -> {res['imported']}")
        if not args.with_kaizen and "Error" in str(res["imported"]):
            print("  (the base install cannot import yet -- see the `kaizen` "
                  "note in pyproject.toml; retry with --with-kaizen)")
        return 0


# ------------------------------------------------------------------------ lint


def cmd_lint(_args: argparse.Namespace) -> int:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "ruff", "check", "--config", str(_sdk_config()),
         str(SDK_SRC.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT, check=False,
    ).returncode


# ------------------------------------------------------------------------- all


def cmd_all(args: argparse.Namespace) -> int:
    steps = [("lint", cmd_lint), ("typecheck", cmd_typecheck),
             ("build", cmd_build), ("tests", cmd_tests)]
    failed: list[str] = []
    for name, fn in steps:
        print(f"\n{'=' * 68}\n== {name}\n{'=' * 68}", flush=True)
        if fn(args) != 0:
            failed.append(name)
            if not args.keep_going:
                break
    print(f"\n{'=' * 68}")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print("SDK harness: all steps passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-j", "--jobs", default=os.environ.get("SDK_TEST_JOBS", "8"),
                    help="pytest-xdist workers (default 8: the connection-pool "
                         "bound this repo measured, not the core count)")
    ap.add_argument("--update-baseline", action="store_true",
                    help="typecheck: bank current counts (ratchets DOWN only)")
    ap.add_argument("--keep-going", action="store_true", help="all: run every step")
    ap.add_argument("--tier", choices=["gate", "infra", "all"], default="gate",
                    help="gate (default): the trees the canonical merge gate runs. "
                         "infra: integration/e2e/performance, which need PG+Redis. "
                         "all: both.")
    ap.add_argument("--with-kaizen", action="store_true",
                    help="install-check: install the [kaizen] extra too")
    ap.add_argument("--travelling", action="store_true",
                    help="list-tests: the files that may be PUBLISHED (a stricter "
                         "question than which files run here); held-back files and "
                         "the imports that held them are reported on stderr")
    ap.add_argument("--porcelain", action="store_true",
                    help="list-tests --travelling: paths only, no summary — for a "
                         "consumer that parses this rather than reads it")
    ap.add_argument("command", choices=["all", "tests", "typecheck", "build", "lint",
                                        "list-tests", "install-check"])
    args = ap.parse_args()
    return {
        "all": cmd_all, "tests": cmd_tests, "typecheck": cmd_typecheck,
        "build": cmd_build, "lint": cmd_lint, "list-tests": cmd_list_tests,
        "install-check": cmd_install_check,
    }[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
