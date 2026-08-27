# Mural-VISTA GUI

Mural-VISTA is a PySide6 desktop interface for
`Mural-VISTA_v1.0.0_260726.py`.


## GUI workflow

1. Choose the input folder containing paired
   `<cell>_fused_green.ply` and optional `<cell>_fused_red.ply` files.
2. Choose a separate output folder.
3. Select **Explore files**. The GUI creates or reads
   `file_list.xlsx` in the output folder and shows the active cell count.
4. Enter the zero-based start number.
5. Check parameters in the left box and output formats in the middle box,
   then select **Add selected**.
6. Select **Run analysis**.

The progress area shows the current cell number, total cell count, and cell
name. The scientific pipeline still opens its normal interactive 3D windows
for seed picking, clipping, and confirmation.

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

The source Python script still writes its complete legacy set of parameter
JSON files. GUI runs suppress that complete set and export only the current
user selection.

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

