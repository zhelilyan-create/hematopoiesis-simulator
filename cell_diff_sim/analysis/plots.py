"""Basic visualization utilities for simulation output.

All functions accept a pandas DataFrame produced by ``Recorder.to_dataframe()``
and return a matplotlib ``Axes`` object so callers can further customise or
embed them in a larger figure.

Functions
---------
plot_population_over_time  -- line chart: cell count per type vs time
plot_final_composition     -- bar chart: cell counts at the last recorded time

Notes
-----
Requires matplotlib >= 3.5.  Install with::

    pip install matplotlib

These plots are intended for quick visual sanity checks, not publication.
No attempt is made to match the colour scheme to standard haematopoiesis
diagrams.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import matplotlib.axes
    import pandas as pd


# Fixed colour order so the same cell type always gets the same colour
# across multiple calls in the same session.
_COLOUR_CYCLE = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2",
    "#59a14f", "#edc948", "#b07aa1", "#ff9da7",
]


def plot_population_over_time(
    df: pd.DataFrame,
    ax: matplotlib.axes.Axes | None = None,
    title: str = "Population over time",
) -> matplotlib.axes.Axes:
    """Line chart of each cell type's count over simulation time.

    Parameters
    ----------
    df : pandas.DataFrame
        Output of ``Recorder.to_dataframe()``.  Must contain a ``time``
        column and one column per cell type.
    ax : matplotlib.axes.Axes, optional
        Axes to draw on.  A new figure is created if not provided.
    title : str
        Plot title.

    Returns
    -------
    matplotlib.axes.Axes
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(10, 5))

    cell_cols = sorted(c for c in df.columns if c not in ("time", "total"))

    for i, col in enumerate(cell_cols):
        colour = _COLOUR_CYCLE[i % len(_COLOUR_CYCLE)]
        ax.plot(df["time"], df[col], label=col, color=colour, linewidth=1.2)

    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Cell count")
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3, linestyle="--")

    return ax


def plot_final_composition(
    df: pd.DataFrame,
    ax: matplotlib.axes.Axes | None = None,
    title: str = "Final cell composition",
) -> matplotlib.axes.Axes:
    """Horizontal bar chart of cell counts at the last recorded time point.

    Parameters
    ----------
    df : pandas.DataFrame
        Output of ``Recorder.to_dataframe()``.
    ax : matplotlib.axes.Axes, optional
        Axes to draw on.  A new figure is created if not provided.
    title : str
        Plot title.

    Returns
    -------
    matplotlib.axes.Axes
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(7, 4))

    cell_cols = sorted(c for c in df.columns if c not in ("time", "total"))
    last = df.iloc[-1]
    labels = [c for c in cell_cols if last[c] > 0]
    values = [int(last[c]) for c in labels]
    colours = [_COLOUR_CYCLE[i % len(_COLOUR_CYCLE)] for i in range(len(labels))]

    ax.barh(labels, values, color=colours)
    ax.set_xlabel("Cell count")
    ax.set_title(f"{title}  (t = {last['time']:.1f} h)")
    ax.grid(True, alpha=0.3, linestyle="--", axis="x")

    # Annotate bars with counts
    for bar, val in zip(ax.patches, values):
        ax.text(
            bar.get_width() + max(values) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            str(val),
            va="center",
            fontsize=8,
        )

    return ax


def save_summary_figure(
    df: pd.DataFrame,
    output_path: str,
    t_max: float | None = None,
) -> None:
    """Save a two-panel summary figure (time course + final composition).

    Parameters
    ----------
    df : pandas.DataFrame
        Output of ``Recorder.to_dataframe()``.
    output_path : str
        File path for the saved figure (PNG, PDF, SVG, …).
    t_max : float, optional
        Used in the figure title if provided.
    """
    import matplotlib.pyplot as plt

    fig, (ax_left, ax_right) = plt.subplots(
        1, 2, figsize=(14, 5), constrained_layout=True
    )

    t_label = f"t_max = {t_max} h" if t_max is not None else ""
    plot_population_over_time(df, ax=ax_left, title=f"Population over time  ({t_label})")
    plot_final_composition(df, ax=ax_right)

    fig.suptitle(
        "Hematopoiesis simulation v0.1  —  NON-CALIBRATED PLACEHOLDER RATES",
        fontsize=10,
        style="italic",
        color="grey",
    )

    fig.savefig(output_path, dpi=150)
    plt.close(fig)
