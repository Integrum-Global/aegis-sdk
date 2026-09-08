"""Architect-facing working material, shipped with the client it describes.

The handbook (:mod:`aegis_sdk.handbook`) tells you how the platform behaves.
This package is the *working* half: two agent briefs, six task skills, six
guardrails, and one probe you run against your own deployment.

The counts are stated because a reader works from them — an undercount here is
how someone never finds the skill that answers their question. They were wrong
until this was corrected: the corpus grew and this sentence did not.

The distinction that decides what belongs here: the handbook states what is
true, and this package states what to DO about it — including the cases where
what is true is inconvenient and no amount of configuration changes it.

Run the probe against the deployment you were given::

    python -m aegis_sdk.coc.probe --base-url https://<your-deployment>

``probe`` is deliberately NOT imported here. Importing a submodule from its own
package ``__init__`` makes ``python -m aegis_sdk.coc.probe`` execute a module
already in ``sys.modules``, which the runtime warns about and which would leave
this package's own entrypoint the least-tested path in it. The handbook's
checker records the same reasoning for the same shape.
"""

from __future__ import annotations

__all__: list[str] = []
