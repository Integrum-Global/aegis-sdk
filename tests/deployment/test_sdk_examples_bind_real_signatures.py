"""Every ``client.<module>.<method>(...)`` call in a SHIPPED SDK example must bind
against the method's REAL signature.

WHY THIS EXISTS
---------------
``src/aegis_sdk/examples/`` ships inside the wheel (``pyproject.toml`` declares
``packages = [..., "src/aegis_sdk"]``, and the Dockerfile's ``COPY src/`` is
broader still). It is the first code an external reader runs. Before this guard,
three of the five example files called signatures the SDK does not have -- 11
call-argument errors, every one a guaranteed ``TypeError`` on the first line
that mattered:

    agents.execute(objective=..., wait=True)      # takes `message`; no `wait`
    agents.stream(objective=...)                  # takes `message`
    sessions.stream_messages(from_message_id=...) # takes session_id only
    objectives.create(metadata=...)               # no such field

The mechanism is drift, not carelessness: ``AgentsModule.execute`` was corrected
to match the server contract and its docstring now states outright that the body
key is ``message`` and that "there is no ``wait`` concept" -- while the example
sitting two directories away still passed both. A docstring cannot fail a build.
This can.

WHAT IT CHECKS
--------------
For each call of the form ``client.<attr>.<method>(...)`` (or
``client.<group>.<attr>.<method>(...)``) in an example file, resolve the real
bound method off a live ``AgenticOSClient`` and run
``inspect.Signature.bind_partial`` with the call's keyword names and positional
arity. A ``TypeError`` from ``bind_partial`` is exactly "this call cannot
succeed" -- an unexpected keyword, or too many positionals.

DELIBERATELY AST + ``inspect``, NOT GREP AND NOT MYPY
-----------------------------------------------------
grep cannot tell a keyword argument from a dict key or a prose mention. mypy
*does* catch this class (it is how the original 11 were found), but the mypy
gate is scoped to the server-side platform package, not to ``src/aegis_sdk``,
so this package is not type-checked at the merge gate at all. Until that
changes, nothing in the required job looks at these files.

WHAT A GREEN RUN DOES **NOT** ESTABLISH
---------------------------------------
Stated so this is not over-read:

* It checks that a call BINDS, never that it BEHAVES. A correct signature with a
  wrong value (a bad enum member, an id that does not exist, a field the server
  rejects) passes here and still fails against a live deployment.
* ``**kwargs`` in a target signature makes ``bind_partial`` accept anything, so
  the sweep follows ONE hop further: it reads the ``**kwargs``-forwarding
  pydantic model out of the target's own source and checks the example's keyword
  names against ``model_fields``. This matters more than it sounds --
  ``AgentCreate`` sets no ``extra`` policy, so pydantic's default is ``ignore``
  and a MISSPELLED kwarg is silently DROPPED at runtime rather than raised. The
  binder is the only thing that sees it.
* A target that pre-flights a REQUIRED kwarg (``if not kwargs.get("x"): raise``)
  is checked for that kwarg too. Two examples omitted ``workspace_id`` and would
  have raised ``ValidationError`` on their first create call.
* A ``**kwargs`` target that forwards to no model and pre-flights nothing is
  genuinely uncheckable and is REPORTED by ``test_no_target_is_unverifiable``,
  not silently passed.
* Positional arity is checked; positional TYPES are not.
* Only calls rooted at a name in ``CLIENT_ROOTS`` are resolved. A call through an
  intermediate local (``mod = client.agents; mod.execute(...)``) is invisible to
  this sweep, and is counted and asserted-absent below so the blind spot cannot
  grow silently.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

from aegis_sdk import AgenticOSClient

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "src" / "aegis_sdk" / "examples"

# Names that hold an AgenticOSClient in the example files.
CLIENT_ROOTS = {"client"}


def _example_files() -> list[Path]:
    return sorted(p for p in EXAMPLES_DIR.glob("*.py") if p.name != "__init__.py")


def _attr_chain(node: ast.AST) -> list[str] | None:
    """Return ['client', 'agents', 'execute'] for ``client.agents.execute``."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if not isinstance(cur, ast.Name):
        return None
    parts.append(cur.id)
    return list(reversed(parts))


def _client_calls(path: Path) -> list[tuple[list[str], ast.Call]]:
    """Every ``client.<...>.<method>(...)`` call in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[tuple[list[str], ast.Call]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _attr_chain(node.func)
        if chain and len(chain) >= 3 and chain[0] in CLIENT_ROOTS:
            out.append((chain, node))
    return out


@pytest.fixture(scope="module")
def client() -> Any:
    """A client instance. Constructed, never connected -- no network, no server.

    ``base_url`` has no default by design, so it is supplied explicitly here.
    """
    return AgenticOSClient(base_url="https://example.invalid", api_key="sk_test_notused")


def _resolve(client: Any, chain: list[str]) -> Any:
    obj = client
    for part in chain[1:]:
        obj = getattr(obj, part)
    return obj


# The examples that SHIP today. A ratchet, not a snapshot: adding an example is
# free (the parametrized tests pick it up automatically), removing one requires
# editing this set deliberately.
#
# Pinned by NAME, not by count. A bare count floor was the first version of this
# control and it FAILED ITS OWN MUTATION TEST: hiding three of the five files
# still left 20+ resolvable calls in the other two, so the "directory is
# non-empty" control passed while 60% of the shipped examples had vanished. A
# total cannot detect a deletion when the survivors are large enough.
EXPECTED_EXAMPLES = frozenset(
    {
        "basic_agent_workflow.py",
        "error_handling.py",
        "stand_up_a_vertical.py",
        "streaming_progress.py",
        "trust_chain_management.py",
    }
)


def test_expected_examples_all_present() -> None:
    """Positive control: a moved, renamed, or deleted example must not read as clean."""
    found = {p.name for p in _example_files()}
    missing = EXPECTED_EXAMPLES - found
    assert not missing, (
        f"shipped example(s) gone from {EXAMPLES_DIR}: {sorted(missing)}. "
        "If the removal is deliberate, update EXPECTED_EXAMPLES in the same "
        "change -- do not delete this test."
    )
    calls = sum(len(_client_calls(p)) for p in _example_files())
    assert calls > 20, (
        f"only {calls} client calls resolved across {len(found)} example files. "
        "A sweep that resolves almost nothing cannot fail, so this floor makes a "
        "broken matcher loud instead of green."
    )


@pytest.mark.parametrize("path", _example_files(), ids=lambda p: p.name)
def test_every_client_call_binds(path: Path, client: Any) -> None:
    failures: list[str] = []
    for chain, call in _client_calls(path):
        try:
            target = _resolve(client, chain)
        except AttributeError as exc:
            failures.append(f"{path.name}:{call.lineno}  {'.'.join(chain)} -> {exc}")
            continue
        if not callable(target):
            failures.append(f"{path.name}:{call.lineno}  {'.'.join(chain)} is not callable")
            continue

        kwargs = {kw.arg: None for kw in call.keywords if kw.arg is not None}
        has_starstar = any(kw.arg is None for kw in call.keywords)
        has_star = any(isinstance(a, ast.Starred) for a in call.args)
        if has_starstar or has_star:
            # An unpacked call cannot be bound statically; skip rather than
            # report a false failure.
            continue
        args = [None] * len(call.args)

        try:
            inspect.signature(target).bind_partial(*args, **kwargs)
        except TypeError as exc:
            failures.append(f"{path.name}:{call.lineno}  {'.'.join(chain)}(...) -> {exc}")

    assert not failures, (
        "shipped example calls an API that does not exist -- this is a TypeError "
        "for the first external reader who runs it:\n  " + "\n  ".join(failures)
    )


def _kwargs_contract(target: Any) -> tuple[set[str] | None, set[str]]:
    """For a ``**kwargs`` target, derive (accepted field names, required names).

    Read out of the target's OWN source, never hand-maintained:

    * accepted -- the ``model_fields`` of the pydantic model the body constructs
      with ``**kwargs`` (``AgentCreate(name=..., **kwargs)``). ``None`` means no
      such model was found, i.e. the target is unverifiable.
    * required -- every ``k`` in ``if not kwargs.get("k"): raise ...``, the
      client-side pre-flight pattern the modules use to fail fast instead of
      round-tripping to an opaque 422.
    """
    import importlib

    try:
        src = inspect.getsource(target)
    except (OSError, TypeError):
        return None, set()
    try:
        tree = ast.parse(_dedent(src))
    except SyntaxError:
        return None, set()

    accepted: set[str] | None = None
    required: set[str] = set()

    module = importlib.import_module(target.__module__)
    # The name of the VAR_KEYWORD parameter itself -- matching on any `**x`
    # would also catch `Agent(**response)`, which forwards the RESPONSE, not the
    # caller's kwargs, and would silently substitute the wrong model's fields.
    var_kw = next(
        (
            n
            for n, prm in inspect.signature(target).parameters.items()
            if prm.kind is inspect.Parameter.VAR_KEYWORD
        ),
        None,
    )
    if var_kw is None:
        return None, set()

    for node in ast.walk(tree):
        # AgentCreate(name=name, **kwargs)  ->  accepted = AgentCreate.model_fields
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if any(
                kw.arg is None and isinstance(kw.value, ast.Name) and kw.value.id == var_kw
                for kw in node.keywords
            ):
                model = getattr(module, node.func.id, None)
                fields = getattr(model, "model_fields", None)
                if isinstance(fields, dict):
                    accepted = set(fields)
        # if not kwargs.get("workspace_id"): raise ...
        if isinstance(node, ast.If) and _raises(node):
            for sub in ast.walk(node.test):
                if (
                    isinstance(sub, ast.Call)
                    and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "get"
                    and isinstance(sub.func.value, ast.Name)
                    and sub.func.value.id == var_kw
                    and sub.args
                    and isinstance(sub.args[0], ast.Constant)
                    and isinstance(sub.args[0].value, str)
                ):
                    required.add(sub.args[0].value)
    return accepted, required


def _dedent(src: str) -> str:
    import textwrap

    return textwrap.dedent(src)


def _raises(node: ast.If) -> bool:
    return any(isinstance(n, ast.Raise) for n in ast.walk(node))


@pytest.mark.parametrize("path", _example_files(), ids=lambda p: p.name)
def test_kwargs_targets_accept_what_examples_pass(path: Path, client: Any) -> None:
    """Follow ``**kwargs`` one hop into the model it forwards to."""
    failures: list[str] = []
    for chain, call in _client_calls(path):
        try:
            target = _resolve(client, chain)
        except AttributeError:
            continue
        if not callable(target):
            continue
        params = inspect.signature(target).parameters
        if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
            continue
        if any(kw.arg is None for kw in call.keywords):
            continue  # **unpacked call -- not statically knowable

        named = {kw.arg for kw in call.keywords if kw.arg is not None}
        explicit = {n for n, p in params.items() if p.kind is not inspect.Parameter.VAR_KEYWORD}
        forwarded = named - explicit

        accepted, required = _kwargs_contract(target)
        if accepted is not None:
            unknown = forwarded - accepted
            if unknown:
                failures.append(
                    f"{path.name}:{call.lineno}  {'.'.join(chain)}(...) passes "
                    f"{sorted(unknown)}, which the forwarded model does not "
                    "declare -- pydantic's default `extra` policy DROPS these "
                    "silently at runtime"
                )
        missing = required - named
        if missing:
            failures.append(
                f"{path.name}:{call.lineno}  {'.'.join(chain)}(...) omits "
                f"{sorted(missing)}, which the method pre-flights and RAISES on"
            )

    assert not failures, "shipped example violates a **kwargs contract:\n  " + "\n  ".join(
        failures
    )


def test_no_target_is_unverifiable(client: Any) -> None:
    """A ``**kwargs`` target with no forwarded model and no pre-flight is opaque.

    Such a call is checked by nothing. Surface it rather than let a green run
    imply coverage it does not have. If one legitimately appears, the fix is to
    give the target a typed model -- not to widen this test.
    """
    opaque: set[str] = set()
    for path in _example_files():
        for chain, _call in _client_calls(path):
            try:
                target = _resolve(client, chain)
            except AttributeError:
                continue
            if not callable(target):
                continue
            params = inspect.signature(target).parameters.values()
            if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params):
                continue
            accepted, required = _kwargs_contract(target)
            if accepted is None and not required:
                opaque.add(".".join(chain))
    assert not opaque, (
        "these example targets take **kwargs, forward to no typed model, and "
        f"pre-flight nothing -- nothing verifies their call sites: {sorted(opaque)}"
    )


def test_no_client_module_is_aliased_through_a_local(  # noqa: D103
) -> None:
    """The sweep only follows chains rooted at a client name -- pin that blind spot.

    ``mod = client.agents`` followed by ``mod.execute(...)`` is invisible above.
    None exist today; this fails if one is introduced, so the gap cannot widen
    without a deliberate decision.
    """
    aliased: list[str] = []
    for path in _example_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            chain = _attr_chain(node.value)
            if chain and chain[0] in CLIENT_ROOTS and len(chain) >= 2:
                for tgt in node.targets:
                    if isinstance(tgt, ast.Name):
                        aliased.append(f"{path.name}:{node.lineno}  {tgt.id} = {'.'.join(chain)}")
    assert not aliased, (
        "an example binds a client module to a local name; calls through it are "
        "NOT checked by this guard:\n  " + "\n  ".join(aliased)
    )
