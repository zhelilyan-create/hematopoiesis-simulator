"""Centriole state dataclass — v0.4.

CentrioleState tracks the replicative age of the centriole carried by a cell.
It is the upstream cause of asymmetric stemness inheritance in
:class:`~models.inheritance.CentrioleInheritanceRules`.

Design
------
One field: ``age`` — the number of division cycles this centriole has existed.

At each division:

- Daughter 0 (inherits the *old* centriole):  ``CentrioleState(age = parent.age + 1)``
- Daughter 1 (inherits the *new* centriole):  ``CentrioleState(age = 0)``

The "old centriole → daughter 0 → higher stemness" convention is fixed in
:class:`~models.inheritance.CentrioleInheritanceRules`.

Founder assumption
------------------
All founder cells start with ``CentrioleState(age=0)`` — a freshly formed
centriole with no prior history.  On the **first division** of a founder cell:

    stemness_delta = centriole_stemness_factor * min(0, age_cap) = 0

Both daughters therefore receive the same stemness score as the founder.
Stemness asymmetry only emerges from the **second division onward**, once
the old-centriole lineage has ``age >= 1``.

This is an **intentional v0.4 assumption**, not a limitation.  A simulation
can override this by founding cells with a non-zero ``age``.

Biological framing (kept modest)
---------------------------------
This is a minimal mechanistic proxy.  At each division, one daughter inherits
the older centriole (age incremented) and the other inherits a freshly formed
one (age = 0).  A configurable, bounded factor translates centriole age into
a stemness shift.  This model makes no claims about specific molecular
mechanisms (PCM asymmetry, satellite proteins, niche proximity, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CentrioleState:
    """Per-cell centriole age state.

    Parameters
    ----------
    age : int
        Number of division cycles this centriole has existed.
        ``0`` means freshly formed (default for all founder cells).

    Raises
    ------
    ValueError
        If ``age < 0``.
    """

    age: int = 0

    def __post_init__(self) -> None:
        if self.age < 0:
            raise ValueError(f"CentrioleState.age must be >= 0, got {self.age}")
