from dataclasses import dataclass, field
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle, Circle

@dataclass
class CableGland:
    cable_outer_diameter: float
    cable_outer_area: float = field(init=False)
    cable_clearance_radius: float
    cable_clearance_area: float = field(init=False) # Area of the outer circle including the inner cable area
    label: str = "Gland"

    def __post_init__(self):
        self.cable_outer_area = np.pi * (self.cable_outer_diameter / 2) ** 2
        self.cable_clearance_area = np.pi * (self.cable_outer_diameter / 2 + self.cable_clearance_radius) ** 2



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

def calculate_layout(plate_width: float, plate_height: float, glands: list[CableGland], edge_margin: float = 15.0):
    """
    Iterative row-based packing with edge margin, boundary, and overlap checks.
    edge_margin: minimum distance (mm) from the edge of any gland footprint to the plate edge.
    """

    sorted_glands = sorted(glands, key=lambda gland: (gland.cable_clearance_area), reverse=True)
    
    # Define the usable area based on the margin
    usable_width = plate_width - (2 * edge_margin)
    usable_height = plate_height - (2 * edge_margin)
    
    best_effort_positions = []
    
    is_no_useable_space = usable_width <= 0 or usable_height <= 0
    if is_no_useable_space:
        return best_effort_positions, False        

    for num_rows in range(1, 3): 
        current_positions = []
        rows = [[] for _ in range(num_rows)]
        for i, g in enumerate(sorted_glands):
            rows[i % num_rows].append(g)

        # Distribute rows vertically within the usable height
        # y_start starts at edge_margin, y_end ends at plate_height - edge_margin
        if num_rows == 1:
            v_spacing = [plate_height / 2] # Centerline
        else:
            v_spacing = np.linspace(edge_margin, plate_height - edge_margin, num_rows + 2)[1:-1]
        
        valid_layout = True
        
        for row_idx, row_glands in enumerate(rows):
            y = v_spacing[row_idx]
            gap = 5 
            
            row_footprint_width = sum((g.cable_outer_diameter + 2*g.cable_clearance_radius) for g in row_glands)
            row_footprint_width += (len(row_glands) - 1) * gap
            
            # Start position to center the row within the plate width
            current_left_edge = (plate_width - row_footprint_width) / 2
            
            if num_rows > 1 and row_idx % 2 == 1:
                shift = 10 
                current_left_edge += shift

            for g in row_glands:
                eff_r = (g.cable_outer_diameter / 2) + g.cable_clearance_radius
                center_x = current_left_edge + eff_r
                
                # CHECK BOUNDARY against the Edge Margin
                if (center_x + eff_r > plate_width - edge_margin or 
                    center_x - eff_r < edge_margin or 
                    y + eff_r > plate_height - edge_margin or 
                    y - eff_r < edge_margin):
                    valid_layout = False
                
                current_positions.append((center_x, y, g))
                current_left_edge += (eff_r * 2) + gap
        
        best_effort_positions = current_positions

        # Overlap check remains the same
        if valid_layout:
            for i in range(len(current_positions)):
                for j in range(i + 1, len(current_positions)):
                    x1, y1, g1 = current_positions[i]
                    x2, y2, g2 = current_positions[j]
                    r1 = g1.cable_outer_diameter/2 + g1.cable_clearance_radius
                    r2 = g2.cable_outer_diameter/2 + g2.cable_clearance_radius
                    if np.sqrt((x1-x2)**2 + (y1-y2)**2) < (r1 + r2):
                        valid_layout = False
                        break
                if not valid_layout: break

        if valid_layout:
            return current_positions, True

    return best_effort_positions, False

def plot_layout(ax: Axes, plate_width: float, plate_height: float, glands: list[CableGland], edge_margin: float = 15.0):
    layout, fits_perfectly = calculate_layout(plate_width, plate_height, glands, edge_margin)
    
    # Visualise the Margin Boundary for the user
    margin_rect = Rectangle((edge_margin, edge_margin), 
                            plate_width - 2*edge_margin, 
                            plate_height - 2*edge_margin,
                            fill=False, edgecolor='yellow', linestyle=':', alpha=0.4, label='Margin Limit')
    ax.add_patch(margin_rect)
    if not fits_perfectly:
        ax.set_title("LAYOUT ERROR: OVERLAP DETECTED", color='red', pad=20, weight='bold')
    else:
        ax.set_title(f"Gland Layout: {len(layout)} Cables Scheduled", pad=20)

    for i, (x, y, g) in enumerate(layout, start=1):
        cable_r = g.cable_outer_diameter / 2
        eff_r = cable_r + g.cable_clearance_radius
        
        # Determine color: Red if it's outside the boundary
        is_outside = (x + eff_r > plate_width or x - eff_r < 0 or 
                      y + eff_r > plate_height or y - eff_r < 0)
        
        cable_color = '#e74c3c' if is_outside else '#3498db' # Red if outside, Blue if inside
        
        # 1. Plot Clearance
        ax.add_patch(Circle((x, y), eff_r, fill=False, edgecolor='#7f8c8d', 
                            linestyle='--', linewidth=1, alpha=0.5))
        
        # 2. Plot Cable
        ax.add_patch(Circle((x, y), cable_r, color=cable_color, alpha=0.8, 
                            label=f"{i}: {g.label}", zorder=3))
        
        # 3. ID Number
        ax.text(x, y, str(i), color='white', weight='bold', ha='center', va='center', zorder=4)

    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), title="Cable ID & Type", prop={'size': 8})



def run_test():
    # Example Plate
    width, height = 150, 80
    
    # Example Glands (Diameter, Clearance, Label)
    glands = [
        CableGland(20, 5, "M32"), CableGland(20, 5, "M32"),
        CableGland(12, 4, "M20"), CableGland(12, 4, "M20"),
        CableGland(12, 4, "M20"), CableGland(8, 3, "M16"),
        CableGland(8, 3, "M16"), CableGland(8, 3, "M16"),
    ]
    
    fig, ax = initialise_rectangle_plot(width, height)
    plot_layout(ax, width, height, glands, edge_margin=0)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    run_test()