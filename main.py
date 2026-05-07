"""
Cable Gland Plate Layout Tool
Compliant with AS/NZS 3000:2018 (Wiring Rules) and AS/NZS 5000.1 (cable ODs)

Supports Australian cable notation:
  "3x1C 95mm2 Cu X90"   → three single-core 95 mm² copper X-90 XLPE cables
  "1x3C+E 35mm2"        → one 3-core + earth 35 mm² cable (single gland)
  "2x1C 185mm2 Al"      → two single-core 185 mm² aluminium cables
  "M32"                 → explicit gland label, uses manual diameter/clearance
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.patches import Circle, Rectangle


# ---------------------------------------------------------------------------
# AS/NZS 5000.1 approximate overall cable outer diameters (mm)
# Source: Prysmian/Olex AU catalogue, Nexans AU catalogue
# Single-core (1C) X-90 XLPE/PVC; multicore adds ~15-20 % for lay-up
# ---------------------------------------------------------------------------

# 1C X-90 overall OD by conductor cross-section (mm²)
_1C_OD: dict[float, float] = {
    1.5: 7.4,  2.5: 8.2,  4.0: 9.1,  6.0: 10.0,
    10.0: 11.8, 16.0: 13.3, 25.0: 15.5, 35.0: 16.8,
    50.0: 18.9, 70.0: 21.2, 95.0: 24.0, 120.0: 26.8,
    150.0: 29.4, 185.0: 32.3, 240.0: 36.5, 300.0: 40.5,
    400.0: 46.2, 500.0: 51.5,
}

# Multicore lay-up factor vs number of cores (approximate)
_MULTICORE_FACTOR: dict[int, float] = {
    2: 1.55, 3: 1.65, 4: 1.80,
}

# Default gland clearance radius (mm) per gland size bracket (AS/NZS 3000 Cl 3.10)
_GLAND_CLEARANCE = 5.0  # conservative default


def _nearest_od(size_mm2: float, table: dict[float, float]) -> float:
    """Return OD for the nearest standard size in the lookup table."""
    nearest_key = min(table, key=lambda k: abs(k - size_mm2))
    return table[nearest_key]


def approx_cable_od(conductor_mm2: float, num_cores: int) -> float:
    """
    Approximate overall cable outer diameter (mm) per AS/NZS 5000.1 data.
    Multicore OD is estimated from the single-core OD × lay-up factor.
    """
    single_od = _nearest_od(conductor_mm2, _1C_OD)
    if num_cores == 1:
        return single_od
    factor = _MULTICORE_FACTOR.get(num_cores, 1.65 + 0.1 * (num_cores - 3))
    return round(single_od * factor, 1)


# ---------------------------------------------------------------------------
# Cable / Gland data model
# ---------------------------------------------------------------------------

@dataclass
class CableGland:
    """
    Represents a single cable gland entry on the plate.

    cable_od       : overall cable outer diameter (mm) — drives gland selection
    clearance_r    : minimum clearance radius around the gland footprint (mm)
    label          : short description shown in the legend
    cable_spec     : raw spec string if parsed from text (informational)
    """
    cable_od: float
    clearance_r: float = _GLAND_CLEARANCE
    label: str = ""
    cable_spec: str = ""

    @property
    def footprint_r(self) -> float:
        return self.cable_od / 2 + self.clearance_r
    
    @property
    def footprint_area(self) -> float:
        return np.pi * self.footprint_r ** 2


# ---------------------------------------------------------------------------
# Cable spec parser  ("3x1C 95mm2 Cu X90", "1x3C+E 35mm2", "M32 20mm", …)
# ---------------------------------------------------------------------------

_SPEC_RE = re.compile(
    r"""
    (?:(?P<qty>\d+)\s*[xX×])?\s*        # optional qty prefix, e.g. "3x"
    (?P<cores>\d+)\s*C                  # number of cores, e.g. "1C", "3C"
    (?:\+E)?\s*                          # optional "+E" (core + earth)
    (?P<size>[\d.]+)\s*mm[²2]?          # conductor size in mm²
    (?:\s+(?P<material>Cu|Al))?         # optional conductor material
    (?:\s+(?P<insul>X90|V90|XLPE|PVC))? # optional insulation type
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_cable_spec(spec: str) -> list[CableGland]:
    """
    Parse an Australian cable specification string and return a list of
    CableGland objects (one per physical cable entry on the plate).

    Examples
    --------
    "3x1C 95mm2 Cu X90"   → 3 × single-core glands, OD ~24 mm
    "1x3C+E 35mm2"        → 1 × three-core gland, OD ~27.7 mm
    "2x1C 185mm2"         → 2 × single-core glands, OD ~32.3 mm
    """
    m = _SPEC_RE.search(spec)
    if not m:
        raise ValueError(
            f"Cannot parse cable spec: '{spec}'\n"
            "Expected format: [qty x] <cores>C[+E] <size>mm2 [Cu|Al] [X90|V90]\n"
            "Example: '3x1C 95mm2 Cu X90' or '1x3C+E 35mm2'"
        )

    qty = int(m.group("qty") or 1)
    num_cores = int(m.group("cores"))
    size_mm2 = float(m.group("size"))
    material = (m.group("material") or "Cu").upper()
    insul = (m.group("insul") or "X90").upper()

    od = approx_cable_od(size_mm2, num_cores)
    core_str = f"{num_cores}C" if num_cores == 1 else f"{num_cores}C+E"
    label = f"{qty}×{core_str} {size_mm2:.0f}mm² {material} {insul}"

    return [
        CableGland(cable_od=od, clearance_r=_GLAND_CLEARANCE,
                   label=f"{core_str} {size_mm2:.0f}mm²", cable_spec=label)
        for _ in range(qty)
    ]


def make_glands(*specs: str | tuple) -> list[CableGland]:
    """
    Build a gland list from mixed inputs:
      str  → parsed via parse_cable_spec()
      tuple(od, clearance, label) → explicit manual gland
    """
    glands: list[CableGland] = []
    for spec in specs:
        if isinstance(spec, str):
            glands.extend(parse_cable_spec(spec))
        else:
            od, clr, lbl = spec
            glands.append(CableGland(cable_od=od, clearance_r=clr, label=lbl))
    return glands


# ---------------------------------------------------------------------------
# Layout engine
# ---------------------------------------------------------------------------

def _check_boundary(x: float, y: float, r: float,
                    x_lo: float, x_hi: float, y_lo: float, y_hi: float) -> bool:
    return x - r >= x_lo and x + r <= x_hi and y - r >= y_lo and y + r <= y_hi


def _check_no_overlaps(positions: list[tuple]) -> bool:
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            x1, y1, g1 = positions[i]
            x2, y2, g2 = positions[j]
            if np.hypot(x1 - x2, y1 - y2) < g1.footprint_r + g2.footprint_r:
                return False
    return True


def _pack_row(glands: list[CableGland], y: float, plate_width: float,
              x_lo: float, x_hi: float, gap: float = 5.0,
              stagger_offset: float = 0.0) -> tuple[list[tuple], bool]:
    """Pack a single row of glands centred on plate_width, return (positions, fits)."""
    total_w = sum(g.footprint_r * 2 for g in glands) + (len(glands) - 1) * gap
    start_x = (plate_width - total_w) / 2 + stagger_offset
    positions, fits = [], True
    cursor = start_x
    for g in glands:
        cx = cursor + g.footprint_r
        cursor += g.footprint_r * 2 + gap
        ok = _check_boundary(cx, y, g.footprint_r, x_lo, x_hi,
                              x_lo, plate_width - (plate_width - x_hi))
        if not ok:
            fits = False
        positions.append((cx, y, g))
    return positions, fits


def calculate_layout(plate_width: float, plate_height: float,
                     glands: list[CableGland],
                     edge_margin: float = 15.0) -> tuple[list[tuple], bool]:
    """
    Row-based packing within the margin boundary.
    Tries 1 and 2 rows, returns the first valid layout (or best-effort if none fit).
    """
    x_lo = edge_margin
    x_hi = plate_width - edge_margin
    y_lo = edge_margin
    y_hi = plate_height - edge_margin

    if x_hi <= x_lo or y_hi <= y_lo:
        return [], False

    sorted_glands = sorted(glands, key=lambda g: g.footprint_r, reverse=True)
    best: list[tuple] = []

    for num_rows in range(1, 3):
        rows = [sorted_glands[i::num_rows] for i in range(num_rows)]

        if num_rows == 1:
            y_centres = [plate_height / 2]
        else:
            y_centres = list(np.linspace(y_lo, y_hi, num_rows + 2)[1:-1])

        all_positions, layout_ok = [], True
        for row_idx, (row_glands, y) in enumerate(zip(rows, y_centres)):
            stagger = 10.0 if (num_rows > 1 and row_idx % 2 == 1) else 0.0
            row_pos, row_ok = _pack_row(
                row_glands, y, plate_width, x_lo, x_hi,
                stagger_offset=stagger
            )
            all_positions.extend(row_pos)
            layout_ok = layout_ok and row_ok

        best = all_positions
        if layout_ok and _check_no_overlaps(all_positions):
            return all_positions, True

    return best, False


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def initialise_plot(plate_width: float, plate_height: float) -> tuple:
    scale = 0.05
    fig, ax = plt.subplots(figsize=(plate_width * scale, plate_height * scale))
    ax.add_patch(Rectangle((0, 0), plate_width, plate_height,
                            facecolor="#0a1c20", edgecolor="#ff0000",
                            linestyle="--", label="Plate Boundary"))
    ax.set_xlim(-10, plate_width + 10)
    ax.set_ylim(-10, plate_height + 10)
    ax.set_aspect("equal")
    ax.set_xlabel("Width (mm)")
    ax.set_ylabel("Height (mm)")
    ax.grid(True, linestyle=":", alpha=0.3)
    return fig, ax


def plot_layout(ax: Axes, plate_width: float, plate_height: float,
                glands: list[CableGland], edge_margin: float = 15.0) -> None:
    layout, fits = calculate_layout(plate_width, plate_height, glands, edge_margin)

    ax.add_patch(Rectangle(
        (edge_margin, edge_margin),
        plate_width - 2 * edge_margin,
        plate_height - 2 * edge_margin,
        fill=False, edgecolor="yellow", linestyle=":", alpha=0.4,
        label="Margin Limit (AS/NZS 3000)"
    ))

    title = (f"Gland Layout — {len(layout)} cables" if fits
             else "LAYOUT ERROR: OVERLAP / OUT-OF-BOUNDS")
    ax.set_title(title, color="white" if fits else "red", pad=20, weight="bold")

    for idx, (x, y, g) in enumerate(layout, start=1):
        outside = not (edge_margin <= x - g.footprint_r and
                       x + g.footprint_r <= plate_width - edge_margin and
                       edge_margin <= y - g.footprint_r and
                       y + g.footprint_r <= plate_height - edge_margin)
        cable_color = "#e74c3c" if outside else "#3498db"

        ax.add_patch(Circle((x, y), g.footprint_r,
                             fill=False, edgecolor="#7f8c8d",
                             linestyle="--", linewidth=1, alpha=0.5))
        ax.add_patch(Circle((x, y), g.cable_od / 2,
                             color=cable_color, alpha=0.8,
                             label=f"{idx}: {g.label}", zorder=3))
        ax.text(x, y, str(idx), color="white", weight="bold",
                ha="center", va="center", zorder=4, fontsize=7)

    ax.legend(loc="upper left", bbox_to_anchor=(1, 1),
              title="ID  |  Cable Type", prop={"size": 8})


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

def run_example() -> None:
    width, height = 400, 200

    glands = make_glands(
        "1x3C+E 70mm2"    # 1 × 3-core+E 70 mm² multicore
    )

    fig, ax = initialise_plot(width, height)
    plot_layout(ax, width, height, glands, edge_margin=20)
    plt.tight_layout()
    plt.show()

    # Print summary to console
    print(f"\n{'ID':<4} {'Label':<22} {'Cable OD':>9} {'Footprint R':>12}")
    print("-" * 52)
    layout, _ = calculate_layout(width, height, glands, edge_margin=20)
    for idx, (x, y, g) in enumerate(layout, start=1):
        print(f"{idx:<4} {g.label:<22} {g.cable_od:>8.1f}mm {g.footprint_r:>11.1f}mm")


if __name__ == "__main__":
    run_example()
