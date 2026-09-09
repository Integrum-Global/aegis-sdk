"""Architect-facing working material, shipped with the client it describes.

The handbook (:mod:`aegis_sdk.handbook`) tells you how the platform behaves.
This package is the *working* half: two agent briefs, six task skills, seven
guardrails, and one probe you run against your own deployment.

The counts are stated because a reader works from them — an undercount here is
how someone never finds the skill that answers their question. This sentence has
now been wrong TWICE, each time because the corpus grew and the prose did not,
and the second time while carrying a note claiming it had been corrected. Prose
saying it is current is not a mechanism. So it is now pinned against the
directories it describes by a test in the platform repository, which fails when
a file is added or removed and this sentence is not updated in the same change.
If you are reading a count here that disagrees with the directories beside it,
trust the directories: they are the corpus, this sentence only describes it.

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
