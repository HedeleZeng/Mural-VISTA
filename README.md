# Mural-VISTA
A tool for mural cell-vessel interaction assessment and multiscale single-cell topo-morphological analysis

# v1.0.0 (260726)

**Mural cell-Vessel Interaction and Single-cell Topo-morphology Analysis**

Source program in this release: **`Mural-VISTA_v1.0.0_260726.py`**

> Development note: this source file is named
> `260726_MuralVista_main_axis_extraction_refined.py` in the working project.
> The public v1.0.0 GitHub/Zenodo release should refer to it as
> `Mural-VISTA_v1.0.0_260726.py`.

Mural-VISTA analyzes the 3-D surface morphology of a mural cell and, when a
registered vessel mesh is supplied, the spatial relationship between the cell
and the vessel. The program extracts centerlines, separates branches and soma,
calculates morphology and topology measurements, and exports both numerical
results and derived meshes.

This source workflow is **interactive**. It opens 3D VMTK/PyVista windows in
which the user selects centerline endpoints, removes unwanted mesh regions, and
confirms the segmentation. It is not intended to run as an unattended or
headless batch process.

## Input

Set `DEFAULT_INPUT_DIR` near the beginning of the Python file to the folder
containing the meshes. The program searches that folder and its subfolders for
lowercase `.ply` files.

For each dataset, use these names:

```text
<dataset>_fused_green.ply    required mural-cell surface mesh
<dataset>_fused_red.ply      optional reference-vessel surface mesh
```

`<dataset>_fused_gre.ply` is also accepted for the mural-cell mesh. For
example:

```text
input_folder/
├── cell_01_fused_green.ply
├── cell_01_fused_red.ply
├── cell_02_fused_green.ply
└── cell_02_fused_red.ply
```

Input meshes should be triangulated surfaces. The green and red meshes for a
dataset must be in the same coordinate system and use the same units. Reported
lengths, areas, and volumes inherit the units of the input meshes.

The red vessel mesh is optional. Without it, Mural-VISTA still calculates cell
morphology, but vessel-coverage, projection, and branch-vessel measurements are
not calculated.

## Basic workflow

For every detected dataset, the program performs the following steps:

1. Reads the green/`gre` PLY mesh and converts it to an ASCII VTP surface for
   VMTK.
2. Lets the user remove mesh defects, then repairs, smooths, cleans, and
   subdivides the surface.
3. Lets the user select source and target points and extracts the VMTK
   centerline.
4. Builds a centerline-based tube and asks the user to accept the extraction or
   select the centerline points again.
5. Interactively separates the branches, main axis or primary process, and
   soma.
6. Calculates branch, branch-tree, soma, main-axis, and whole-cell
   measurements.
7. If a red vessel mesh is present, calculates cell-vessel coverage,
   projection, and angle measurements.
8. Saves numerical JSON files, derived meshes, centerline datasets, and caches
   that can be reused in a later run.


## Output

When the source program is run with its default configuration, results are
written into the input folder. The output root can also be set through
`AnalysisConfig.output_dir` when the program is called from another Python
driver.

The output root contains:

- `file_list.xlsx`, listing the detected datasets;
- VMTK-compatible and preprocessed meshes such as `<green_stem>.vtp` and
  `<green_stem>_clipped.ply`;
- saved centerline selections: `<green_stem>_seeds.json` and
  `<green_stem>_main_axis_seeds.json`;
- derived PLY surfaces for the branches, soma, and main-axis regions.

Each dataset also receives its own folder:

```text
<output>/<dataset>/
├── re_extract_properties.json       combined summary measurements
├── branches_properties.json         measurements for individual branches
├── cell_body_properties.json        soma measurements
├── main_axis_properties.json        main-axis measurements
├── branch_*.json                     branch and vessel-relation values
├── cl_tree_*.json                    branch-tree values
├── clipped_mesh.pkl                  reusable segmentation cache
├── workspace.pkl                     saved analysis workspace
├── branches_surface/                 per-branch surface files (.vtu)
├── branches_centerline/              centerline files (.vtu)
└── branches_tube/                    per-branch tube files (.vtp)
```

The reported quantities include branch length, diameter, curvature, torsion,
tortuosity, surface area and volume; branch-tree organization; soma volume,
area, sphericity, solidity and principal axes; main-axis geometry; whole-cell
shape and topology; and, when the red mesh is supplied, mural cell-vessel
spatial measurements.

On a repeated run, Mural-VISTA reuses compatible clipped meshes, selected seed
points, segmentation caches, and centerlines. Remove the relevant cache only
when that interactive stage needs to be repeated.

## Requirements

The project was tested with Python 3.10 and the environment recorded in
`envi_lib_list.txt`. The main non-standard dependencies are:

- VTK and PyVista;
- VMTK 1.5.0, using the modified `vmtkcenterlines.py` supplied with this
  release;
- NumPy, pandas, SciPy, NetworkX, trimesh, PyMeshFix, and GUDHI;
- openpyxl, used by pandas to write `file_list.xlsx`.

A graphical desktop session is required. Before starting a long analysis,
verify the environment with:

```bash
python -c "import vtk, pyvista, vmtk, numpy, pandas, scipy, networkx, trimesh, pymeshfix, gudhi, openpyxl"
```

## Modified VMTK function

Mural-VISTA uses a **modified** version of VMTK's `vmtkcenterlines.py`. 
(https://github.com/vmtk/vmtk/blob/master/vmtkScripts/vmtkcenterlines.py)
The modification keeps source seeds visually distinguishable while targets are
selected and exposes the selected source and target coordinates so that
Mural-VISTA can save and reuse them.

The matching modified file is distributed with this software on GitHub and in
the archived Zenodo release. 
Use the copy from the **same Mural-VISTA release** as the analysis script.

For source use:

1. Install VMTK in the Python environment.
2. Locate its package folder:

   ```bash
   python -c "import pathlib, vmtk; print(pathlib.Path(vmtk.__file__).resolve().parent)"
   ```

3. Make a backup of the installed `vmtkcenterlines.py`.
4. Replace it with the modified `vmtkcenterlines.py` supplied in this release,
   keeping exactly the same filename.



## Run the source program

1. Activate the prepared Python environment.
2. Edit `DEFAULT_INPUT_DIR` in `Mural-VISTA_v1.0.0_260726.py`.
3. Start the program from a terminal:

   ```bash
   python Mural-VISTA_v1.0.0_260726.py
   ```

4. Keep the terminal open and complete each interactive 3-D step. Progress and
   the current dataset name are printed in the terminal.


## Ready-to-use Windows GUI

An associated 64-bit Windows GUI is also available as
`Mural-VISTA-GUI_v1.0.0_Windows_exe.zip`. It bundles Python and the required scientific
libraries, so users do not need to install Python or Conda.

To use it:

1. Download the ZIP from the Mural-VISTA GitHub release or Zenodo record.
2. Extract the **complete** ZIP.
3. Open the extracted `Mural-VISTA` folder and double-click
   `Mural-VISTA.exe`.

Keep `Mural-VISTA.exe` together with its `_internal` folder. The EXE should not
be copied or distributed by itself. The GUI provides folder browsing, dataset
discovery, progress display, and parameter/export selection, while the core
scientific workflow still opens interactive VMTK/PyVista windows.

The currently associated GUI uses a later GUI-adapted Mural-VISTA pipeline.
For an exactly reproducible analysis, record whether the v1.0.0 source or a
particular GUI release was used.

## Citation

If Mural-VISTA contributes to your work, **we would greatly appreciate a citation**.

Please cite:

1. The exact Mural-VISTA software version used.
2. The associated Mural-VISTA research article, when its citation is provided
   on the project page.

3. VMTK:

   Izzo, R., et al., 
   The Vascular Modeling Toolkit: A Python Library for the Analysis of Tubular Structures in Medical Images. 
   Journal of Open Source Software, 2018. 3(25): p. 745.
   DOI: 10.21105/joss.00745


## Project links

- GitHub repository or release: **[add GitHub URL]**
- Zenodo archive and DOI: **[add Zenodo URL or DOI]**

## License

Copyright © 2026 Hedele Zeng.

Except where otherwise noted, original code developed for this project is licensed under the BSD 3-Clause License.

This project uses and, where indicated, includes third-party software distributed under their respective licenses. 
Third-party components retain their original copyright and license terms and are not relicensed under the BSD 3-Clause License.

See THIRD_PARTY_LICENSES.md for details.

Some functionality of this project depends on GPL-licensed software, 
including PyMeshFix/MeshFix and the GPLv3 dependencies used by GUDHI AlphaComplex. 
Users redistributing combined or bundled versions of this software are responsible 
for complying with the applicable third-party license terms.
