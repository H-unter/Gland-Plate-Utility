# from pyxll import xl_func, plot
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle



def initialise_rectangle_plot(plate_width = 100, plate_height = 50) -> tuple[Figure, Axes]:
   """create a matplotlib figure containing the gland plate as a rectangle"""
   scale_factor = 0.1  # Adjust this to make the plot larger/smaller on screen
   fig, ax = plt.subplots(figsize=(plate_width * scale_factor, plate_height * scale_factor))
   gland_plate = Rectangle((0, 0), plate_width, plate_height, 
                           fill=True, color='lightblue', label='Gland Plate')
   ax.add_patch(gland_plate)
   ax.set_xlim(0, plate_width)
   ax.set_ylim(0, plate_height)
   ax.set_aspect('equal')
   ax.set_xlabel("Width (mm)")
   ax.set_ylabel("Height (mm)")
   ax.grid(True, linestyle='--', alpha=0.6)
   return fig, ax

def run_test():
   print("Hello World")
   fig, ax = initialise_rectangle_plot()
   plt.show()


if __name__ == "__main__":
   run_test()
