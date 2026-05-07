from dataclasses import dataclass
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, Circle

@dataclass
class CableGland:
    cable_outer_diameter: float
    cable_clearance_radius: float
    label: str = "Gland"

def initialise_rectangle_plot(plate_width=100, plate_height=50):
    """Initialises a rectangle plot with the given dimensions"""
    scale_factor = 0.05 
    fig, ax = plt.subplots(figsize=(plate_width * scale_factor, plate_height * scale_factor))
    
    # Dark background for professional look
    gland_plate = Rectangle((0, 0), plate_width, plate_height, 
                            fill=True, color="#0a1c20", edgecolor="#ff0000", linestyle='--', label='Plate Boundary')
    ax.add_patch(gland_plate)
    
    ax.set_xlim(-10, plate_width + 10) 
    ax.set_ylim(-10, plate_height + 10)
    ax.set_aspect('equal')
    ax.set_xlabel("Width (mm)")
    ax.set_ylabel("Height (mm)")
    ax.grid(True, linestyle=':', alpha=0.3)
    return fig, ax

def calculate_layout(plate_width: float, plate_height: float, glands: list[CableGland]):
    """Iterative row-based packing with explicit overlap and boundary checks."""
    # Sort glands by total effective size (Diameter + 2*Clearance)
    sorted_glands = sorted(glands, key=lambda g: (g.cable_outer_diameter/2 + g.cable_clearance_radius), reverse=True)
    rows_to_try = min(len(glands), 5)  
    # Try 1 row, then 2, etc.
    for num_rows in range(1, rows_to_try + 1): 
        positions = []
        rows = [[] for _ in range(num_rows)]
        
        # Distribute glands into rows
        for i, g in enumerate(sorted_glands):
            rows[i % num_rows].append(g)

        # Distribute rows vertically
        v_spacing = plate_height / (num_rows + 1)
        can_fit = True
        
        for row_idx, row_glands in enumerate(rows):
            y = (row_idx + 1) * v_spacing
            gap = 5  # mm gap between glands
            
            # Total width of the footprint of all glands in this row
            row_footprint_width = sum((g.cable_outer_diameter + 2*g.cable_clearance_radius) for g in row_glands)
            row_footprint_width += (len(row_glands) - 1) * gap
            
            # Start position to center the row
            current_left_edge = (plate_width - row_footprint_width) / 2
            
            # STAGGER: Shift even rows slightly to help with nesting
            if num_rows > 1 and row_idx % 2 == 1:
                # Only shift if there is enough space on the plate
                shift = 10 
                if current_left_edge + shift + row_footprint_width < plate_width:
                    current_left_edge += shift

            for g in row_glands:
                eff_r = (g.cable_outer_diameter / 2) + g.cable_clearance_radius
                center_x = current_left_edge + eff_r
                
                # Check Boundary (mm)
                if (center_x + eff_r > plate_width or center_x - eff_r < 0 or 
                    y + eff_r > plate_height or y - eff_r < 0):
                    can_fit = False
                    break
                
                positions.append((center_x, y, g))
                current_left_edge += (eff_r * 2) + gap
            
            if not can_fit: break
        
        # FINAL SAFETY: Check for any overlapping circles (Vertical or Diagonal)
        if can_fit:
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    x1, y1, g1 = positions[i]
                    x2, y2, g2 = positions[j]
                    r1 = g1.cable_outer_diameter/2 + g1.cable_clearance_radius
                    r2 = g2.cable_outer_diameter/2 + g2.cable_clearance_radius
                    dist = np.sqrt((x1-x2)**2 + (y1-y2)**2)
                    if dist < (r1 + r2):
                        can_fit = False # Overlap detected between rows
                        break
                if not can_fit: break

        if can_fit: return positions
    return None

def plot_layout(ax: Axes, plate_width: float, plate_height: float, glands: list[CableGland]):
    layout = calculate_layout(plate_width, plate_height, glands)
    
    if not layout:
        ax.text(plate_width/2, plate_height/2, "WILL NOT FIT\nIncrease Plate Size", 
                ha='center', va='center', color='red', weight='bold', fontsize=12)
        return

    seen_labels = set()

    for x, y, g in layout:
        cable_r = g.cable_outer_diameter / 2
        eff_r = cable_r + g.cable_clearance_radius
        
        label_text = f"{g.label} (Ø{g.cable_outer_diameter}mm)"
        
        # 1. Plot the Clearance/Gland Footprint (Dotted)
        clearance_circle = Circle((x, y), eff_r, fill=False, 
                                  edgecolor='#7f8c8d', linestyle='--', linewidth=1, alpha=0.5)
        ax.add_patch(clearance_circle)
        
        # 2. Plot the Actual Cable (Solid)
        plot_label = label_text if label_text not in seen_labels else None
        cable_circle = Circle((x, y), cable_r, color='#3498db', 
                              alpha=0.8, label=plot_label, zorder=3)
        ax.add_patch(cable_circle)
        
        seen_labels.add(label_text)

    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), title="Gland Sizes")
    ax.set_title(f"Gland Layout: {len(layout)} Cables", pad=20)

def run_test():
    # Example Plate
    width, height = 150, 100
    
    # Example Glands (Diameter, Clearance, Label)
    glands = [
        CableGland(20, 5, "M32"), CableGland(20, 5, "M32"),
        CableGland(12, 4, "M20"), CableGland(12, 4, "M20"),
        CableGland(12, 4, "M20"), CableGland(8, 3, "M16"),
        CableGland(8, 3, "M16"), CableGland(8, 3, "M16"),
    ]
    
    fig, ax = initialise_rectangle_plot(width, height)
    plot_layout(ax, width, height, glands)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    run_test()