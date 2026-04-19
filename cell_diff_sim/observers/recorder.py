"""Time-series population recorder — v0.8.

Recorder is an observer that collects a lightweight snapshot of the
population after every simulation event.  Snapshots can be exported to
a pandas DataFrame for downstream analysis and plotting.

v0.8 extension
--------------
When ``track_states=True`` is passed to the constructor, each snapshot
additionally records per-step internal-state distributions:

    mean_stemness, mean_stress, mean_bias, population_size

These are available via :meth:`to_state_dataframe`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cell_diff_sim.cell import CellType
    from cell_diff_sim.population import Population


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    """Population count (and optionally state distributions) at one time point.

    Parameters
    ----------
    time : float
        Simulation time of this snapshot (hours).
    counts : dict[CellType, int]
        Number of live cells per cell type at this moment.
        Cell types with zero cells are omitted.
    mean_stemness : float or None
        Population-mean stemness score.  Populated only when
        ``Recorder(track_states=True)`` is used.
    mean_stress : float or None
        Population-mean stress score.  Populated only when
        ``Recorder(track_states=True)`` is used.
    mean_bias : float or None
        Population-mean epigenetic bias.  Populated only when
        ``Recorder(track_states=True)`` is used.
    """

    time: float
    counts: dict[CellType, int] = field(default_factory=dict)
    # v0.8 state distributions (None when track_states=False)
    mean_stemness: float | None = None
    mean_stress:   float | None = None
    mean_bias:     float | None = None

    @property
    def total(self) -> int:
        """Total number of live cells across all types."""
        return sum(self.counts.values())

    def __repr__(self) -> str:
        summary = ", ".join(f"{k}={v}" for k, v in sorted(self.counts.items()))
        return f"Snapshot(t={self.time:.3f}, total={self.total}, [{summary}])"


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------

class Recorder:
    """Collects population snapshots after every simulation event.

    Attach to CTMCEngine via the ``observers`` parameter.  After the
    simulation, call :meth:`to_dataframe` to get a tidy DataFrame with
    one row per event.

    Parameters
    ----------
    track_states : bool
        When ``True``, each snapshot also records population-mean
        stemness, stress, and epigenetic bias.  Default ``False``
        (zero overhead — v0.7-compatible behaviour).

    Example
    -------
    >>> recorder = Recorder(track_states=True)
    >>> engine = CTMCEngine(model, population, observers=[recorder])
    >>> engine.run(t_max=100.0)
    >>> df_counts = recorder.to_dataframe()
    >>> df_states = recorder.to_state_dataframe()

    Extension path
    --------------
    - Subsample every N steps for large populations.
    - Stream snapshots to disk incrementally for very long runs.
    - Add ``on_division`` / ``on_apoptosis`` hooks for lineage tracking.
    """

    def __init__(self, track_states: bool = False) -> None:
        self._snapshots: list[Snapshot] = []
        self._track_states = track_states

    # ------------------------------------------------------------------
    # Observer interface
    # ------------------------------------------------------------------

    def on_step(self, time: float, population: Population) -> None:
        """Record a snapshot of the current population state.

        Called by CTMCEngine after every event.

        Parameters
        ----------
        time : float
            Current simulation time (hours).
        population : Population
            Current population.  Only ``snapshot()`` is called — the
            population is not mutated.
        """
        snap = Snapshot(time=time, counts=population.snapshot())

        if self._track_states:
            cells = list(population)
            n = len(cells)
            if n > 0:
                snap.mean_stemness = sum(c.internal_state.stemness_score   for c in cells) / n
                snap.mean_stress   = sum(c.internal_state.stress_score     for c in cells) / n
                snap.mean_bias     = sum(c.internal_state.epigenetic_bias  for c in cells) / n
            else:
                snap.mean_stemness = 0.0
                snap.mean_stress   = 0.0
                snap.mean_bias     = 0.0

        self._snapshots.append(snap)

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    @property
    def snapshots(self) -> list[Snapshot]:
        """All recorded snapshots, in chronological order (read-only copy)."""
        return list(self._snapshots)

    def __len__(self) -> int:
        """Number of snapshots recorded so far."""
        return len(self._snapshots)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_dataframe(self):
        """Export cell-count snapshots to a tidy pandas DataFrame.

        Returns
        -------
        pandas.DataFrame
            Columns: ``time``, one column per cell type encountered,
            ``total``.  Missing cell types in a given snapshot are
            filled with 0.  One row per recorded event.

        Raises
        ------
        ImportError
            If pandas is not installed.
        """
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "pandas is required for Recorder.to_dataframe(). "
                "Install it with: pip install pandas"
            ) from exc

        if not self._snapshots:
            return pd.DataFrame()

        rows = [
            {"time": s.time, **s.counts, "total": s.total}
            for s in self._snapshots
        ]
        df = pd.DataFrame(rows).fillna(0)
        # Ensure time column stays float; cell count columns become int
        df["time"] = df["time"].astype(float)
        count_cols = [c for c in df.columns if c not in ("time", "total")]
        df[count_cols + ["total"]] = df[count_cols + ["total"]].astype(int)
        return df

    def to_state_dataframe(self):
        """Export state-distribution snapshots to a tidy pandas DataFrame.

        Available only when the recorder was created with
        ``track_states=True``.  Raises ``RuntimeError`` otherwise.

        Returns
        -------
        pandas.DataFrame
            Columns: ``time``, ``population_size``,
            ``mean_stemness``, ``mean_stress``, ``mean_bias``.
            One row per recorded event.

        Raises
        ------
        RuntimeError
            If ``track_states`` was not enabled at construction time.
        ImportError
            If pandas is not installed.
        """
        if not self._track_states:
            raise RuntimeError(
                "State tracking was not enabled.  "
                "Create the Recorder with track_states=True."
            )
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "pandas is required for Recorder.to_state_dataframe(). "
                "Install it with: pip install pandas"
            ) from exc

        if not self._snapshots:
            return pd.DataFrame()

        rows = [
            {
                "time":           s.time,
                "population_size": s.total,
                "mean_stemness":  s.mean_stemness,
                "mean_stress":    s.mean_stress,
                "mean_bias":      s.mean_bias,
            }
            for s in self._snapshots
        ]
        df = pd.DataFrame(rows)
        df["time"]           = df["time"].astype(float)
        df["population_size"] = df["population_size"].astype(int)
        return df
