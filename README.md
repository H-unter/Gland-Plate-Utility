## How to run

Head to `dist/main.exe` and run the executable. Simples.

If you're a nerd, you can also run `main.py` directly if you have Python and the required libraries installed.
To assist nerds who dont have the right packages (but DO have python), paste the following into the terminal:

```cmd
cd C:\Path\To\The\Gland\Tool\Folder
pip install -r requirements.txt
```


## How to Add Cables

There are two ways to add cables to the layout: using standard **Cable Specs** (which auto-calculate the physical diameter based on AS/NZS and IEC standards) or entering a **Manual OD** for non-standard cables.

### Method 1: The Cable Spec String
To auto-calculate a cable's overall diameter, type your cable specification using the following format:

> `[Quantity]x [Cores]C[+E] [Size]mm2 [Material] [Insulation]`

* **Quantity** *(Optional)*: Number of identical cables to add at once (e.g., `3x` or `12*`). Defaults to `1`.
* **Cores** *(Required)*: Number of active cores (e.g., `1C`, `3C`, `4C`).
* **Earth** *(Optional)*: Add `+E` if an earth core is bundled in the cable (e.g., `3C+E`).
* **Size** *(Required)*: Conductor cross-sectional area (e.g., `2.5mm2`, `35mm²`, `0.75mm`).
* **Material** *(Optional)*: `Cu` (Copper) or `Al` (Aluminium). Defaults to `Cu`.
* **Insulation** *(Optional)*: `X90`, `V90`, `XLPE`, or `PVC`. *(Note: This is used for generating the label; X90/V90 share the same standard thickness).*

**Examples of valid inputs:**
* `3x 3C+E 35mm2 Cu XLPE` *(Adds three fully-specified cables)*
* `1C 630mm2 Al` *(Single massive aluminium core)*
* `4C 2.5mm2` *(Simple multi-core, automatically defaults to Copper)*

---

### Method 2: Manual OD Entry
If you are using a specialised cable that doesn't follow standard circular power-cable geometry (e.g., Steel Wire Armoured (SWA) cables, VSD cables with split earths, or Comms/Data cables), use the manual override.

1. **Leave the Spec field blank.**
2. Enter the exact physical diameter in the **Manual OD (mm)** field.
3. Provide a descriptive name in the **Label** field (e.g., `"Cat6 Ethernet"` or `"16mm2 VSD"`).
4. Click **Add Cable**.