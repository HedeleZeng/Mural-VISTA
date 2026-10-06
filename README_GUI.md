# Mural-VISTA GUI

Mural-VISTA is a PySide6 desktop interface 

## GUI workflow

1. Choose the input folder containing `<cell>_fused_green.ply` (or `_fused_gre.ply`)
   and optional `<cell>_fused_red.ply`.
2. Choose an output folder and click **Explore files**.
3. Enter the zero-based **Start number**.
4. Choose the **options** if needed:

   - **Expand the mural cell mesh**:
     Enter a non-negative distance in mesh units.
   - **Open the corresponding raw z-stack image for cell structure reference**:
     place `<cell>_fused.tif`, `.tiff`, `.ome.tif`, or `.ome.tiff` beside the mesh.

5. Select parameters, choose output formats, and click **Add selected**.
6. Click **Run analysis** and complete the interactive 3-D selections.

**Skip this cell** stops at the next safe stage boundary. The GUI tries to
close active PyVista windows; if a VMTK or 3D selection window stays visible,
close it to complete the skip.

**Skip and remove from file list** also removes the cell from the output
folder's `file_list.xlsx`. The next file exploration reads that saved list,
so the removed cell remains excluded.

## Selected exports

- **Raw data** writes `<parameter_id>_raw.json` in the cell's output folder.
- **Mean**, **Median**, and **Standard deviation** are written to the cell's
  `re_extract_properties.json`. This file contains only the summary formats
  selected in the GUI.
- A raw-only selection does not create `re_extract_properties.json`.
- Before writing the current selection, the GUI removes only Mural-VISTA's
  known parameter-result JSON files from a previous run in that cell's
  output folder. Unrelated user JSON files are preserved.

Preprocessed meshes, seed files, and derived PLY files are written under the
chosen output root. Per-cell JSON, pickle, VTU, and VTP results are written to
`<output folder>/<cell name>/`.

Operational `*_seeds.json` and `*_main_axis_seeds.json` files are preserved
because they cache interactive centerline selections. Meshes, pickle caches,
branch datasets, and `workspace.pkl` are also retained.

## This is a Windows application

A one-folder build is used because Qt, VTK, and VMTK contain many native DLLs.
Users of the built application do not need Python installed, but the complete
`dist\Mural-VISTA` folder must be distributed with the EXE.

