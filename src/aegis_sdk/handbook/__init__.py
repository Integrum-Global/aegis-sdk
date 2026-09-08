"""The Aegis handbook, for the audiences the SDK is given to.

Architects, operators, developers and users. The parts that are only meaningful
to someone modifying the platform's own source do not ship here — they are not
withheld, they are irrelevant without a checkout the reader does not have.

Verify every claim still names a surface this build actually has::

    python -m aegis_sdk.handbook.check

``check`` is deliberately NOT imported here. Importing a submodule from its own
package ``__init__`` makes ``python -m aegis_sdk.handbook.check`` execute a
module that is already in ``sys.modules``, which the runtime warns about and
which would leave the gate's own entrypoint the least-tested path in it.
"""

from __future__ import annotations

__all__: list[str] = []
