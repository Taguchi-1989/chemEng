# CAD Drawing Pipeline Skill

## Overview
Generate technical drawings with dimensions from parametric 3D CAD models using a fully OSS headless pipeline.

## Tool Stack
| Tool | Purpose | License |
|------|---------|---------|
| CadQuery | 3D parametric modeling | Apache 2.0 |
| ezdxf | DXF generation with dimensions | MIT |
| matplotlib | DXF to PDF rendering | BSD |
| FreeCAD | Assembly, TechDraw (optional) | LGPL |

## Directory Structure
```
cad-training/gearbox/
├── params/                    # YAML design parameters
│   ├── gearbox.yaml          # Gear, shaft, housing dimensions
│   ├── fits.yaml             # Tolerance policy (H7/g6)
│   ├── bom.yaml              # Parts list with MISUMI part numbers
│   └── drawing_info.yaml     # Drawing metadata (title, date, author)
├── src/
│   ├── parts/                # CadQuery part generators
│   │   ├── housing.py
│   │   ├── shaft.py
│   │   └── drawing_export.py
│   └── assemble/             # Assembly and drawing scripts
│       ├── drawing_with_dims.py    # Main drawing generator
│       ├── drawing_pipeline.py     # Projection views
│       ├── freecad_assembly.FCMacro
│       └── techdraw_export.FCMacro
├── vendor/misumi/            # MISUMI CAD data (layout only)
└── out/                      # Generated outputs
    ├── step/                 # 3D STEP files
    ├── stl/                  # 3D STL files
    ├── drawings_dxf/         # DXF with dimensions
    └── drawings_pdf/         # PDF drawings (A4 Landscape)
```

## Commands

### Generate All (Parts + Drawings + BOM)
```bash
cd cad-training/gearbox
make all
```

### Generate Drawings Only
```bash
# With dimensions (recommended)
python src/assemble/drawing_with_dims.py

# Specific part
python src/assemble/drawing_with_dims.py --part housing

# Projection views only (no dimensions)
python src/assemble/drawing_pipeline.py --format all
```

### Generate Assembly
```bash
# Requires FreeCAD
freecadcmd src/assemble/freecad_assembly.FCMacro
```

## Workflow
1. **Edit Parameters**: Modify `params/*.yaml`
2. **Generate Parts**: Run `make parts` or part scripts with `--export`
3. **Generate Drawings**: Run `make drawings` or `drawing_with_dims.py`
4. **Review**: Open PDF/DXF files

## Key Design Decisions

### MISUMI CAD Data Usage
- Use for **layout/interference check only**
- Do NOT use as manufacturing Source of Truth
- Always refer to catalog specs for critical dimensions

### Tolerance Notation
- Bearing seats: H7 (hole), g6 (shaft)
- Defined in `fits.yaml`
- Applied in dimension text (e.g., "D26 H7")

### Drawing Format
- A4 Landscape (297x210mm)
- Title block: Part name, Drawing No., Material, Scale, Date
- Metadata loaded from `params/drawing_info.yaml`

## ezdxf Implementation Notes

### Layer Colors
**Important**: Avoid DXF color 7 (white/black auto) - it may render as white on white background.

```python
# Good - use explicit colors
doc.layers.add("GEOMETRY", color=250)  # Dark gray
doc.layers.add("DIMENSIONS", color=3)   # Green
doc.layers.add("CENTER", color=1)       # Red
doc.layers.add("FRAME", color=250)      # Dark gray

# Bad - color 7 may be invisible on white background
doc.layers.add("GEOMETRY", color=7)     # Don't use!
```

### Dimension Style Colors
Set dimension line colors explicitly (don't rely on BYBLOCK=0):

```python
dim_style = doc.dimstyles.duplicate_entry("Standard", "CUSTOM")
dim_style.dxf.dimtxt = 3.5      # Text height
dim_style.dxf.dimasz = 2.5      # Arrow size
dim_style.dxf.dimtih = 1        # Text inside horizontal
dim_style.dxf.dimtoh = 1        # Text outside horizontal
dim_style.dxf.dimclrd = 3       # Dimension line color (green)
dim_style.dxf.dimclre = 3       # Extension line color (green)
dim_style.dxf.dimclrt = 3       # Text color (green)
```

### PDF Export with matplotlib

**Important**: ezdxf's `draw_layout()` changes figure size. Restore it after drawing.

```python
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

# A4 Landscape in inches
fig_width = 297 / 25.4   # 11.69"
fig_height = 210 / 25.4  # 8.27"

fig = plt.figure(figsize=(fig_width, fig_height))
ax = fig.add_axes([0, 0, 1, 1])

# Draw DXF content
ctx = RenderContext(doc)
out = MatplotlibBackend(ax)
Frontend(ctx, out).draw_layout(msp)

# IMPORTANT: Restore figure size (ezdxf changes it!)
fig.set_size_inches(fig_width, fig_height)

# Set view limits
ax.set_xlim(0, 297)
ax.set_ylim(0, 210)
ax.autoscale(False)
ax.axis('off')

# Save PDF
fig.savefig(pdf_path, format='pdf')
```

## Extending

### Add New Part
1. Create `src/parts/newpart.py` with CadQuery model
2. Add drawing spec in `drawing_with_dims.py`:
```python
def get_newpart_drawing_spec(params: dict) -> DrawingSpec:
    meta = get_drawing_meta(params, "newpart")
    return DrawingSpec(
        name="newpart",
        meta=meta,
        geometry=[("rect", {...}), ("circle", {...})],
        dimensions=[Dimension("linear_h", p1, p2, offset=10)]
    )
```
3. Add to pipeline in `run_pipeline()`

### Add Dimension Types
Supported in ezdxf:
- `linear_h`: Horizontal dimension
- `linear_v`: Vertical dimension
- `diameter`: Diameter dimension with "D" prefix
- `radius`: Radius dimension (add to code)
- `angular`: Angular dimension (add to code)

## Troubleshooting

### Model/geometry not visible in PDF

- Check layer colors - avoid color 7
- Use color 250 (dark gray) for geometry layers

### Dimension lines not visible (only text shows)

- Set `dimclrd`, `dimclre` in dimension style
- Don't use 0 (BYBLOCK) - set explicit color

### PDF page size wrong (cropped)

- Call `fig.set_size_inches()` AFTER `draw_layout()`
- ezdxf changes figure size during rendering

### PDF orientation wrong (portrait instead of landscape)

- Ensure figsize is (11.69, 8.27) for A4 Landscape
- Check xlim/ylim are (0, 297) and (0, 210)
