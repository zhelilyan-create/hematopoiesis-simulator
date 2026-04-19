"""Parameter validation: hard bounds + dangerous combination warnings."""
from __future__ import annotations

HARD_BOUNDS: dict[str, tuple[float, float]] = {
    "self_renewal_weight":      (0.0,  1.0),
    "density_gamma":            (0.0, 20.0),
    "density_beta":             (0.0,  3.0),
    "niche_strength":           (0.0, 20.0),
    "crowding_threshold":       (1.0,  5.0),
    "crowding_apoptosis_rate":  (0.0,  1.0),
    "t_max":                    (1.0, 5000.0),
    "seed":                     (-1,  999999),
}

DEFAULTS = {
    "self_renewal_weight":      0.825,
    "density_gamma":            4.0,
    "density_beta":             0.0,
    "niche_strength":           4.0,
    "crowding_threshold":       1.3,
    "crowding_apoptosis_rate":  0.1,
}


def validate_params(params: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings).

    errors   — hard violations that must block the request
    warnings — dangerous but allowed combinations
    """
    errors: list[str] = []
    warnings: list[str] = []

    for key, (lo, hi) in HARD_BOUNDS.items():
        if key not in params:
            continue
        v = params[key]
        try:
            v = float(v)
        except (TypeError, ValueError):
            errors.append(f"Parameter '{key}' must be numeric, got {v!r}")
            continue
        if not (lo <= v <= hi):
            errors.append(
                f"Parameter '{key}' = {v} is outside allowed range [{lo}, {hi}]"
            )

    # self_renewal_weight must not make fates sum > 1 (MPP_MPP fixed at 0.05)
    sr = float(params.get("self_renewal_weight", DEFAULTS["self_renewal_weight"]))
    if 0.0 <= sr <= 1.0 and (1.0 - sr - 0.05) < 0:
        errors.append(
            "self_renewal_weight too high: leaves no room for committed fate "
            "(need sr + 0.05 <= 1.0)"
        )

    # Dangerous combinations
    sr   = float(params.get("self_renewal_weight",     DEFAULTS["self_renewal_weight"]))
    ns   = float(params.get("niche_strength",           DEFAULTS["niche_strength"]))
    apo  = float(params.get("crowding_apoptosis_rate",  DEFAULTS["crowding_apoptosis_rate"]))
    gam  = float(params.get("density_gamma",            DEFAULTS["density_gamma"]))

    if sr > 0.9 and ns > 8:
        warnings.append(
            "HSC self-renewal > 0.9 combined with niche_strength > 8 "
            "may cause stem-lock (HSC dominance, near-zero differentiation)."
        )
    if sr < 0.6 and apo > 0.2:
        warnings.append(
            "Low self-renewal (< 0.6) with high emergency apoptosis (> 0.2) "
            "creates high extinction risk."
        )
    if gam == 0:
        warnings.append(
            "density_gamma = 0 disables the density controller — "
            "population may grow without bound."
        )
    if apo > 0.3:
        warnings.append(
            "crowding_apoptosis_rate > 0.3 is very aggressive and can "
            "crash the population when crowding threshold is crossed."
        )

    return errors, warnings
