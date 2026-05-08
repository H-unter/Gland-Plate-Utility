"""
Cable Gland Plate Layout Tool — main.py
Compliant with AS/NZS 3000:2018 / AS/NZS 5000.1 / IEC 60228 / IEC 60502-1

USAGE
-----
  python main.py
  Opens an interactive tkinter GUI to design cable gland layouts.

OD CALCULATION METHOD
---------------------
  1. Conductor OD       IEC 60228:2004 Table C.1 (Cu) / Table C.2 (Al compacted)
  2. Insulation thk     IEC 60502-1 / AS/NZS 5000.1 Table 3  (0.6/1 kV nominal)
  3. Insulated core OD  d_cond + 2 * t_ins
  4. Bundle OD          d_core * (1 + 1/sin(pi/n))  — exact circumscribed-circle
  5. Bedding            1.0 mm PVC tape, multicore only  (AS/NZS 5000.1 Cl 8)
  6. Sheath thk         max(0.035 * D + 1.0,  1.4 mm)   (IEC 60502-1 Cl 12)
  7. Overall OD         d_under_sheath + 2 * t_sheath
"""

from __future__ import annotations

import math
import re
import sys
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import messagebox, ttk

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Circle, Rectangle


# =============================================================================
# IEC 60228 / IEC 60502-1 lookup tables
# =============================================================================

# IEC 60228:2004 Table C.1 — Class 2 stranded non-compacted Cu, max diameter (mm)
_CONDUCTOR_OD_CU: dict[float, float] = {
    0.5: 1.1,    0.75: 1.2,   1.0: 1.4,    1.5: 1.7,
    2.5: 2.2,    4.0: 2.7,    6.0: 3.3,    10.0: 4.2,
    16.0: 5.3,   25.0: 6.6,   35.0: 7.9,   50.0: 9.1,
    70.0: 11.0,  95.0: 12.9,  120.0: 14.5, 150.0: 16.2,
    185.0: 18.0, 240.0: 20.6, 300.0: 23.1, 400.0: 26.1,
    500.0: 29.2, 630.0: 33.2,
}

# IEC 60228:2004 Table C.2 — Class 2 compacted circular conductors, midpoint (mm)
# Used for Al conductors (always compacted) and compacted Cu.
_CONDUCTOR_OD_COMPACTED: dict[float, float] = {
    10.0: 3.8,    16.0: 4.9,   25.0: 6.05,  35.0: 7.05,
    50.0: 8.15,   70.0: 9.75,  95.0: 11.5,  120.0: 12.9,
    150.0: 14.35, 185.0: 16.05, 240.0: 18.4, 300.0: 20.65,
    400.0: 23.45, 500.0: 26.45, 630.0: 30.6,
}

# IEC 60502-1 Table 2 / AS/NZS 5000.1 Table 3 — nominal insulation thickness (mm)
# X-90 (XLPE) and V-90 (PVC) share this schedule at 0.6/1 kV.
_INSULATION_THICKNESS: dict[float, float] = {
    0.5: 0.7,   0.75: 0.7,  1.0: 0.7,   1.5: 0.7,
    2.5: 0.9,   4.0: 1.0,   6.0: 1.0,   10.0: 1.0,
    16.0: 1.0,  25.0: 1.2,  35.0: 1.2,  50.0: 1.4,
    70.0: 1.4,  95.0: 1.6,  120.0: 1.6, 150.0: 1.8,
    185.0: 2.0, 240.0: 2.2, 300.0: 2.4, 400.0: 2.6,
    500.0: 2.8, 630.0: 3.0,
}

_GLAND_CLEARANCE = 5.0   # default footprint clearance radius (mm), AS/NZS 3000 Cl 3.10


# =============================================================================
# Layer-by-layer OD geometry
# =============================================================================

def _nearest(size_mm2: float, table: dict[float, float]) -> float:
    return table[min(table, key=lambda k: abs(k - size_mm2))]


def _conductor_od(size_mm2: float, compacted: bool) -> float:
    """IEC 60228 conductor OD: compacted table for Al; non-compacted for Cu."""
    if compacted and size_mm2 >= 10.0:
        return _nearest(size_mm2, _CONDUCTOR_OD_COMPACTED)
    return _nearest(size_mm2, _CONDUCTOR_OD_CU)


def _insulation_thickness(size_mm2: float) -> float:
    return _nearest(size_mm2, _INSULATION_THICKNESS)


def _bundle_od(core_od: float, num_cores: int) -> float:
    """
    Exact circumscribed-circle diameter for n equal circular cores.
        d_bundle = d_core * (1 + 1/sin(pi/n))
    n=1 -> d_core; n=3 -> factor 2.155; n=4 -> factor 2.414
    """
    if num_cores == 1:
        return core_od
    r_core = core_od / 2.0
    return 2.0 * r_core * (1.0 + 1.0 / math.sin(math.pi / num_cores))


def _sheath_thickness(od_under: float) -> float:
    """IEC 60502-1 Cl 12: t = max(0.035 * D + 1.0, 1.4 mm)."""
    return max(0.035 * od_under + 1.0, 1.4)


def calc_cable_od(
    size_mm2: float,
    num_cores: int,
    material: str = "Cu",
    has_earth: bool = False,
    bedding_mm: float = 1.0,
) -> tuple[float, dict]:
    """
    Calculate overall cable OD (mm) from first principles.
    Returns (overall_od, breakdown_dict).
    """
    compacted   = (material.upper() == "AL")
    d_cond      = _conductor_od(size_mm2, compacted)
    t_ins       = _insulation_thickness(size_mm2)
    d_core      = d_cond + 2.0 * t_ins

    total_cores = num_cores + (1 if has_earth else 0)
    d_bundle    = _bundle_od(d_core, total_cores)

    t_bed       = bedding_mm if total_cores > 1 else 0.0
    d_under     = d_bundle + 2.0 * t_bed
    t_sheath    = _sheath_thickness(d_under)
    overall_od  = d_under + 2.0 * t_sheath

    breakdown = {
        "conductor_od_mm":       round(d_cond,     2),
        "insulation_thk_mm":     round(t_ins,      2),
        "insulated_core_od_mm":  round(d_core,     2),
        "total_cores_bundled":   total_cores,
        "bundle_od_mm":          round(d_bundle,   2),
        "bedding_thk_mm":        round(t_bed,      2),
        "sheath_thk_mm":         round(t_sheath,   2),
        "overall_od_mm":         round(overall_od, 2),
    }
    return round(overall_od, 1), breakdown


# =============================================================================
# Data model
# =============================================================================

@dataclass
class CableGland:
    cable_od: float
    clearance_r: float = _GLAND_CLEARANCE
    label: str = ""
    breakdown: dict = field(default_factory=dict)

    @property
    def footprint_r(self) -> float:
        return self.cable_od / 2.0 + self.clearance_r


# =============================================================================
# Cable spec parser (for standalone / example use)
# =============================================================================

_SPEC_RE = re.compile(
    r"""
    (?:(?P<qty>\d+)\s*[xX*×])?\s*
    (?P<cores>\d+)\s*C
    (?P<earth>\+E)?\s*
    (?P<size>[\d.]+)\s*mm[2²]?
    (?:\s+(?P<material>Cu|Al))?
    (?:\s+(?P<insul>X90|V90|XLPE|PVC))?
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_cable_spec(spec: str) -> list[CableGland]:
    m = _SPEC_RE.search(spec)
    if not m:
        raise ValueError(
            f"Cannot parse: '{spec}'\n"
            "Expected: [qty x] <n>C[+E] <size>mm2 [Cu|Al] [X90|V90]"
        )
    qty       = int(m.group("qty") or 1)
    num_cores = int(m.group("cores"))
    size_mm2  = float(m.group("size"))
    has_earth = m.group("earth") is not None
    material  = (m.group("material") or "Cu").upper()
    insul     = (m.group("insul") or "X90").upper()

    od, breakdown = calc_cable_od(size_mm2, num_cores, material, has_earth)
    earth_str = "+E" if has_earth else ""
    label     = f"{num_cores}C{earth_str} {size_mm2:.0f}mm² {material} {insul}"

    return [CableGland(cable_od=od, clearance_r=_GLAND_CLEARANCE,
                       label=label, breakdown=breakdown)
            for _ in range(qty)]


def make_glands(*specs: "str | tuple") -> list[CableGland]:
    glands: list[CableGland] = []
    for spec in specs:
        if isinstance(spec, str):
            glands.extend(parse_cable_spec(spec))
        else:
            od, clr, lbl = spec
            glands.append(CableGland(cable_od=od, clearance_r=clr, label=lbl))
    return glands



# =============================================================================
# Entry point — tkinter GUI
# =============================================================================


class GlandLayoutApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cable Gland Plate Layout Tool")
        self.root.geometry("1200x800")
        
        self.fig = None
        self.canvas = None
        self.canvas_widget = None
        self.layout = []
        self.fits = False
        
        self._build_ui()
        
    def _build_ui(self):
        """Build the tkinter interface."""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # ── Left panel ────────────────────────────────────────────────────────
        SIDEBAR_W = 260  # fixed pixel width for the sidebar

        left_container = ttk.Frame(main_frame, width=SIDEBAR_W)
        left_container.pack(side="left", fill="y", expand=False, padx=(0, 5))
        left_container.pack_propagate(False)   # honour the fixed width

        # Canvas + scrollbar — background matches ttk theme (system default)
        sidebar_bg = ttk.Style().lookup("TFrame", "background") or "SystemButtonFace"
        sidebar_canvas = tk.Canvas(
            left_container, highlightthickness=0,
            bg=sidebar_bg, width=SIDEBAR_W,
        )
        scrollbar = ttk.Scrollbar(left_container, orient="vertical",
                                   command=sidebar_canvas.yview)
        scrollable_frame = ttk.Frame(sidebar_canvas)

        # Keep the inner frame the same width as the canvas at all times
        def _on_canvas_configure(event):
            sidebar_canvas.itemconfig(_win_id, width=event.width)
        sidebar_canvas.bind("<Configure>", _on_canvas_configure)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: sidebar_canvas.configure(
                scrollregion=sidebar_canvas.bbox("all")
            ),
        )

        _win_id = sidebar_canvas.create_window(
            (0, 0), window=scrollable_frame, anchor="nw"
        )
        sidebar_canvas.configure(yscrollcommand=scrollbar.set)

        def _on_mousewheel(event):
            sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        sidebar_canvas.bind_all("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side="right", fill="y")
        sidebar_canvas.pack(side="left", fill="both", expand=True)

        # ── Plate Dimensions ─────────────────────────────────────────────────
        plate_frame = ttk.LabelFrame(scrollable_frame, text="Plate Dimensions (mm)")
        plate_frame.pack(fill="x", padx=6, pady=(8, 4))
        plate_frame.columnconfigure(1, weight=1)

        self.width_var  = tk.StringVar(value="400")
        self.height_var = tk.StringVar(value="200")
        self.margin_var = tk.StringVar(value="20")
        self.gap_var    = tk.StringVar(value="5")

        fields = [
            ("Width:",       self.width_var),
            ("Height:",      self.height_var),
            ("Edge Margin:", self.margin_var),
            ("Gap Between:", self.gap_var),
        ]
        for row, (lbl, var) in enumerate(fields):
            ttk.Label(plate_frame, text=lbl).grid(
                row=row, column=0, sticky="w", padx=(8, 4), pady=4
            )
            ttk.Entry(plate_frame, textvariable=var).grid(
                row=row, column=1, sticky="ew", padx=(0, 8), pady=4
            )

        # ── Add Cable ─────────────────────────────────────────────────────────
        cable_frame = ttk.LabelFrame(scrollable_frame, text="Add Cable")
        cable_frame.pack(fill="x", padx=6, pady=4)
        cable_frame.columnconfigure(0, weight=1)

        ttk.Label(cable_frame, text="Spec (e.g. 3x 1C+E 35mm²):").pack(
            anchor="w", padx=8, pady=(8, 2)
        )
        self.cable_spec_var = tk.StringVar()
        ttk.Entry(cable_frame, textvariable=self.cable_spec_var).pack(
            fill="x", padx=8, pady=(0, 4)
        )

        ttk.Label(cable_frame, text="Or manual OD (mm):").pack(
            anchor="w", padx=8, pady=(4, 2)
        )
        self.manual_od_var = tk.StringVar()
        ttk.Entry(cable_frame, textvariable=self.manual_od_var).pack(
            fill="x", padx=8, pady=(0, 4)
        )

        ttk.Label(cable_frame, text="Label (optional):").pack(
            anchor="w", padx=8, pady=(4, 2)
        )
        self.label_var = tk.StringVar()
        ttk.Entry(cable_frame, textvariable=self.label_var).pack(
            fill="x", padx=8, pady=(0, 4)
        )

        ttk.Button(cable_frame, text="Add Cable", command=self._add_cable).pack(
            fill="x", padx=8, pady=(4, 8)
        )

        # ── Cables Added ──────────────────────────────────────────────────────
        list_frame = ttk.LabelFrame(scrollable_frame, text="Cables Added")
        list_frame.pack(fill="x", padx=6, pady=4)

        list_scrollbar = ttk.Scrollbar(list_frame)
        list_scrollbar.pack(side="right", fill="y")

        self.cable_listbox = tk.Listbox(
            list_frame, yscrollcommand=list_scrollbar.set, height=8
        )
        self.cable_listbox.pack(side="left", fill="both", expand=True,
                                padx=(6, 0), pady=6)
        list_scrollbar.config(command=self.cable_listbox.yview)

        # Action buttons — stacked vertically inside the list frame
        ttk.Button(list_frame, text="Remove Selected",
                   command=self._remove_cable).pack(fill="x", padx=6, pady=(0, 3))
        ttk.Button(list_frame, text="Clear All",
                   command=self._clear_cables).pack(fill="x", padx=6, pady=(0, 6))

        # ── Generate Layout ───────────────────────────────────────────────────
        ttk.Button(
            scrollable_frame, text="⚡  Generate Layout",
            command=self._calculate,
        ).pack(fill="x", padx=6, pady=(8, 4))

        # ── Status ────────────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            scrollable_frame, textvariable=self.status_var,
            wraplength=SIDEBAR_W - 20, justify="left",
        ).pack(fill="x", padx=8, pady=(0, 8))

        # ── Right panel: plot ─────────────────────────────────────────────────
        self.plot_frame = ttk.Frame(main_frame)
        self.plot_frame.pack(side="right", fill="both", expand=True)

        # Store glands in memory
        self.glands = []
        
    def _add_cable(self):
        """Add a cable to the list."""
        spec = self.cable_spec_var.get().strip()
        manual_od = self.manual_od_var.get().strip()
        label = self.label_var.get().strip()
        
        try:
            if manual_od:
                # Manual OD entry
                od = float(manual_od)
                if not label:
                    label = f"Manual OD {od:.1f} mm"
                gland = CableGland(cable_od=od, clearance_r=_GLAND_CLEARANCE, 
                                 label=label, breakdown={})
                self.glands.append(gland)
                display = f"Manual OD {od:.1f} mm — {label}"
            elif spec:
                # Parse cable spec
                new_glands = parse_cable_spec(spec)
                self.glands.extend(new_glands)
                display = f"{len(new_glands)}x {spec}"
            else:
                messagebox.showwarning("Input Error", "Enter a cable spec or manual outer diameter")
                return
            
            self.cable_listbox.insert(tk.END, display)
            self.cable_spec_var.set("")
            self.manual_od_var.set("")
            self.label_var.set("")
            self.status_var.set(f"{len(self.glands)} cable(s) added")
        except Exception as e:
            messagebox.showerror("Parse Error", str(e))
            
    def _remove_cable(self):
        """Remove selected cable from list."""
        sel = self.cable_listbox.curselection()
        if sel:
            idx = sel[0]
            self.cable_listbox.delete(idx)
            # Find which glands correspond to this entry and remove them
            # Simple approach: remove the last N glands that were added
            self.glands.pop(idx)
            self.status_var.set(f"{len(self.glands)} cable(s) remaining")
            
    def _clear_cables(self):
        """Clear all cables."""
        self.cable_listbox.delete(0, tk.END)
        self.glands = []
        self.status_var.set("Cables cleared")
        
    def _calculate(self):
        """Calculate layout and update plot."""
        if not self.glands:
            messagebox.showwarning("No Cables", "Add at least one cable first")
            return
            
        try:
            width = float(self.width_var.get())
            height = float(self.height_var.get())
            margin = float(self.margin_var.get())
            gap = float(self.gap_var.get())
        except ValueError:
            messagebox.showerror("Invalid Input", "Plate dimensions must be numbers")
            return
        
        # Calculate layout
        self.layout, self.fits = calculate_layout(width, height, self.glands, 
                                                  edge_margin=margin, gap=gap)
        
        # Status message
        if self.fits:
            msg = f"✓ Layout valid: {len(self.layout)} cables scheduled"
            self.status_var.set(msg)
        else:
            msg = f"⚠ Layout warning: {len(self.layout)} cables, but overlaps/bounds issues"
            self.status_var.set(msg)
        
        # Redraw plot
        self._plot_layout(width, height, margin, gap)
        
    def _plot_layout(self, width, height, margin, gap):
        """Redraw the matplotlib plot in the tkinter window."""
        # Clear old plot
        if self.canvas_widget:
            self.canvas_widget.get_tk_widget().destroy()
            self.canvas = None
            
        # Create new figure
        scale = 0.01
        fig, ax = plt.subplots(figsize=(width * scale + 2, height * scale + 1.5))
        
        # Draw plate boundary
        ax.add_patch(Rectangle((0, 0), width, height,
                              facecolor="#0a1c20", edgecolor="#ff0000",
                              linestyle="--", label="Plate Boundary"))
        
        # Draw margin limit
        ax.add_patch(Rectangle((margin, margin),
                              width - 2 * margin,
                              height - 2 * margin,
                              fill=False, edgecolor="yellow", linestyle=":",
                              alpha=0.4, label="Margin Limit (AS/NZS 3000)"))
        
        # Draw cables
        for idx, (x, y, g) in enumerate(self.layout, start=1):
            outside = not _check_boundary(x, y, g.footprint_r,
                                        margin, width - margin,
                                        margin, height - margin)
            cable_color = "#e74c3c" if outside else "#3498db"
            
            # Footprint circle (dashed)
            ax.add_patch(Circle((x, y), g.footprint_r,
                               fill=False, edgecolor="#7f8c8d",
                               linestyle="--", linewidth=1, alpha=0.5))
            
            # Cable circle
            ax.add_patch(Circle((x, y), g.cable_od / 2.0,
                               color=cable_color, alpha=0.8,
                               label=f"{idx}: {g.label}", zorder=3))
            
            # Number label
            ax.text(x, y, str(idx), color="white", weight="bold",
                   ha="center", va="center", zorder=4, fontsize=7)
        
        # Formatting
        title = (f"Gland Layout — {len(self.layout)} cables" if self.fits
                else "LAYOUT WARNING: OVERLAP / OUT-OF-BOUNDS")
        ax.set_title(title, color="white" if self.fits else "#e74c3c",
                    pad=20, weight="bold")
        
        ax.set_xlim(-10, width + 10)
        ax.set_ylim(-10, height + 10)
        ax.set_aspect("equal")
        ax.set_xlabel("Width (mm)")
        ax.set_ylabel("Height (mm)")
        ax.grid(True, linestyle=":", alpha=0.3)
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1),
                 title="ID  |  Cable", prop={"size": 8})
        
        plt.tight_layout()
        
        # Embed in tkinter
        self.canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        self.canvas.draw()
        self.canvas_widget = self.canvas
        self.canvas_widget.get_tk_widget().pack(fill="both", expand=True)


def _check_boundary(x, y, r, x_lo, x_hi, y_lo, y_hi) -> bool:
    return x - r >= x_lo and x + r <= x_hi and y - r >= y_lo and y + r <= y_hi


def _check_no_overlaps(positions: list[tuple]) -> bool:
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            x1, y1, g1 = positions[i]
            x2, y2, g2 = positions[j]
            if np.hypot(x1 - x2, y1 - y2) < g1.footprint_r + g2.footprint_r:
                return False
    return True


def _pack_row(glands, y, plate_width, x_lo, x_hi, gap=5.0, stagger=0.0):
    total_w = sum(g.footprint_r * 2.0 for g in glands) + (len(glands) - 1) * gap
    cursor  = (plate_width - total_w) / 2.0 + stagger
    positions, fits = [], True
    for g in glands:
        cx      = cursor + g.footprint_r
        cursor += g.footprint_r * 2.0 + gap
        if not _check_boundary(cx, y, g.footprint_r, x_lo, x_hi, x_lo, x_hi):
            fits = False
        positions.append((cx, y, g))
    return positions, fits


def calculate_layout(plate_width, plate_height, glands, edge_margin=15.0, gap=5.0):
    x_lo, x_hi = edge_margin, plate_width  - edge_margin
    y_lo, y_hi = edge_margin, plate_height - edge_margin

    if x_hi <= x_lo or y_hi <= y_lo:
        return [], False

    sorted_glands = sorted(glands, key=lambda g: g.footprint_r, reverse=True)
    best: list[tuple] = []

    for num_rows in range(1, 3):
        rows      = [sorted_glands[i::num_rows] for i in range(num_rows)]
        y_centres = ([plate_height / 2.0] if num_rows == 1
                     else list(np.linspace(y_lo, y_hi, num_rows + 2)[1:-1]))

        all_positions, layout_ok = [], True
        for row_idx, (row_glands, y) in enumerate(zip(rows, y_centres)):
            stagger_offset = 10.0 if (num_rows > 1 and row_idx % 2 == 1) else 0.0
            row_pos, row_ok = _pack_row(row_glands, y, plate_width,
                                        x_lo, x_hi, gap=gap,
                                        stagger=stagger_offset)
            all_positions.extend(row_pos)
            layout_ok = layout_ok and row_ok

        best = all_positions
        if layout_ok and _check_no_overlaps(all_positions):
            return all_positions, True

    return best, False


if __name__ == "__main__":
    root = tk.Tk()
    app = GlandLayoutApp(root)
    root.mainloop()