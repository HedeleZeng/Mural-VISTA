# -*- coding: utf-8 -*-
"""
# First version created on Fri Apr 18 16:41:51 2025 by Hedele_Zeng (UTokyo) with help from ChatGPT 4.1

Sun Jul 26 2026 for v1.0.0 preprint release 

@author: Hedele_Zeng(UTokyo) with helps from ChatGPT
"""

# -*- coding: utf-8 -*-


import vtk, os, re, json, trimesh, pickle
import numpy 
import numpy as np
import pandas as pd
import networkx as nx
import pyvista as pv
import pymeshfix as mf
from vmtk import vmtkscripts

from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk
from math import pi
from scipy.spatial import ConvexHull, cKDTree
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from scipy.interpolate import BSpline

# DEFAULT_INPUT_DIR can be edited for a new batch. Runtime state is kept in
# AnalysisConfig and DatasetState, not module-level mutable variables.

DEFAULT_INPUT_DIR = Path(r"YOUR_FILE_FOLDER_ADDRESS")


pv.global_theme.notebook = False



@dataclass
class AnalysisConfig:
    input_dir: Path = field(default_factory=lambda: DEFAULT_INPUT_DIR)
    output_dir: Optional[Path] = None
    tube_radius_threshold: float = 3.0
    tube_number_of_sides: int = 50
    tube_radius_factor: float = 1.0
    centerline_resampling_length: float = 0.5
    centerline_simplify_voronoi: bool = True
    centerline_delaunay_tolerance: float = 1e-5
    centerline_cap_displacement: float = 0.1
    centerline_flip_normals: bool = False
    centerline_cost_function: str = "1/R"
    radius_array_name: str = "MaximumInscribedSphereRadius"
    segmentation_cache_name: str = "clipped_mesh.pkl"
    workspace_cache_name: str = "workspace.pkl"
    branch_surface_dir: str = "branches_surface"
    branch_centerline_dir: str = "branches_centerline"
    branch_tube_dir: str = "branches_tube"
    export_default_parameter_json: bool = True
    cancel_check: Optional[Callable[[], bool]] = field(default=None, repr=False)

    def __post_init__(self):
        self.input_dir = Path(self.input_dir)
        self.output_dir = (
            self.input_dir
            if self.output_dir is None
            else Path(self.output_dir)
        )


@dataclass
class DatasetState:
    dataset_name: str
    file_path: Path
    ref_path: Optional[Path] = None
    output_dir: Optional[Path] = None
    file_path_nosuffix: Path = field(init=False)
    output_file_path_nosuffix: Path = field(init=False)
    data_dir: Path = field(init=False)

    clipped_mesh: Any = None
    clipped_mesh_whole: Any = None
    original_mesh: Any = None
    cleaned: Any = None
    tube_mesh: Any = None
    branches: Any = None
    cell_body_mainAx: Any = None
    cell_body: Any = None
    cell_mainAx: Any = None
    cell_body_capped: Any = None

    merger: Any = None
    clipper: Any = None
    cellcenter: Any = None
    cl_trees: list = field(default_factory=list)
    cl_tree_max_branch_level: list = field(default_factory=list)
    cl_tree_max_tree_length: list = field(default_factory=list)
    cl_tree_aspect_ratio: list = field(default_factory=list)
    cl_tree_fractal_dimension: list = field(default_factory=list)
    cl_tree_anisotropy: list = field(default_factory=list)
    cl_tree_sinuosity: list = field(default_factory=list)
    cl_tree_straightness: list = field(default_factory=list)
    sources: np.ndarray = field(default_factory=lambda: np.empty((0, 3)))
    targets: np.ndarray = field(default_factory=lambda: np.empty((0, 3)))

    main_axis_merger: Any = None
    main_axis_centerline: Any = None
    main_axis_sources: np.ndarray = field(default_factory=lambda: np.empty((0, 3)))
    main_axis_targets: np.ndarray = field(default_factory=lambda: np.empty((0, 3)))
    main_axis_properties: dict = field(default_factory=dict)

    branches_properties: list = field(default_factory=list)
    branches_sf: list = field(default_factory=list)
    branches_cl: list = field(default_factory=list)
    branches_tb: list = field(default_factory=list)
    cell_body_properties: dict = field(default_factory=dict)

    overall_volume: Optional[float] = None
    overall_surface_area: Optional[float] = None
    cell_solidity: Optional[float] = None
    branch_solidity: Optional[float] = None
    compactness: Optional[float] = None
    chi: Optional[float] = None
    IAMC: Optional[float] = None
    W: Optional[float] = None
    W_per_area: Optional[float] = None

    branch_number: Optional[int] = None
    covered_area: Optional[float] = None
    total_length: Optional[float] = None
    tpl: dict = field(default_factory=dict)

    knots: Any = None
    P: Any = None
    k: Optional[int] = None
    u_new: Any = None
    vessel_curve: Any = None
    vessel_curve_tree: Any = None
    vessel_spline: Any = None
    vessel_spline_der: Any = None
    reference_vessel_mesh: Any = None
    covered_region: Any = None
    projection_curve_line: Any = None
    projection_line: Any = None
    projection_distances: Any = None

    branch_vessel_cl_angles: list = field(default_factory=list)
    branch_vessel_cl_angles_mean: list = field(default_factory=list)
    branch_vessel_cl_proj_lengths: list = field(default_factory=list)
    branch_vessel_cl_proj_angles: list = field(default_factory=list)

    re_extract_properties: dict = field(default_factory=dict)

    def __post_init__(self):
        self.file_path = Path(self.file_path)
        self.file_path_nosuffix = self.file_path.with_suffix("")
        if self.ref_path is not None:
            self.ref_path = Path(self.ref_path)
        self.output_dir = (
            self.file_path.parent
            if self.output_dir is None
            else Path(self.output_dir)
        )
        self.output_file_path_nosuffix = (
            self.output_dir / self.file_path.stem
        )
        self.data_dir = self.output_dir / str(self.dataset_name)

    @property
    def seed_file(self):
        return Path(str(self.output_file_path_nosuffix) + "_seeds.json")

    @property
    def main_axis_seed_file(self):
        return Path(
            str(self.output_file_path_nosuffix)
            + "_main_axis_seeds.json"
        )

# Custom JSON encoder to handle NumPy data types
class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        # use default for other types
        return super().default(obj)


class DatasetSkipped(Exception):
    """Stop the current dataset and continue with the next one."""


def raise_if_cancelled(config: AnalysisConfig):
    if config.cancel_check is not None and config.cancel_check():
        raise DatasetSkipped()


def _get_array_any(dataset, name):
    """Return a VTK/PyVista array from point data first, then cell data."""
    if hasattr(dataset, "GetPointData"):
        arr = dataset.GetPointData().GetArray(name)
        if arr is not None:
            return arr
    if hasattr(dataset, "GetCellData"):
        arr = dataset.GetCellData().GetArray(name)
        if arr is not None:
            return arr
    return None


def _safe_remove_actor(plotter, name):
    try:
        plotter.remove_actor(name)
    except Exception:
        pass


def _as_point_array(points):
    if points is None:
        return np.empty((0, 3))
    arr = np.asarray(points, dtype=float)
    if arr.size == 0:
        return np.empty((0, 3))
    return arr.reshape((-1, 3))


def delete_seed_file(seed_file):
    seed_file = Path(seed_file)
    if seed_file.exists():
        seed_file.unlink()
        print(f"Deleted seed cache: {seed_file.name}")


def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, cls=NpEncoder)


def _show_plotter_safe(plotter, context):
    try:
        plotter.show()
    except AttributeError as exc:
        print(f"Skipping {context} visualization because the plotter backend is unavailable: {exc}")


def reload_existing_segmentation_bundle(state: DatasetState, config: AnalysisConfig):
    """
    Reload the original cached segmentation bundle if present.
    Matches 260210 behavior and filename convention: clipped_mesh.pkl.
    """
    meta_file = state.data_dir / config.segmentation_cache_name
    if os.path.exists(meta_file):
        with open(meta_file, "rb") as f:
            bundle = pickle.load(f)
        state.cell_body_mainAx = bundle["cell_body_mainAxis"]
        state.cell_body = bundle["cell_body"]
        state.branches = bundle["branches"]
        print(f"Loaded existing segmentation bundle: {meta_file.name}")
        return True
    return False


def load_data(state: DatasetState, config: AnalysisConfig):
    """1. Loading data: read the input cell mesh and prepare the output directory."""
    state.output_dir.mkdir(parents=True, exist_ok=True)
    state.data_dir.mkdir(parents=True, exist_ok=True)
    for sub in (config.branch_surface_dir, config.branch_centerline_dir, config.branch_tube_dir):
        (state.data_dir / sub).mkdir(exist_ok=True)
    clipped_path = Path(
        str(state.output_file_path_nosuffix) + "_clipped.ply"
    )
    # If a preprocessed clipped mesh exists, load it; otherwise read original PLY and convert to VTP
    if clipped_path.exists():
        plyR = vtk.vtkPLYReader()
        plyR.SetFileName(str(clipped_path))
        plyR.Update()
        state.clipped_mesh_whole = plyR.GetOutput()
        print(f"Loaded existing clipped mesh for {state.file_path.name}")
    else:
        # Read original PLY
        plyR = vtk.vtkPLYReader()
        plyR.SetFileName(str(state.file_path))
        plyR.Update()
        # Write to ASCII VTP (for VMTK compatibility)
        writer = vtk.vtkXMLPolyDataWriter()
        writer.SetFileName(
            str(state.output_file_path_nosuffix) + ".vtp"
        )
        writer.SetInputConnection(plyR.GetOutputPort())
        writer.SetDataModeToAscii()
        writer.SetCompressorTypeToNone()
        writer.Write()
        assert os.path.exists(writer.GetFileName())
        # Load surface via VMTK
        surfR = vmtkscripts.vmtkSurfaceReader()
        surfR.InputFileName = writer.GetFileName()
        surfR.Execute()
        # Decimate surface to reduce mesh complexity
        dec = vmtkscripts.vmtkSurfaceDecimation()
        dec.Surface = surfR.Surface
        dec.TargetReduction = 0.4
        dec.Execute()
        # After decimation, set clipped_mesh for further processing
        state.clipped_mesh = pv.wrap(dec.Surface)


def data_pretreatment(state: DatasetState, config: AnalysisConfig):
    """2. Data pretreatment: Mesh decimation, initial error removal, and smoothing."""
    if state.clipped_mesh_whole is not None:
        # Already have preprocessed mesh, skip pretreatment steps
        print("Skipping pretreatment (mesh already clipped and smoothed).")
        return
    # Manual interactive clipping to remove mesh errors or fragments
    state.clipped_mesh = run_manual_clipping_ui(
        state.clipped_mesh,
        title="Remove mesh defects",
        instruction="R: Draw or redraw a rectangle selection as needed. Enter:Clip selected region \nU: undo last applied clip. C: restart this stage. \nClose when done.",
    )
    raise_if_cancelled(config)
    # Repair mesh and fill holes
    meshfix = mf.MeshFix(state.clipped_mesh.extract_surface())
    meshfix.repair(verbose=True)
    surface = meshfix.mesh
    # Compute normals for offsetting the surface
    surface_with_normals = surface.compute_normals(cell_normals=False, point_normals=True, auto_orient_normals=True)
    normals = np.array(surface_with_normals.point_normals)
    margin = 0.5
    # Offset surface outward by margin and smooth slightly
    points = np.array(surface.points)
    offset_points = points + normals * margin
    offset_surface = pv.PolyData(offset_points, surface.faces)
    offset_surface = offset_surface.smooth_taubin(n_iter=10, boundary_smoothing=False)
    # Clean the offset surface using PyTMesh
    tin = mf.PyTMesh()
    tin.load_array(offset_surface.points, offset_surface.faces.reshape((-1, 4))[:, 1:])
    tin.clean(max_iters=10, inner_loops=3)
    vclean, fclean = tin.return_arrays()
    triangles = np.empty((fclean.shape[0], 4), dtype=fclean.dtype)
    triangles[:, -3:] = fclean
    triangles[:, 0] = 3
    offset_surface = pv.PolyData(vclean, triangles)
    # Smooth the surface using VMTK (Taubin smoothing)
    smo = vmtkscripts.vmtkSurfaceSmoothing()
    smo.Surface = offset_surface.extract_surface()
    smo.PassBand = 0.1
    smo.NumberOfIterations = 10
    smo.Execute()
    pd = smo.Surface.GetPoints().GetData()
    pts = vtk_to_numpy(pd).reshape(-1, 3)
    print("Smoothed points:", pts.shape)
    # Subdivide surface (Loop subdivision) for a finer mesh
    subdivisionFilter = vmtkscripts.vmtkSurfaceSubdivision()
    subdivisionFilter.Surface = smo.Surface
    subdivisionFilter.Method = "loop"
    subdivisionFilter.Execute()
    # Save the processed mesh for future reuse
    clipped_path = Path(
        str(state.output_file_path_nosuffix) + "_clipped.ply"
    )
    pv.wrap(subdivisionFilter.Surface).save(
        clipped_path,
        binary=False,
        recompute_normals=True,
    )
    # Load the saved clipped mesh as vtkPolyData
    plyR = vtk.vtkPLYReader()
    plyR.SetFileName(str(clipped_path))
    plyR.Update()
    state.clipped_mesh_whole = plyR.GetOutput()
    # Visualize the original vs processed mesh
    p = pv.Plotter()
    p.add_mesh(pv.wrap(state.clipped_mesh_whole), opacity=0.5, color="cyan")
    p.add_mesh(pv.wrap(surface), opacity=0.3, color="magenta")
    p.show()


def run_manual_clipping_ui(mesh, title, instruction, centerline=None,
                           mesh_color="cyan", centerline_color="tomato"):
    """
    Reusable manual clipping widget.
    Return applies the current rectangle selection, U undoes one applied clip,
    C restarts the current stage, and closing accepts the current mesh.
    """
    if mesh is None:
        return None

    current_mesh = mesh.copy(deep=True) if hasattr(mesh, "copy") else mesh
    original_mesh = current_mesh.copy(deep=True) if hasattr(current_mesh, "copy") else current_mesh
    previous_mesh = {"value": None}
    plotter = pv.Plotter()
    message_name = "clip_message"

    def picked_cells_from_plotter():
        sel = getattr(plotter, "picked_cells", None)
        if sel is None:
            return None
        # To make sure the selected skeleton part would not be cut
        if isinstance(sel, pv.MultiBlock):
            for block in sel:
                if block is not None and getattr(block, "n_cells", 0) > 0:
                    return block
            return None
        # Only cut the mesh
        if isinstance(sel, (list, tuple)):
            for block in sel:
                if block is not None and getattr(block, "n_cells", 0) > 0 and not isinstance(block, pv.MultiBlock):
                    return block
            return None
        return sel if getattr(sel, "n_cells", 0) > 0 else None

    def selected_original_cell_ids(selected_cells):
        for name in ("orig_extract_id", "vtkOriginalCellIds"):
            if name in selected_cells.cell_data:
                return np.asarray(selected_cells.cell_data[name])
        return None

    def pick_callback(cell_selection):
        picked = picked_cells_from_plotter()
        count = getattr(picked, "n_cells", 0) if picked is not None else 0
        print(f"{count} cells have been selected")

    def redraw():
        _safe_remove_actor(plotter, "current")
        _safe_remove_actor(plotter, "current_cl")
        _safe_remove_actor(plotter, "picked")
        _safe_remove_actor(plotter, message_name)
        plotter.add_text(f"({title})\n{instruction}", name=message_name)
        plotter.add_mesh(current_mesh, name="current", color=mesh_color, opacity=0.5)
        if centerline is not None:
            plotter.add_mesh(
                pv.wrap(centerline),
                name="current_cl",
                color=centerline_color,
                line_width=2,
                pickable=False,
            )
        plotter.disable_picking()
        plotter.enable_cell_picking(
            callback=pick_callback,
            through=True,
            show_message=False,
            name="picked",
        )
        plotter.render()

    def apply_clip():
        nonlocal current_mesh
        selected_cells = picked_cells_from_plotter()
        if selected_cells is None or selected_cells.n_cells == 0:
            print("No cells selected!")
            return
        cell_ids = selected_original_cell_ids(selected_cells)
        if cell_ids is None or len(cell_ids) == 0:
            print("Selected cells do not contain original cell ids; please redraw the selection.")
            return
        previous_mesh["value"] = current_mesh.copy(deep=True) if hasattr(current_mesh, "copy") else current_mesh
        current_mesh = current_mesh.extract_cells(cell_ids, invert=True)
        redraw()

    def undo_clip():
        nonlocal current_mesh
        if previous_mesh["value"] is None:
            print("No applied clip to undo.")
            return
        current_mesh = previous_mesh["value"]
        previous_mesh["value"] = None
        print("Undid the last applied clip.")
        redraw()

    def restart_stage():
        nonlocal current_mesh
        current_mesh = original_mesh.copy(deep=True) if hasattr(original_mesh, "copy") else original_mesh
        previous_mesh["value"] = None
        print("Restarted this clipping stage.")
        redraw()

    redraw()
    plotter.add_key_event("Return", apply_clip)
    plotter.add_key_event("u", undo_clip)
    plotter.add_key_event("U", undo_clip)
    plotter.add_key_event("c", restart_stage)
    plotter.add_key_event("C", restart_stage)
    plotter.show()
    return current_mesh

def add_branch_geometry_to_centerlines(brancher, brc_geometry):
    """
    Copy branch geometry arrays from vmtkBranchGeometry.GeometryData back to
    brancher.Centerlines cell-data, mirroring the working 260210 pipeline.
    """
    geom = brc_geometry.GeometryData.GetPointData()
    print("PointData arrays: ",
          [geom.GetArrayName(i) for i in range(geom.GetNumberOfArrays())])

    lengths_np = vtk_to_numpy(geom.GetArray('Length'))
    curvatures_np = vtk_to_numpy(geom.GetArray('Curvature'))
    torsion_np = vtk_to_numpy(geom.GetArray('Torsion'))
    tortuosity_np = vtk_to_numpy(geom.GetArray('Tortuosity'))
    branch_ids_np = vtk_to_numpy(geom.GetArray('GroupIds'))

    length_map = dict(zip(branch_ids_np, lengths_np))
    curvatures_map = dict(zip(branch_ids_np, curvatures_np))
    torsion_map = dict(zip(branch_ids_np, torsion_np))
    tortuosity_map = dict(zip(branch_ids_np, tortuosity_np))

    groupIds_np = vtk_to_numpy(brancher.Centerlines.GetCellData().GetArray('GroupIds'))

    branch_lengths = vtk.vtkDoubleArray()
    branch_lengths.SetName('BranchLength')
    branch_lengths.SetNumberOfTuples(brancher.Centerlines.GetNumberOfCells())
    for cellId in range(brancher.Centerlines.GetNumberOfCells()):
        gid = groupIds_np[cellId]
        branch_lengths.SetValue(cellId, length_map.get(gid, 0.0))
    brancher.Centerlines.GetCellData().AddArray(branch_lengths)

    branch_curvatures = vtk.vtkDoubleArray()
    branch_curvatures.SetName('BranchCurvature')
    branch_curvatures.SetNumberOfTuples(brancher.Centerlines.GetNumberOfCells())
    for cellId in range(brancher.Centerlines.GetNumberOfCells()):
        gid = groupIds_np[cellId]
        branch_curvatures.SetValue(cellId, curvatures_map.get(gid, 0.0))
    brancher.Centerlines.GetCellData().AddArray(branch_curvatures)

    branch_torsions = vtk.vtkDoubleArray()
    branch_torsions.SetName('BranchTorsion')
    branch_torsions.SetNumberOfTuples(brancher.Centerlines.GetNumberOfCells())
    for cellId in range(brancher.Centerlines.GetNumberOfCells()):
        gid = groupIds_np[cellId]
        branch_torsions.SetValue(cellId, torsion_map.get(gid, 0.0))
    brancher.Centerlines.GetCellData().AddArray(branch_torsions)

    branch_tortuosities = vtk.vtkDoubleArray()
    branch_tortuosities.SetName('BranchTortuosity')
    branch_tortuosities.SetNumberOfTuples(brancher.Centerlines.GetNumberOfCells())
    for cellId in range(brancher.Centerlines.GetNumberOfCells()):
        gid = groupIds_np[cellId]
        branch_tortuosities.SetValue(cellId, tortuosity_map.get(gid, 0.0))
    brancher.Centerlines.GetCellData().AddArray(branch_tortuosities)

def _configure_centerline_script(cl, config: AnalysisConfig):
    cl.SimplifyVoronoi = config.centerline_simplify_voronoi
    cl.DelaunayTolerance = config.centerline_delaunay_tolerance
    cl.CapDisplacement = config.centerline_cap_displacement
    cl.FlipNormals = config.centerline_flip_normals
    cl.CostFunction = config.centerline_cost_function
    cl.RadiusArrayName = config.radius_array_name


def run_seeded_centerline(surface, seed_file, config: AnalysisConfig,
                          force_repick=False, require_single_pair=False):
    seed_file = Path(seed_file)

    def load_seed_points():
        if not seed_file.exists():
            return np.empty((0, 3)), np.empty((0, 3))
        with open(seed_file, "r") as f:
            data = json.load(f)
        return _as_point_array(data.get("sources", [])), _as_point_array(data.get("targets", []))

    def save_seed_points(sources, targets):
        seeds = {
            "sources": _as_point_array(sources).tolist(),
            "targets": _as_point_array(targets).tolist(),
        }
        with open(seed_file, "w") as f:
            json.dump(seeds, f, indent=2, cls=NpEncoder)

    def flatten_points(points):
        return [float(c) for pt in _as_point_array(points) for c in pt]

    if force_repick:
        delete_seed_file(seed_file)

    while True:
        raise_if_cancelled(config)
        sources, targets = load_seed_points()
        selector = "pointlist" if len(sources) != 0 and len(targets) != 0 else "pickpoint"

        if require_single_pair and selector == "pointlist" and (len(sources) != 1 or len(targets) != 1):
            print("Cached main-axis seeds are not exactly one start and one end point; please reselect.")
            delete_seed_file(seed_file)
            continue

        cl = vmtkscripts.vmtkCenterlines()
        cl.Surface = surface
        cl.SeedSelectorName = selector
        if selector == "pointlist":
            cl.SourcePoints = flatten_points(sources)
            cl.TargetPoints = flatten_points(targets)
        _configure_centerline_script(cl, config)
        cl.Execute()
        raise_if_cancelled(config)

        if selector == "pickpoint":
            sources = _as_point_array(cl.PickedSeedsSource)
            targets = _as_point_array(cl.PickedSeedsTarget)
            if require_single_pair and (len(sources) != 1 or len(targets) != 1):
                print("Please select exactly one start point and one end point for the main axis.")
                delete_seed_file(seed_file)
                continue
            save_seed_points(sources, targets)

        pd = cl.Centerlines.GetPointData()
        cd = cl.Centerlines.GetCellData()
        print("PointData arrays:", [pd.GetArrayName(i) for i in range(pd.GetNumberOfArrays())])
        print("CellData arrays:", [cd.GetArrayName(i) for i in range(cd.GetNumberOfArrays())])
        print(f"lines: {cl.Centerlines.GetNumberOfLines()}")
        print(f"pd: {pd.GetNumberOfArrays()}")
        return cl, sources, targets


def clean_centerlines(centerlines):
    cleaner = vtk.vtkCleanPolyData()
    cleaner.SetInputData(centerlines)
    cleaner.SetConvertLinesToPoints(False)
    cleaner.SetConvertPolysToLines(True)
    cleaner.Update()
    centerlines_clean = cleaner.GetOutput()

    idsToDelete = vtk.vtkIdList()
    for cid in range(centerlines_clean.GetNumberOfCells()):
        cell = centerlines_clean.GetCell(cid)
        if cell.GetNumberOfPoints() < 2:
            idsToDelete.InsertNextId(cid)
    for i in range(idsToDelete.GetNumberOfIds()):
        centerlines_clean.DeleteCell(idsToDelete.GetId(i))
    centerlines_clean.RemoveDeletedCells()
    return centerlines_clean


def postprocess_centerline(raw_centerlines, config: AnalysisConfig):

    centerlines_clean = clean_centerlines(raw_centerlines)

    resampler = vmtkscripts.vmtkCenterlineResampling()
    resampler.Centerlines = centerlines_clean
    resampler.Length = config.centerline_resampling_length
    resampler.Execute()

    types = set(centerlines_clean.GetCellType(i) for i in range(centerlines_clean.GetNumberOfCells()))
    print("Cell types:", types)

    

    # where the kernel death happened \ToT/
    # Happened in vtkvmtk.vtkvmtkCenterlineBranchExtractor() \ToT/
    # ERROR:root:Error while constructing cell map: Invalid cell size for lines.
    
    brancher = vmtkscripts.vmtkBranchExtractor()
    brancher.Centerlines = resampler.Centerlines
    brancher.Execute()
    

    merger = vmtkscripts.vmtkCenterlineMerge()
    merger.Centerlines = brancher.Centerlines
    merger.Execute()
    
    brc_geometry = vmtkscripts.vmtkBranchGeometry()
    brc_geometry.Centerlines = merger.Centerlines
    brc_geometry.Execute()

    add_branch_geometry_to_centerlines(merger, brc_geometry)


    renumber_centerline_tract_ids(merger.Centerlines)
    return merger


def renumber_centerline_tract_ids(centerlines):
    ctl_pd = centerlines.GetCellData()
    tract_arr = ctl_pd.GetArray("TractIds")
    if tract_arr is None:
        return
    branch_level_new = vtk_to_numpy(tract_arr)
    branch_level_new = np.array([int(round(x / 2 + 1)) for x in branch_level_new])
    ctl_pd.RemoveArray("TractIds")
    branch_level_new_vtk = numpy_to_vtk(branch_level_new)
    branch_level_new_vtk.SetName("TractIds")
    ctl_pd.AddArray(branch_level_new_vtk)
    ctl_pd.Modified()


def interactive_centerline_extraction(state: DatasetState, config: AnalysisConfig, force_repick=False):
    """3. Interactive centerline extraction: compute vessel centerline from cell mesh."""
    cl, state.sources, state.targets = run_seeded_centerline(
        state.clipped_mesh_whole,
        state.seed_file,
        config,
        force_repick=force_repick,
    )
        

# =============================================================================
#     p = pv.Plotter()
#     p.add_mesh(state.clipped_mesh_whole, opacity=0.3)
#     p.add_mesh(cl.Centerlines,  color="tomato", line_width= 4)
#     p.show() 
# =============================================================================

    state.merger = postprocess_centerline(cl.Centerlines, config)
    print("Centerline extraction complete.")


def tubular_mask_segmentation(state: DatasetState, config: AnalysisConfig):
    """4. Tubular mask segmentation: separate mesh regions within a tube around centerline."""
    state.original_mesh = pv.wrap(state.clipped_mesh_whole)
    tube = vtk.vtkTubeFilter()
    tube.SetInputData(state.merger.Centerlines)
    tube.SetNumberOfSides(config.tube_number_of_sides)
    tube.SetCapping(True)
    tube.SetVaryRadiusToVaryRadiusByAbsoluteScalar()
    tube.SetRadiusFactor(config.tube_radius_factor)
    tube.SetInputArrayToProcess(
        0, 0, 0,
        vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS,
        config.radius_array_name,
    )
    tube.Update()
    state.tube_mesh = pv.wrap(tube.GetOutput())

    impDist = vtk.vtkImplicitPolyDataDistance()
    impDist.SetInput(tube.GetOutput())
    pts = state.original_mesh.points
    distances = np.array([impDist.EvaluateFunction(pt) for pt in pts])
    state.original_mesh.point_data["DistanceToTube"] = distances

    far_pt_ids = np.where(distances > config.tube_radius_threshold)[0]
    faces = state.original_mesh.faces.reshape(-1, 4)
    cell_point_ids = faces[:, 1:]
    mask = np.isin(cell_point_ids, far_pt_ids)
    rows = np.any(mask, axis=1)
    cells_to_remove = np.nonzero(rows)[0]
    filtered = state.original_mesh.remove_cells(list(cells_to_remove), inplace=False)
    state.cleaned = filtered.clean(inplace=False)
    state.clipped_mesh = state.cleaned


def confirm_extraction(result_mesh, context_mesh, title,
                       result_color="cyan", context_color=None,
                       result_opacity=0.5, context_opacity=0.5,
                       result_line_width=5,
                       allow_surface_switch=False):
    decision = {"action": None}
    p = pv.Plotter()
    p.add_mesh(
        pv.wrap(result_mesh),
        opacity=result_opacity,
        color=result_color,
        line_width=result_line_width,
    )
    p.add_mesh(
        pv.wrap(context_mesh),
        opacity=context_opacity,
        color=context_color,
    )
    confirmation_text = (
        f"({title}).\n"
        "A or closing window: accept current start/end points.\n"
        "D: delete points and reselect."
    )
    if allow_surface_switch:
        confirmation_text += (
            "\nW: delete points, switch capped/uncapped mesh, and reselect."
        )
    p.add_text(
        confirmation_text,
        name="extraction_confirm_message",
    )


    def set_decision(action):
        decision["action"] = action
        
    p.add_key_event("a", lambda: set_decision("accept"))
    p.add_key_event("A", lambda: set_decision("accept"))
    p.add_key_event("d", lambda: set_decision("reselect"))
    p.add_key_event("D", lambda: set_decision("reselect"))
    if allow_surface_switch:
        p.add_key_event("w", lambda: set_decision("switch_surface"))
        p.add_key_event("W", lambda: set_decision("switch_surface"))
    # p.show(auto_close=False, interactive_update=True)
    p.show( interactive_update=True )
    try:
        while decision["action"] is None:
            p.update()

    except (RuntimeError, AttributeError):
        pass

         
    finally:
        if not getattr(p, "_closed", False):
            try:
                p.close()
            except (RuntimeError, AttributeError):
                pass
            
    action = "accept" if decision["action"] is None else decision["action"]
    
    print(f"Confirmation returned: {action.upper()}", flush=True)
    
    return action

def tubular_mask_segmentation_with_confirmation(state: DatasetState, config: AnalysisConfig):
    while True:
        raise_if_cancelled(config)
        tubular_mask_segmentation(state, config)
        action = confirm_extraction(
            state.tube_mesh,
            state.cleaned,
            "Centerline-derived tube segmentation check",
            context_color="yellow",
        )
        print(f"Tube segmentation confirmation: {action}", flush=True)
        raise_if_cancelled(config)
        
        if action == "accept":
            return
        
        interactive_centerline_extraction(state, config, force_repick=True)

def remove_selected_mesh_from_original(original_mesh, selected_mesh):
    if original_mesh is None or selected_mesh is None or selected_mesh.n_points == 0:
        return None
    tree = cKDTree(original_mesh.points)
    _, raw_ids = tree.query(selected_mesh.points, k=1, workers=-1)
    faces = original_mesh.faces.reshape((-1, 4))
    mesh_cell_point_ids = faces[:, 1:]
    mask = np.isin(mesh_cell_point_ids, raw_ids)
    rows = np.any(mask, axis=1)
    cells_to_remove = np.nonzero(rows)[0]
    filtered = original_mesh.remove_cells(list(cells_to_remove), inplace=False)
    return filtered.clean(inplace=False)


def calculate_cell_mainAx_mesh(state: DatasetState):
    if state.cell_body_mainAx is None or state.cell_body is None:
        return None
    main_axis_surface = pv.wrap(state.cell_body_mainAx).extract_surface()
    cell_body_surface = pv.wrap(state.cell_body).extract_surface()
    return remove_selected_mesh_from_original(main_axis_surface, cell_body_surface)


def manual_clipping_comfirm_branch(state: DatasetState, config: AnalysisConfig):
    """Manual clipping step 2: interactively cut off branch connections from near-vessel mesh."""
    state.clipped_mesh = run_manual_clipping_ui(
        state.clipped_mesh,
        title="Remove non-branch part",
        instruction="R: Draw or redraw a rectangle selection as needed. Enter:Clip selected region \nU: undo last applied clip. C: restart this stage. \nClose when done.",
        centerline=state.merger.Centerlines,
    )
    state.branches = state.clipped_mesh
    state.cell_body_mainAx = remove_selected_mesh_from_original(state.original_mesh, state.branches)


def manual_clipping_comfirm_main_axis(state: DatasetState, config: AnalysisConfig):
    """Manual clipping step 3: interactively cut off residual attachments from cell body main axis."""
    state.clipped_mesh = state.cell_body_mainAx
    state.clipped_mesh = run_manual_clipping_ui(
        state.clipped_mesh,
        title="Remove unwanted branch part",
        instruction="R: Draw or redraw a rectangle selection as needed. Enter:Clip selected region \nU: undo last applied clip. C: restart this stage. \nClose when done.",
        centerline=state.merger.Centerlines,
    )
    state.cell_body_mainAx = state.clipped_mesh


def manual_clipping_select_cell_body_region(state: DatasetState, config: AnalysisConfig):
    """Manual clipping step 4: confirm cell body region by selecting connected component(s)."""
    if state.clipped_mesh is None:
        state.cell_body_mainAx = None
        return
    conn = state.clipped_mesh.connectivity()
    region_ids = conn.cell_data['RegionId']
    selected_rids = set()
    p = pv.Plotter()
    p.add_mesh(state.clipped_mesh, opacity=1, color="cyan", pickable=True)
    p.add_text(
        "(Select the cell main axis/primary process)\n"
        "Use Right-click or press P to select the cell-body part.\n"
        "Close the window after selection",
        font_size=18,
        name="sel_message",
    )

    def select_callback(picked_point):
        cell_id = state.clipped_mesh.find_closest_cell(picked_point)
        rid = region_ids[cell_id]
        if rid not in selected_rids:
            selected_rids.add(rid)
            print(f"Region {rid} added. Selected regions: {selected_rids}")
        else:
            print(f"Region {rid} already selected; skipping.")
        mask = np.isin(region_ids, list(selected_rids))
        cells_to_keep = np.where(mask)[0]
        combined = conn.extract_cells(cells_to_keep)
        _safe_remove_actor(p, 'conn_regions')
        p.add_mesh(combined, color='red', name='conn_regions')
        p.render()

    p.enable_point_picking(callback=select_callback, show_point=True, picker="point", show_message=False, color="magenta")
    p.show()
    if selected_rids:
        mask = np.isin(region_ids, list(selected_rids))
        cells_to_keep = np.where(mask)[0]
        state.cell_body_mainAx = conn.extract_cells(cells_to_keep)
    else:
        state.cell_body_mainAx = None


def manual_clipping_comfirm_cell_body(state: DatasetState, config: AnalysisConfig):
    """Manual clipping step 5: final interactive clipping on isolated cell body (optional)."""
    state.clipped_mesh = state.cell_body_mainAx
    state.clipped_mesh = run_manual_clipping_ui(
        state.clipped_mesh,
        title="Only leave the soma region",
        instruction="R: Draw or redraw a rectangle selection as needed. Enter:Clip selected region \nU: undo last applied clip. C: restart this stage. \nClose when done.",
        centerline=state.merger.Centerlines,
    )
    state.cell_body = state.clipped_mesh
    state.cell_mainAx = calculate_cell_mainAx_mesh(state)
    
    p = pv.Plotter()
    p.add_mesh(pv.wrap(state.main_axis_centerline), color="cyan", line_width = 8 )
    p.add_mesh( state.clipped_mesh_whole, opacity=0.3 )
    p.show()

    
    p2 = pv.Plotter()
    p2.add_mesh(pv.wrap(state.main_axis_centerline), color="cyan", line_width = 8 )
    p2.add_mesh(pv.wrap(state.merger.Centerlines), color="tomato", line_width = 2 )
    p2.add_mesh(state.branches, opacity=0.5, color="yellow")
    p2.add_mesh(state.cell_mainAx, opacity=0.5, color="magenta")
    p2.add_mesh(state.cell_body, opacity=1, color="wheat")
    p2.show()


def calculate_main_axis_centerline_properties(centerlines):
    if centerlines is None or centerlines.GetNumberOfCells() == 0:
        return {}

    def centerline_cell_path_length(cell_id):
        cell = centerlines.GetCell(cell_id)
        if cell.GetNumberOfPoints() < 2:
            return 0.0
        length = 0.0
        for i in range(cell.GetNumberOfPoints() - 1):
            p0 = np.array(centerlines.GetPoint(cell.GetPointId(i)))
            p1 = np.array(centerlines.GetPoint(cell.GetPointId(i + 1)))
            length += float(np.linalg.norm(p1 - p0))
        return length

    def cell_data_value(array_name, cell_id):
        arr = centerlines.GetCellData().GetArray(array_name)
        if arr is None or cell_id >= arr.GetNumberOfTuples():
            return None
        return float(arr.GetValue(cell_id))

    group_arr = centerlines.GetCellData().GetArray("GroupIds")
    candidates = []
    for cell_id in range(centerlines.GetNumberOfCells()):
        cell = centerlines.GetCell(cell_id)
        if cell.GetNumberOfPoints() < 2:
            continue

        p0 = np.array(centerlines.GetPoint(cell.GetPointId(0)))
        pN = np.array(centerlines.GetPoint(cell.GetPointId(cell.GetNumberOfPoints() - 1)))
        chord = float(np.linalg.norm(pN - p0))
        length = cell_data_value("BranchLength", cell_id)
        if length is None or length <= 0:
            length = centerline_cell_path_length(cell_id)

        tortuosity = cell_data_value("BranchTortuosity", cell_id)
        if tortuosity is None and chord > 1e-12:
            tortuosity = length / chord

        centerline_id = int(group_arr.GetValue(cell_id)) if group_arr is not None else int(cell_id)
        candidates.append({
            "main_axis_centerlineId": centerline_id,
            "main_axis_length": length,
            "main_axis_curvature": cell_data_value("BranchCurvature", cell_id),
            "main_axis_torsion": cell_data_value("BranchTorsion", cell_id),
            "main_axis_tortuosity": tortuosity,
            "main_axis_start_point": p0.tolist(),
            "main_axis_end_point": pN.tolist(),
        })

    if not candidates:
        return {}

    selected = dict(
        max(
            candidates,
            key=lambda item: item.get("main_axis_length") or 0.0,
        )
    )
    selected["main_axis_centerline_count"] = len(candidates)
    if len(candidates) > 1:
        selected["main_axis_all_centerline_properties"] = candidates
    return selected


def get_main_axis_centerline_file(state: DatasetState, config: AnalysisConfig):
    return state.data_dir / config.branch_centerline_dir / "main_axis_centerline.vtu"


def reload_existing_main_axis_centerline(state: DatasetState, config: AnalysisConfig):
    main_axis_file = get_main_axis_centerline_file(state, config)
    if not main_axis_file.exists():
        return False
    state.main_axis_centerline = pv.read(main_axis_file)
    state.main_axis_properties = calculate_main_axis_centerline_properties(state.main_axis_centerline)
    print(f"Loaded existing main-axis centerline: {main_axis_file.name}")
    return True


def main_axis_extraction_with_confirmation(state: DatasetState, config: AnalysisConfig):
    """Extract and quantify the main-axis centerline after user confirmation."""
    if state.cell_body_mainAx is None:
        print("Skipping main-axis centerline extraction: no main-axis mesh is available.")
        state.main_axis_properties = {}
        state.main_axis_centerline = None
        return

    surface_uncapped = pv.wrap(state.cell_body_mainAx).extract_surface()
    meshfix = mf.MeshFix(surface_uncapped.copy())
    meshfix.repair(verbose=True)
    surface_capped = meshfix.mesh

# =============================================================================
#     surface_capped_with_normals = surface_capped.compute_normals(
#         cell_normals=False,
#         point_normals=True,
#         auto_orient_normals=True,
#     )
#     capped_normals = np.array(surface_capped_with_normals.point_normals)
#     capped_margin = 0.5
#     capped_points = np.array(surface_capped.points)
#     capped_offset_points = capped_points + capped_normals * capped_margin
#     surface_capped = pv.PolyData(capped_offset_points, surface_capped.faces)
#     surface_capped = surface_capped.smooth_taubin(
#         n_iter=10,
#         boundary_smoothing=False,
#     )
# =============================================================================

    surface = surface_capped
    using_capped_surface = True

    surface_whole = pv.wrap(state.clipped_mesh_whole).extract_surface()
    force_repick = False
    while True:
        raise_if_cancelled(config)
        cl, state.main_axis_sources, state.main_axis_targets = run_seeded_centerline(
            surface,
            state.main_axis_seed_file,
            config,
            force_repick=force_repick,
            require_single_pair=True,
        )

        surface_name = "capped" if using_capped_surface else "uncapped"
        action = confirm_extraction(
            cl.Centerlines,
            surface_whole,
            f"Main-axis centerline extraction check ({surface_name} mesh)",
            context_opacity=0.3,
            allow_surface_switch=True,
        )

        print(f"Main-axis extraction confirmation: {action}", flush=True)
        raise_if_cancelled(config)

        if action == "accept":
            break

        if action == "switch_surface":
            using_capped_surface = not using_capped_surface
            surface = surface_capped if using_capped_surface else surface_uncapped
            surface_name = "capped" if using_capped_surface else "uncapped"
            print(f"Switching main-axis extraction to the {surface_name} mesh.")

        force_repick = True

    state.main_axis_merger = postprocess_centerline(cl.Centerlines, config)
    state.main_axis_centerline = pv.wrap(
        state.main_axis_merger.Centerlines
    ).cast_to_unstructured_grid()
    state.main_axis_properties = calculate_main_axis_centerline_properties(
        state.main_axis_centerline
    )
    print("Main-axis centerline extraction complete.")


def branch_parameter_calculation(state: DatasetState, config: AnalysisConfig):
    """
    Compute the individual-branch and connected branch-tree parameters:
    - use branch GroupIds from the clipper output,
    - compute truncated-cone volume/area from centerline radii,
    - read branch geometry arrays back from centerline cell-data,
    - store start/end points,
    - prepare per-branch surface / centerline / tube datasets,
    - calculate the centerline-tree metrics.
    """
    # Remove small disconnected centerline fragments not connected to source
    centerlines = pv.wrap(state.merger.Centerlines)
    tract_ids = centerlines.cell_data["TractIds"]
    group_ids = centerlines.cell_data["GroupIds"]
    point_locator = centerlines.find_closest_point
    closest_point_ids = {
        int(point_locator(tuple(point)))
        for point in _as_point_array(state.sources)
    }
    bad_group_ids = {
        int(group_ids[cell_id])
        for cell_id in range(centerlines.n_cells)
        if tract_ids[cell_id] == 1
        and not any(
            point_id in closest_point_ids
            for point_id in centerlines.get_cell(cell_id).point_ids
        )
    }
    clean_centerlines = centerlines.extract_values(
        scalars="GroupIds",
        values=list(bad_group_ids),
        invert=True,
    )

    state.clipper = vmtkscripts.vmtkBranchClipper()
    state.clipper.Centerlines = clean_centerlines.extract_surface()
    state.clipper.Surface = state.branches.extract_surface()
    state.clipper.Execute()
    state.branch_number = state.clipper.Centerlines.GetNumberOfCells()

    state.cellcenter = vtk.vtkCellCenters()
    state.cellcenter.SetInputData(state.clipper.Centerlines)
    state.cellcenter.Update()

    clipper = state.clipper
    state.branches_sf = []
    state.branches_tb = []
    state.branches_cl = []
    state.branches_properties = []

    centerline_points = vtk_to_numpy(
        clipper.Centerlines.GetPoints().GetData()
    )
    surface_group_ids = _get_array_any(clipper.Surface, "GroupIds")
    region_ids = np.unique(vtk_to_numpy(surface_group_ids))
    centerline_group_ids = clipper.Centerlines.GetCellData().GetArray(
        "GroupIds"
    )
    radius_array = clipper.Centerlines.GetPointData().GetArray(
        config.radius_array_name
    )
    branch_length_array = clipper.Centerlines.GetCellData().GetArray(
        "BranchLength"
    )
    branch_curvature_array = clipper.Centerlines.GetCellData().GetArray(
        "BranchCurvature"
    )
    branch_torsion_array = clipper.Centerlines.GetCellData().GetArray(
        "BranchTorsion"
    )
    branch_tortuosity_array = clipper.Centerlines.GetCellData().GetArray(
        "BranchTortuosity"
    )
    branch_level_array = clipper.Centerlines.GetCellData().GetArray(
        "TractIds"
    )

    for region_id in region_ids:
        properties = {}
        volume_sum = 0.0
        area_sum = 0.0

        centerline_index = int(
            centerline_group_ids.LookupValue(float(region_id))
        )
        segment_centerline_cell = clipper.Centerlines.GetCell(centerline_index)
        properties["centerlineId"] = region_id

        point_count = segment_centerline_cell.GetNumberOfPoints()
        segment_radii = []
        radius_start = float(
            radius_array.GetValue(segment_centerline_cell.GetPointId(0))
        )
        radius_end = float(
            radius_array.GetValue(
                segment_centerline_cell.GetPointId(point_count - 1)
            )
        )

        for point_index in range(point_count - 1):
            point_id_0 = segment_centerline_cell.GetPointId(point_index)
            point_id_1 = segment_centerline_cell.GetPointId(point_index + 1)
            point_0 = np.array(clipper.Centerlines.GetPoint(point_id_0))
            point_1 = np.array(clipper.Centerlines.GetPoint(point_id_1))
            interval_length = np.linalg.norm(point_1 - point_0)

            radius_0 = float(radius_array.GetValue(point_id_0))
            radius_1 = float(radius_array.GetValue(point_id_1))
            segment_radii.append(radius_0)

            interval_volume = (
                np.pi
                * interval_length
                * (radius_0 ** 2 + radius_0 * radius_1 + radius_1 ** 2)
                / 3.0
            )
            slant_length = np.sqrt(
                (radius_1 - radius_0) ** 2 + interval_length ** 2
            )
            lateral_area = (
                np.pi * (radius_0 + radius_1) * slant_length
            )
            volume_sum += interval_volume
            area_sum += lateral_area

        segment_radii.append(radius_1)
        properties["branchdiameter_mean"] = np.mean(
            np.array(segment_radii)
        )
        properties["branchdiameter_std"] = np.std(
            np.array(segment_radii)
        )

        cap_area = np.pi * (radius_start ** 2 + radius_end ** 2)
        area_sum += cap_area
        properties["volume"] = volume_sum
        properties["area"] = area_sum
        properties["branchlength"] = branch_length_array.GetValue(
            centerline_index
        )
        properties["branchcurvature"] = branch_curvature_array.GetValue(
            centerline_index
        )
        properties["branchtorsion"] = branch_torsion_array.GetValue(
            centerline_index
        )
        properties["branchtortuosity"] = branch_tortuosity_array.GetValue(
            centerline_index
        )
        properties["tractIds"] = branch_level_array.GetValue(
            centerline_index
        )

        first_point_id = segment_centerline_cell.GetPointId(0)
        last_point_id = segment_centerline_cell.GetPointId(point_count - 1)
        properties["start point"] = centerline_points[first_point_id][:]
        properties["end point"] = centerline_points[last_point_id][:]

        segment_surface = pv.wrap(clipper.Surface).extract_values(
            values=region_id,
            scalars="GroupIds",
            split=False,
        )
        segment_centerline = pv.wrap(clipper.Centerlines).extract_values(
            values=region_id,
            scalars="GroupIds",
            split=False,
        )

        tube = vtk.vtkTubeFilter()
        tube.SetInputData(segment_centerline.extract_surface())
        tube.SetNumberOfSides(config.tube_number_of_sides)
        tube.SetCapping(True)
        tube.SetVaryRadiusToVaryRadiusByAbsoluteScalar()
        tube.SetRadiusFactor(config.tube_radius_factor)
        tube.SetInputArrayToProcess(
            0, 0, 0,
            vtk.vtkDataObject.FIELD_ASSOCIATION_POINTS,
            config.radius_array_name,
        )
        tube.Update()

        state.branches_sf.append(segment_surface)
        state.branches_cl.append(segment_centerline)
        state.branches_tb.append(pv.wrap(tube.GetOutput()))
        state.branches_properties.append(properties)

    # Compute centerline-tree metrics from the final branch centerlines
    connected_centerlines = pv.wrap(state.clipper.Centerlines).connectivity("all")
    tree_region_ids = np.unique(connected_centerlines.cell_data["RegionId"])
    state.cl_trees = []

    for region_id in tree_region_ids:
        tree = {}
        tree["centerline_tree_number"] = region_id
        tree_mesh = connected_centerlines.connectivity("specified", [region_id])
        tree["centerline_tree_content"] = tree_mesh
        tree["centerline_tree_maxbranchlevel"] = np.max(
            tree_mesh.cell_data["TractIds"]
        )

        tree_points = tree_mesh.points
        point_graph = nx.Graph()
        for cell_id in range(tree_mesh.n_cells):
            cell = tree_mesh.GetCell(cell_id)
            point_ids = cell.GetPointIds()
            for point_index in range(point_ids.GetNumberOfIds() - 1):
                point_id_0 = point_ids.GetId(point_index)
                point_id_1 = point_ids.GetId(point_index + 1)
                edge_length = float(
                    np.linalg.norm(
                        tree_points[point_id_0] - tree_points[point_id_1]
                    )
                )
                if not point_graph.has_edge(point_id_0, point_id_1):
                    point_graph.add_edge(
                        point_id_0,
                        point_id_1,
                        weight=edge_length,
                    )

        leaves = [node for node, degree in point_graph.degree() if degree == 1]
        start_node = leaves[0] if leaves else next(iter(point_graph.nodes))
        distances = nx.single_source_dijkstra_path_length(
            point_graph,
            start_node,
            weight="weight",
        )
        first_end_node = max(distances, key=distances.get)
        distances = nx.single_source_dijkstra_path_length(
            point_graph,
            first_end_node,
            weight="weight",
        )
        second_end_node = max(distances, key=distances.get)
        maximum_length = distances[second_end_node]
        first_end_point = tree_points[first_end_node]
        second_end_point = tree_points[second_end_node]
        tree["centerline_tree_maxlength"] = float(maximum_length)

        xmin, xmax, ymin, ymax, zmin, zmax = (
            tree_mesh.oriented_bounding_box().bounds
        )
        extents = np.array([xmax - xmin, ymax - ymin, zmax - zmin])
        aspect_ratio = (
            extents.max() / extents.min()
            if extents.min() > 0
            else np.nan
        )
        tree["centerline_tree_aspect_ratio"] = float(aspect_ratio)

        tree_diagonal = tree_mesh.length
        resampling_length = max(tree_diagonal / 4096, 1e-9)
        spline_filter = vtk.vtkSplineFilter()
        spline_filter.SetInputData(tree_mesh)
        spline_filter.SetSubdivideToLength()
        spline_filter.SetLength(float(resampling_length))
        spline_filter.Update()
        resampled_tree = pv.wrap(spline_filter.GetOutput())

        resampled_points = resampled_tree.points
        bounds = resampled_tree.bounds
        minimum_bounds = np.array([bounds[0], bounds[2], bounds[4]])
        maximum_bounds = np.array([bounds[1], bounds[3], bounds[5]])
        bounding_diagonal = np.linalg.norm(maximum_bounds - minimum_bounds)
        scales = (bounding_diagonal / 2.0) / (2.0 ** np.arange(8))
        log_inverse_scales = []
        log_box_counts = []
        for scale in scales:
            occupied_boxes = np.floor(
                (resampled_points - minimum_bounds) / scale
            ).astype(np.int64)
            box_count = np.unique(occupied_boxes, axis=0).shape[0]
            if box_count < 10:
                continue
            log_inverse_scales.append(np.log(1.0 / scale))
            log_box_counts.append(np.log(box_count))

        if len(log_inverse_scales) < 2:
            fractal_dimension = np.nan
        else:
            fractal_dimension = np.polyfit(
                np.asarray(log_inverse_scales),
                np.asarray(log_box_counts),
                1,
            )[0]
        tree["centerline_tree_fractal_dimension"] = (
            1 if fractal_dimension < 1 else fractal_dimension
        )

        centered_points = tree_points - tree_points.mean(axis=0)
        covariance = np.cov(centered_points, rowvar=False)
        eigenvalues, _ = np.linalg.eigh(covariance)
        eigenvalues = np.sort(eigenvalues)[::-1]
        eigenvalue_sum = eigenvalues.sum()
        anisotropy = float(
            (3.0 * (eigenvalues[0] / eigenvalue_sum) - 1.0) / 2.0
        )
        chord_length = np.linalg.norm(second_end_point - first_end_point)
        sinuosity = chord_length / maximum_length

        tree["centerline_tree_anisotropy"] = anisotropy
        tree["centerline_tree_sinuosity"] = sinuosity
        tree["centerline_tree_straightness"] = float(anisotropy * sinuosity)
        state.cl_trees.append(tree)

    state.cl_tree_max_branch_level = [
        tree["centerline_tree_maxbranchlevel"] for tree in state.cl_trees
    ]
    state.cl_tree_max_tree_length = [
        tree["centerline_tree_maxlength"] for tree in state.cl_trees
    ]
    state.cl_tree_aspect_ratio = [
        tree["centerline_tree_aspect_ratio"] for tree in state.cl_trees
    ]
    state.cl_tree_fractal_dimension = [
        tree["centerline_tree_fractal_dimension"] for tree in state.cl_trees
    ]
    state.cl_tree_anisotropy = [
        tree["centerline_tree_anisotropy"] for tree in state.cl_trees
    ]
    state.cl_tree_sinuosity = [
        tree["centerline_tree_sinuosity"] for tree in state.cl_trees
    ]
    state.cl_tree_straightness = [
        tree["centerline_tree_straightness"] for tree in state.cl_trees
    ]

def cell_body_parameter_calculation(state: DatasetState):
    """8. Cell body parameter calculation: compute geometric metrics for the cell body region."""
    input_surface = state.cell_body.extract_surface()
    # Cap all surface open boundaries 
    # Powerful method for holey vessel mesh
    meshfix = mf.MeshFix(input_surface)
    meshfix.repair(verbose=True)
    surface = meshfix.mesh
    # Compute volume and area for cell body (closed surface)
    mass_props = vtk.vtkMassProperties()
    mass_props.SetInputData(surface.triangulate())
    mass_props.Update()
    volume = mass_props.GetVolume()
    area = mass_props.GetSurfaceArea()
    properties = {}
    properties["volume"] = volume
    properties["area"] = area
    properties["sphericity"] = (np.pi**(1/3) * (6 * volume)**(2/3)) / area if area > 1e-6 else None
    # Compute equivalent diameter
    eq_diameter = (6 * volume / np.pi)**(1/3)
    properties["equivalent_diameter"] = eq_diameter
    # Compute convex hull volume and solidity
    try:
        hull = ConvexHull(surface.points)
        convex_vol = hull.volume
        properties["convex_hull_volume"] = convex_vol
        if convex_vol > 1e-6:
            properties["solidity"] = volume / convex_vol
        else:
            properties["solidity"] = None
    except Exception as e:
        properties["convex_hull_volume"] = None
        properties["solidity"] = None
    # Principal axes via covariance
    try:
        pts = surface.points - surface.points.mean(axis=0)
        cov = np.cov(pts, rowvar=False)
        evals, evecs = np.linalg.eigh(cov)
        idx = np.argsort(evals)[::-1]
        axis_lengths = 2*np.sqrt(evals[idx])  # principal axis lengths (2*sqrt(eigenvalues))
        properties["principal_axes_projection"] = axis_lengths.tolist()
        properties["principal_axes"] = evecs[:, idx]
        properties["centroid"] = surface.points.mean(axis=0)
    except Exception as e:
        properties["principal_axes"] = None
        properties["principal_axes_projection"] = None
        properties["centroid"] = None
        print("Principal axes computation failed:", e)
    state.cell_body_properties = properties
    state.cell_body_capped = surface

def whole_cell_parameter_calculation(state: DatasetState):
    """9. Whole cell parameter calculation: compute metrics for entire cell shape."""
    mesh = pv.wrap(state.clipped_mesh_whole)
    state.overall_volume = abs(float(mesh.volume))
    state.overall_surface_area = abs(float(mesh.area))

    point_mesh = trimesh.Trimesh(vertices=mesh.points, process=False)
    hull = point_mesh.convex_hull
    hull_volume = abs(float(hull.volume))
    state.cell_solidity = state.overall_volume / hull_volume
    
    hull_faces = np.column_stack((
            np.full(hull.faces.shape[0], 3, dtype=np.int64),
            hull.faces.astype(np.int64))).ravel()

    hull_mesh = pv.PolyData(hull.vertices,hull_faces).clean()
    
    
    from gudhi import AlphaComplex

    points = mesh.points
    
    # Estimate of mesh volume for branch solidity (Alpha Complex)
    sample_count = 5000
    first_indices = np.random.randint(
        0,
        points.shape[0],
        size=sample_count,
    )
    second_indices = np.random.randint(
        0,
        points.shape[0],
        size=sample_count,
    )
    pair_distances = np.linalg.norm(
        points[first_indices] - points[second_indices],
        axis=1,
    )
    alpha = np.quantile(pair_distances, 0.05)
    
    
    alpha_complex = AlphaComplex(points=points.tolist())
    simplex_tree = alpha_complex.create_simplex_tree(
        max_alpha_square=alpha ** 2
    )
    triangles = [
        simplex
        for simplex in simplex_tree.get_skeleton(2)
        if len(simplex[0]) == 3
    ]
    vertex_triplets = [triplet for triplet, _ in triangles]
    faces = np.hstack([
        np.array([3, *triplet], dtype=np.int64)
        for triplet in vertex_triplets
    ])
    alpha_mesh = pv.PolyData(points, faces)
    alpha_mesh.clean()

# =============================================================================
#     # Estimate volume via Monte Carlo
#     bounds = alpha_mesh.bounds
#     bounding_box_volume = (
#         (bounds[1] - bounds[0])
#         * (bounds[3] - bounds[2])
#         * (bounds[5] - bounds[4])
#     )
#     monte_carlo_sample_count = 5000
#     monte_carlo_points = (
#         np.random.rand(monte_carlo_sample_count, 3)
#         * (
#             np.array(bounds)[1::2]
#             - np.array(bounds)[::2]
#         )
#         + np.array(bounds)[::2]
#     )
# 
#     alpha_trimesh = trimesh.Trimesh(
#         vertices=points,
#         faces=vertex_triplets,
#         process=False,
#     )
#     
# 
#     inside_mask = (
#         trimesh.proximity.signed_distance(
#             alpha_trimesh,
#             monte_carlo_points,
#         )> 0
#     )
#     
#     estimated_volume = (
#         inside_mask.sum() / monte_carlo_sample_count
#     ) * bounding_box_volume
# =============================================================================
    # Estimate volume via tetrahedron sum
    
    tetrahedra = np.asarray( [ simplex for simplex, _ in simplex_tree.get_skeleton(3) if len(simplex) == 4 ]) 
    coordinates = points[tetrahedra] 
    
    # For each tetrahedron:
    # V = |det(p1-p0, p2-p0, p3-p0)| / 6 
    
    edge_matrices = coordinates[:, 1:, :] - coordinates[:, :1, :] 
    individual_volumes = np.abs(np.linalg.det(edge_matrices)) / 6.0
    estimated_volume = individual_volumes.sum()
    
 
    state.branch_solidity = float(mesh.volume / estimated_volume)
    
# =============================================================================
#     p = pv.Plotter()
#     p.add_mesh(mesh, color = "tomato", opacity = .5)
#     p.add_mesh(alpha_mesh, color="cyan", opacity=.1)
#     p.show()
#     
#     
#     p = pv.Plotter()
#     p.add_mesh(mesh, color = "tomato", opacity = .5)
#     p.add_mesh(hull_mesh, color="orange", opacity=.3)
#     p.show()
# 
# 
# =============================================================================
    
    print(f"Estimated volume = {estimated_volume:.3f} (units^3)")
    print(f"Cell Solidity = {state.cell_solidity:.3f}")
    print(f"Branch Solidity = {state.branch_solidity:.3f}")

    state.compactness = 36 * pi * (mesh.volume ** 2) / mesh.area ** 3
    state.chi = mesh.n_points - mesh.extract_all_edges().n_cells + mesh.n_cells

    mean_curvature = mesh.curvature(curv_type="mean")
    cell_areas = mesh.compute_cell_sizes(
        length=False,
        area=True,
        volume=False,
    ).cell_data["Area"]
    vertex_areas = np.zeros(mesh.n_points)
    cells = mesh.faces.reshape((-1, 4))[:, 1:]
    for triangle, triangle_area in zip(cells, cell_areas):
        vertex_areas[triangle] += triangle_area / 3.0
    state.IAMC = float(np.sum(np.abs(mean_curvature) * vertex_areas))
    state.W = float(np.sum((mean_curvature ** 2) * vertex_areas))
    state.W_per_area = state.W / mesh.area



def whole_cell_vessel_relation(state: DatasetState):
    """10. Whole cell–vessel spatial relation quantification: vessel coverage area and cell projection length along vessel."""
    state.branch_number = state.clipper.Centerlines.GetNumberOfCells() if state.clipper else 0
    if state.ref_path is None:
        print("No reference mesh found; skipping vessel-relation calculations.")
        return

    cell_mesh = pv.wrap(state.clipped_mesh_whole)
    ref_mesh = pv.read(state.ref_path)
    ref_mesh.compute_normals(cell_normals=False)
    ref_mesh.compute_implicit_distance(cell_mesh, inplace=True)
    covered_region = ref_mesh.threshold(-0.3, scalars='implicit_distance', invert=True)
    state.reference_vessel_mesh = ref_mesh
    state.covered_region = covered_region
    state.covered_area = covered_region.area
    print(f"Overlap surface area: {state.covered_area}")

    ref_pts = ref_mesh.points
    ref_pts_normal = ref_mesh.point_normals
    centroid = ref_pts.mean(axis=0)
    centered = ref_pts - centroid
    Np = centered.shape[0]
    cov = (centered.T @ centered) / Np
    evals, evecs = np.linalg.eigh(cov)
    idx = np.argsort(evals)[::-1]
    evecs = evecs[:, idx]
    projections = ref_pts.dot(evecs[:, 0])
    idx_min = np.argmin(projections)
    idx_max = np.argmax(projections)
    p0 = ref_pts[idx_min]
    p3 = ref_pts[idx_max]

    num_samples = min(1000, ref_pts.shape[0], cell_mesh.n_points)
    idx_ref = np.random.choice(ref_pts.shape[0], size=num_samples, replace=False)
    ref_pts_down = ref_pts[idx_ref]
    ref_pts_normal_down = ref_pts_normal[idx_ref]
    idx_cell = np.random.choice(cell_mesh.n_points, size=num_samples, replace=False)
    cell_pts_down = cell_mesh.points[idx_cell]

    state.k = 2
    state.knots = np.array([0] * (state.k + 1) + [1] * (state.k + 1))
    c_eye = np.eye(4)
    bases = [BSpline(state.knots, c_eye[j], state.k) for j in range(4)]

    chord = p3 - p0
    raw_t = ((ref_pts_down - p0) @ chord) / np.dot(chord, chord)
    t_fit = np.clip(raw_t, 0, 1)
    Nmat = np.vstack([b(t_fit) for b in bases]).T
    state.P, residuals, rank, s = np.linalg.lstsq(Nmat, ref_pts_down, rcond=None)

    state.u_new = np.linspace(0, 1, 500)
    state.vessel_curve = np.vstack([BSpline(state.knots, state.P[:, d], state.k)(state.u_new) for d in range(3)]).T
    diffs = np.diff(state.vessel_curve, axis=0)
    arc_length = np.concatenate([[0], np.cumsum(np.linalg.norm(diffs, axis=1))])
    state.vessel_curve_tree = cKDTree(state.vessel_curve)
    idxs = state.vessel_curve_tree.query(cell_mesh.points,k=1)[1]
    proj_dists = arc_length[idxs]
    state.projection_distances = proj_dists
    state.projection_curve_line = pv.lines_from_points(state.vessel_curve, close=False)
    state.projection_line = pv.lines_from_points(state.vessel_curve[np.unique(idxs)], close=False)
    state.total_length = float(proj_dists.max() - proj_dists.min())
    print("Total projection length (B-spline):", state.total_length)

    state.tpl = {"B-spline curve projection": state.total_length}
    state.vessel_spline = BSpline(state.knots, state.P, state.k)
    state.vessel_spline_der = state.vessel_spline.derivative()

def branch_vessel_relation(state: DatasetState):
    """11. Branch–vessel spatial relation quantification: summary of branch metrics relative to vessel."""
    state.branch_vessel_cl_angles = []
    state.branch_vessel_cl_angles_mean = []
    state.branch_vessel_cl_proj_lengths = []
    state.branch_vessel_cl_proj_angles = []

    if not state.clipper:
        return

    n_regions_arr = _get_array_any(state.clipper.Surface, "GroupIds")
    n_regions = np.unique(vtk_to_numpy(n_regions_arr)) if n_regions_arr is not None else np.array([])
    cl = pv.wrap(state.clipper.Centerlines)

    for i in range(len(n_regions)):
        region_id = n_regions[i]
        segment_cl = cl.extract_values(values=region_id, scalars='GroupIds', split=False)
        if segment_cl.n_points < 2:
            state.branch_vessel_cl_angles.append([])
            state.branch_vessel_cl_angles_mean.append(None)
            state.branch_vessel_cl_proj_lengths.append(None)
            state.branch_vessel_cl_proj_angles.append(None)
            continue

        cl_pts = segment_cl.points
        p0 = cl_pts[0][:]
        pN = cl_pts[-1][:]
        line_vec = pN - p0
        line_norm = np.linalg.norm(line_vec)
        if line_norm < 1e-12:
            state.branch_vessel_cl_angles.append([])
            state.branch_vessel_cl_angles_mean.append(None)
            state.branch_vessel_cl_proj_lengths.append(0.0)
            state.branch_vessel_cl_proj_angles.append(0.0)
            continue
        line_unit = line_vec / line_norm

        idx = state.vessel_curve_tree.query(cl_pts)[1]
        u_proj = state.u_new[idx]
        tangents = state.vessel_spline_der(u_proj)
        norms = np.linalg.norm(tangents, axis=1, keepdims=True)
        tangents_unit = tangents / (norms + 1e-10)

        dots = np.einsum('ij,j->i', tangents_unit, line_unit)
        dots = np.clip(dots, -1.0, 1.0)
        angles = np.degrees(np.arccos(dots))
        state.branch_vessel_cl_angles.append(angles)
        state.branch_vessel_cl_angles_mean.append(np.mean(angles))

        idx0 = state.vessel_curve_tree.query(p0)[1]
        u0 = state.u_new[idx0]
        proj_pt = state.vessel_spline(u0)

        tan0 = state.vessel_spline_der(u0)
        n_plane = tan0 / (np.linalg.norm(tan0) + 1e-12)

        line_proj = line_vec - np.dot(line_vec, n_plane) * n_plane
        length_proj = np.linalg.norm(line_proj)
        if length_proj > 1e-12:
            line_proj = line_proj / length_proj
            line_proj_ref = np.array([0, 1, 0]) - np.dot(np.array([0, 1, 0]), n_plane) * n_plane
            ref_norm = np.linalg.norm(line_proj_ref)
            if ref_norm > 1e-12:
                line_proj_ref = line_proj_ref / ref_norm
                angle_proj = np.arctan2(
                    np.dot(n_plane, np.cross(line_proj, line_proj_ref)),
                    np.dot(line_proj, line_proj_ref)
                )
            else:
                angle_proj = 0.0
        else:
            angle_proj = 0.0

        state.branch_vessel_cl_proj_lengths.append(length_proj)
        state.branch_vessel_cl_proj_angles.append(angle_proj)


def _prepare_branch_tree_visualization_data(state: DatasetState):
    if state.clipper is None:
        return None, None

    clipper_centerlines = pv.wrap(state.clipper.Centerlines)
    if clipper_centerlines.n_cells == 0:
        return None, None

    connected_centerlines = clipper_centerlines.connectivity('all')
    tree_ids = np.asarray(connected_centerlines.cell_data["RegionId"]).astype(int)
    connected_centerlines.cell_data["BranchTreeNumber"] = tree_ids

    tree_summaries = state.cl_trees
    if not tree_summaries:
        return None, None

    return connected_centerlines, tree_summaries


def _plot_branch_tree_metric(connected_centerlines, tree_summaries, metric_key, title, decimals=None):
    if connected_centerlines is None or not tree_summaries:
        return

    def format_tree_metric_label(value):
        if value is None:
            return "NA"
        try:
            value = float(value)
        except (TypeError, ValueError):
            return str(value)
        if not np.isfinite(value):
            return "NA"
        return str(value) if decimals is None else f"{value:.{decimals}f}"

    label_points = []
    label_values = []
    for tree in tree_summaries:
        tree_mesh = pv.wrap(tree["centerline_tree_content"])
        if tree_mesh.n_points == 0:
            continue
        label_points.append(tree_mesh.points.mean(axis=0))
        label_values.append(format_tree_metric_label(tree.get(metric_key)))

    p = pv.Plotter()
    p.add_text(title, font_size=18)
    p.add_mesh(
        connected_centerlines,
        opacity=1,
        line_width=5,
        scalars="BranchTreeNumber",
        cmap="prism",
        categories=True,
        scalar_bar_args={"title": "Tree number"},
    )
    if label_points:
        label_mesh = pv.PolyData(np.asarray(label_points))
        p.add_point_labels(label_mesh, label_values,always_visible=True)
    _show_plotter_safe(p, title.lower())


def visualization_branches(state: DatasetState):
    if state.clipper is None or state.cellcenter is None:
        return

    def cellcenter_label_values(cellcenter_output, array_name, decimals=None):
        arr = cellcenter_output.GetPointData().GetArray(array_name)
        if arr is None:
            return None
        values = vtk_to_numpy(arr)
        if decimals is not None:
            values = np.around(values.astype(float), decimals)
        return [str(v) for v in values]

    clipper_surface = pv.wrap(state.clipper.Surface)
    clipper_centerlines = pv.wrap(state.clipper.Centerlines)
    center_pts = pv.wrap(state.cellcenter.GetOutput())

    p1 = pv.Plotter()
    p1.add_text("Branch level", font_size=18)
    p1.add_mesh(
        clipper_centerlines,
        opacity=1,
        line_width=5,
        scalars="TractIds",
        show_scalar_bar=True,
        scalar_bar_args={"title": "Branch level"},
    )
    tract_labels = cellcenter_label_values(state.cellcenter.GetOutput(), "TractIds")
    if tract_labels is not None:
        p1.add_point_labels(center_pts, tract_labels, always_visible=True)
    _show_plotter_safe(p1, "branch level")

    p2 = pv.Plotter()
    p2.add_text("Centerline group", font_size=18)
    # p2.add_mesh(
    #     clipper_surface,
    #     scalars="GroupIds",
    #     opacity=0.5,
    #     cmap="flag",
    #     categories=True,
    #     show_scalar_bar=False,
    # )
    p2.add_mesh(
        clipper_centerlines,
        opacity=1,
        line_width=5,
        scalars="GroupIds",
        show_scalar_bar=False,
    )
    centerline_label_array = "GroupIds" if cellcenter_label_values(state.cellcenter.GetOutput(), "GroupIds") is not None else "TractIds"
    centerline_labels = cellcenter_label_values(state.cellcenter.GetOutput(), centerline_label_array)
    if centerline_labels is not None:
        p2.add_point_labels(center_pts, centerline_labels,always_visible=True)
    _show_plotter_safe(p2, "centerline group")

    p3 = pv.Plotter()
    p3.add_text("Branch length (um)", font_size=18)
    # p3.add_mesh(
    #     clipper_surface,
    #     scalars="GroupIds",
    #     opacity=0.5,
    #     cmap="flag",
    #     categories=True,
    #     show_scalar_bar=False,
    # )
    p3.add_mesh(
        clipper_centerlines,
        opacity=1,
        line_width=5,
        scalars="GroupIds",
        show_scalar_bar=False,
    )
    branch_length_labels = cellcenter_label_values(state.cellcenter.GetOutput(), "BranchLength", decimals=2)
    if branch_length_labels is not None:
        p3.add_point_labels(center_pts, branch_length_labels,always_visible=True)
    _show_plotter_safe(p3, "branch length")


def visualization_branch_trees(state: DatasetState):
    connected_centerlines, tree_summaries = _prepare_branch_tree_visualization_data(state)
    _plot_branch_tree_metric(
        connected_centerlines,
        tree_summaries,
        "centerline_tree_maxbranchlevel",
        "Branch tree max branch level",
        decimals=0,
    )
    _plot_branch_tree_metric(
        connected_centerlines,
        tree_summaries,
        "centerline_tree_maxlength",
        "Branch tree max length (um)",
        decimals=2,
    )


def visualization_coverage_area(state: DatasetState):
    if state.covered_region is None or state.reference_vessel_mesh is None:
        return
    p = pv.Plotter()
    p.add_text("Coverage area", font_size=18)
    p.add_mesh(pv.wrap(state.reference_vessel_mesh), opacity=0.15, color="pink")
    p.add_mesh(pv.wrap(state.clipped_mesh_whole), opacity=0.25, color="wheat")
    p.add_mesh(pv.wrap(state.covered_region), opacity=0.8, color="green")
    _show_plotter_safe(p, "coverage area")


def visualization_projection_length(state: DatasetState):
    if state.projection_curve_line is None or state.projection_line is None or state.projection_distances is None:
        return
    cell_mesh = pv.wrap(state.clipped_mesh_whole).copy(deep=True)
    cell_mesh["proj_dist"] = state.projection_distances

    p = pv.Plotter()
    p.add_text("Projection length", font_size=18)
    # p.add_mesh(cell_mesh, opacity=0.5, scalars="proj_dist", cmap="viridis")
    # p.add_mesh(cell_mesh, opacity=0.8, color="green")
    p.add_mesh(cell_mesh, opacity=0.15, color="green")
    p.add_mesh(pv.wrap(state.projection_curve_line), color="yellow", line_width=4)
    p.add_mesh(pv.wrap(state.projection_line), color="magenta", line_width=6)
    p.add_mesh(pv.wrap(state. main_axis_centerline), color="cyan", line_width=6)
    if state.reference_vessel_mesh is not None:
        p.add_mesh(pv.wrap(state.reference_vessel_mesh), opacity=0.15, color="pink")
    _show_plotter_safe(p, "projection length")



def visualization_branch_vessel_angle(state: DatasetState):
    if state.clipper is None or state.cellcenter is None or not state.branch_vessel_cl_angles_mean:
        return

    n_regions_arr = _get_array_any(state.clipper.Surface, "GroupIds")
    if n_regions_arr is None:
        return
    n_regions = np.unique(vtk_to_numpy(n_regions_arr))
    angle_map = {int(region_id): angle for region_id, angle in zip(n_regions, state.branch_vessel_cl_angles_mean)}

    centerlines_vis = pv.wrap(state.clipper.Centerlines).copy(deep=True)
    group_arr = state.clipper.Centerlines.GetCellData().GetArray("GroupIds")
    cell_angles = np.array([
        angle_map.get(int(group_arr.GetValue(cell_id)), np.nan) if group_arr is not None else np.nan
        for cell_id in range(state.clipper.Centerlines.GetNumberOfCells())
    ], dtype=float)
    centerlines_vis.cell_data["BranchVesselAngleMean"] = cell_angles

    branch_labels = []
    for angle in state.branch_vessel_cl_angles_mean:
        if angle is None or not np.isfinite(angle):
            branch_labels.append("NA")
        else:
            branch_labels.append(f"{float(angle):.2f}")

    p = pv.Plotter()
    p.add_text("Branch-vessel center curve angle", font_size=18)
    p.add_mesh(
        centerlines_vis,
        scalars="BranchVesselAngleMean",
        line_width=5,
        scalar_bar_args={"title": "Angle (deg)"},
    )
    center_pts = pv.wrap(state.cellcenter.GetOutput())
    if len(branch_labels) == center_pts.n_points:
        p.add_point_labels(center_pts, branch_labels, always_visible = True)
    if state.projection_curve_line is not None:
        p.add_mesh(pv.wrap(state.projection_curve_line), color="yellow", line_width=4)
    if state.reference_vessel_mesh is not None:
        p.add_mesh(pv.wrap(state.reference_vessel_mesh), opacity=0.15, color="pink")
    p.add_mesh(pv.wrap(state.clipped_mesh_whole), opacity=0.15, color="green")
    _show_plotter_safe(p, "branch-vessel angle")


def run_visualizations(state: DatasetState):
    visualization_branches(state)
    visualization_branch_trees(state)
    if state.reference_vessel_mesh is not None:
        visualization_coverage_area(state)
        visualization_projection_length(state)
        visualization_branch_vessel_angle(state)


def export_branch_datasets(state: DatasetState, config: AnalysisConfig):
    export_specs = [
        (config.branch_surface_dir, state.branches_sf, ".vtu"),
        (config.branch_centerline_dir, state.branches_cl, ".vtu"),
        (config.branch_tube_dir, state.branches_tb, ".vtp"),
    ]
    for folder_name, grids, suffix in export_specs:
        grid_folder = state.data_dir / folder_name
        grid_folder.mkdir(exist_ok=True)
        for i, grid in enumerate(grids):
            grid.save(grid_folder / f"{folder_name}_{i}{suffix}")

    if state.main_axis_centerline is not None:
        pv.wrap(state.main_axis_centerline).save(get_main_axis_centerline_file(state, config))


def build_re_extract_properties(state: DatasetState):
    props = {}
    props["overall_volume"] = state.overall_volume
    props["overall_surface_area"] = state.overall_surface_area
    props["overall_projection_length"] = state.total_length
    props["overall_branch_number"] = state.branch_number
    props["overall_coverage_area"] = state.covered_area
    props["overall_cell_solidity"] = state.cell_solidity
    props["overall_branch_solidity"] = state.branch_solidity
    props["overall_compactness"] = state.compactness
    props["overall_Euler_characteristic"] = state.chi
    props["overall_IAMC"] = state.IAMC
    props["overall_Willmore_energy"] = state.W
    props["overall_Willmore_energy_normalized"] = state.W_per_area

    props["cell_body_volume"] = state.cell_body_properties.get("volume", None)
    props["cell_body_area"] = state.cell_body_properties.get("area", None)
    props["cell_body_solidity"] = state.cell_body_properties.get("solidity", None)
    props["cell_body_sphericity"] = state.cell_body_properties.get("sphericity", None)
    props["cell_body_principal_axes_projection"] = state.cell_body_properties.get("principal_axes_projection", None)

    branch_level_array = state.clipper.Centerlines.GetCellData().GetArray(
        "TractIds"
    )
    props["branch_mean_branch_level"] = float(
        np.mean(vtk_to_numpy(branch_level_array))
    )
    props["branch_mean_length"] = float(
        np.mean([
            properties["branchlength"]
            for properties in state.branches_properties
        ])
    )
    props["branch_mean_volume"] = float(
        np.mean([
            properties["volume"]
            for properties in state.branches_properties
        ])
    )
    props["branch_mean_diameter"] = float(
        np.mean([
            properties["branchdiameter_mean"]
            for properties in state.branches_properties
        ])
    )
    props["branch_mean_diameterSTD"] = float(
        np.mean([
            properties["branchdiameter_std"]
            for properties in state.branches_properties
        ])
    )
    props["branch_mean_curvature"] = float(
        np.mean([
            properties["branchcurvature"]
            for properties in state.branches_properties
        ])
    )
    props["branch_mean_torsion"] = float(
        np.mean([
            properties["branchtorsion"]
            for properties in state.branches_properties
        ])
    )
    props["branch_mean_tortuosity"] = float(
        np.mean([
            properties["branchtortuosity"]
            for properties in state.branches_properties
        ])
    )

    props["main_axis_length"] = state.main_axis_properties.get("main_axis_length")
    props["main_axis_curvature"] = state.main_axis_properties.get("main_axis_curvature")
    props["main_axis_torsion"] = state.main_axis_properties.get("main_axis_torsion")
    props["main_axis_tortuosity"] = state.main_axis_properties.get("main_axis_tortuosity")

    props["branch_tree_mean_branch_level"] = float(
        np.mean(state.cl_tree_max_branch_level)
    )
    props["branch_tree_mean_length"] = float(
        np.mean(state.cl_tree_max_tree_length)
    )
    props["branch_tree_mean_anisotropy"] = float(
        np.mean(state.cl_tree_anisotropy)
    )
    props["branch_tree_mean_sinuosity"] = float(
        np.mean(state.cl_tree_sinuosity)
    )
    props["branch_tree_mean_straightness"] = float(
        np.mean(state.cl_tree_straightness)
    )
    props["branch_tree_mean_fractal_dimension"] = float(
        np.mean(state.cl_tree_fractal_dimension)
    )
    props["branch_tree_max_fractal_dimension"] = float(
        np.max(state.cl_tree_fractal_dimension)
    )
    return props


def export_numerical_parameters(state: DatasetState, config: AnalysisConfig):
    """Save caches/meshes and, when enabled, legacy parameter JSON files."""
    bundle = {
        "cell_body": state.cell_body,
        "cell_body_mainAxis": state.cell_body_mainAx,
        "branches": state.branches,
    }
    with open(state.data_dir / config.segmentation_cache_name, "wb") as f:
        pickle.dump(bundle, f)

    if state.cell_mainAx is None:
        state.cell_mainAx = calculate_cell_mainAx_mesh(state)

    if config.export_default_parameter_json:
        write_json(
            state.data_dir / "branches_properties.json",
            state.branches_properties,
        )

        branch_lengths = [
            properties["branchlength"]
            for properties in state.branches_properties
        ]
        branch_tortuosities = [
            properties["branchtortuosity"]
            for properties in state.branches_properties
        ]
        write_json(state.data_dir / "branch_length.json", branch_lengths)
        write_json(
            state.data_dir / "branch_tortuosity.json",
            branch_tortuosities,
        )
        write_json(
            state.data_dir / "cell_body_properties.json",
            state.cell_body_properties,
        )
        write_json(
            state.data_dir / "cell_body_total_projection_length.json",
            state.tpl,
        )
        write_json(
            state.data_dir / "main_axis_properties.json",
            state.main_axis_properties,
        )

    if state.cell_body_mainAx is not None:
        pv.wrap(state.cell_body_mainAx).extract_surface().save(
            str(state.output_file_path_nosuffix)
            + "_cell_body_mainAx.ply",
            binary=False,
            recompute_normals=True,
        )
    if state.cell_body_capped is not None:
        pv.wrap(state.cell_body_capped).extract_surface().save(
            str(state.output_file_path_nosuffix) + "_cell_body.ply",
            binary=False,
            recompute_normals=True,
        )
    if state.cell_mainAx is not None:
        pv.wrap(state.cell_mainAx).extract_surface().save(
            str(state.output_file_path_nosuffix) + "_cell_mainAx.ply",
            binary=False,
            recompute_normals=True,
        )
    if state.branches is not None:
        pv.wrap(state.branches).extract_surface().save(
            str(state.output_file_path_nosuffix) + "_branches.ply",
            binary=False,
            recompute_normals=True,
        )

    export_branch_datasets(state, config)

    state.re_extract_properties = build_re_extract_properties(state)

    if config.export_default_parameter_json:
        write_json(
            state.data_dir / "branch_vessel_cl_angles.json",
            state.branch_vessel_cl_angles,
        )
        write_json(
            state.data_dir / "branch_vessel_cl_angles_mean.json",
            state.branch_vessel_cl_angles_mean,
        )
        write_json(
            state.data_dir / "branch_vessel_cl_proj_lengths.json",
            state.branch_vessel_cl_proj_lengths,
        )
        write_json(
            state.data_dir / "branch_vessel_cl_proj_angles.json",
            state.branch_vessel_cl_proj_angles,
        )

        write_json(
            state.data_dir / "cl_tree_max_branch_level.json",
            state.cl_tree_max_branch_level,
        )
        write_json(
            state.data_dir / "cl_tree_max_tree_length.json",
            state.cl_tree_max_tree_length,
        )
        write_json(
            state.data_dir / "cl_tree_aspect_ratio.json",
            state.cl_tree_aspect_ratio,
        )
        write_json(
            state.data_dir / "re_extract_properties.json",
            state.re_extract_properties,
        )

    print(f"Dataset {state.file_path.name} processed and saved.")


def discover_datasets(config: AnalysisConfig):
    ply_files = list(config.input_dir.rglob("*.ply"))
    pattern = re.compile(r"^(.+)_fused_(.+)\.ply$")
    datasets = {}
    for fpath in ply_files:
        match = pattern.match(fpath.name)
        if not match:
            continue
        dataset_tag, color_tag = match.group(1), match.group(2).lower()
        datasets.setdefault(dataset_tag, {})[color_tag] = fpath
    return sorted(datasets.items())


def process_dataset(dataset_name, files_dict, config: AnalysisConfig, do_visualization=False):
    try:
        file_path = files_dict["green"]
    except KeyError:
        file_path = files_dict["gre"]
    ref_path = files_dict.get("red")

    state = DatasetState(
        dataset_name=dataset_name,
        file_path=file_path,
        ref_path=ref_path,
        output_dir=config.output_dir,
    )
    raise_if_cancelled(config)
    load_data(state, config)
    raise_if_cancelled(config)
    data_pretreatment(state, config)
    raise_if_cancelled(config)
    interactive_centerline_extraction(state, config)
    raise_if_cancelled(config)

    segmentation_loaded = reload_existing_segmentation_bundle(state, config)
    
    if not segmentation_loaded:
        tubular_mask_segmentation_with_confirmation(state, config)
        raise_if_cancelled(config)
        manual_clipping_comfirm_branch(state, config)
        raise_if_cancelled(config)
        manual_clipping_comfirm_main_axis(state, config)
        raise_if_cancelled(config)
        if not reload_existing_main_axis_centerline(state, config):
            main_axis_extraction_with_confirmation(state, config)
            raise_if_cancelled(config)
        manual_clipping_select_cell_body_region(state, config)
        raise_if_cancelled(config)
        manual_clipping_comfirm_cell_body(state, config)
        raise_if_cancelled(config)
    elif not reload_existing_main_axis_centerline(state, config):
        main_axis_extraction_with_confirmation(state, config)
        raise_if_cancelled(config)

    branch_parameter_calculation(state, config)
    raise_if_cancelled(config)
    cell_body_parameter_calculation(state)
    raise_if_cancelled(config)
    whole_cell_parameter_calculation(state)
    raise_if_cancelled(config)
    whole_cell_vessel_relation(state)
    raise_if_cancelled(config)
    
    if state.reference_vessel_mesh is not None:
        branch_vessel_relation(state)
        raise_if_cancelled(config)
        
    export_numerical_parameters(state, config)
    
    if do_visualization:
        run_visualizations(state)
        
    return state


def save_workspace(state: DatasetState, config: AnalysisConfig):
    workspace = {
        name: value
        for name, value in vars(state).items()
        if name not in {
            "merger",
            "main_axis_merger",
            "clipper",
            "cellcenter",
        }
    }
    workspace["clipped_mesh_whole"] = pv.wrap(
        state.clipped_mesh_whole
    )
    workspace["centerlines"] = pv.wrap(state.merger.Centerlines)
    workspace["branch_centerlines"] = pv.wrap(
        state.clipper.Centerlines
    )
    workspace["branch_surface"] = pv.wrap(state.clipper.Surface)
    workspace["branch_cell_centers"] = pv.wrap(
        state.cellcenter.GetOutput()
    )

    with open(state.data_dir / config.workspace_cache_name, "wb") as f:
        pickle.dump(workspace, f)


def main(config: Optional[AnalysisConfig] = None):
    config = config or AnalysisConfig()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    do_visualization = False # Set True to show optional visualization windows.
    items = discover_datasets(config)
    starter = 0
    ender = 166

    if starter == 0:
        file_list = {i: items[i][0] for i in range(len(items))}
        pd.DataFrame({"Path": file_list}).to_excel(
            config.output_dir / "file_list.xlsx",
            index=False,
            index_label=False,
        )

    for counter, (name, files_dict) in enumerate(items[starter:], start=starter):
        print(f" Current data: No. {counter} {name}.")
        state = process_dataset(name, files_dict, config, do_visualization=do_visualization)
        save_workspace(state, config)


    return state 
# Run the main function when script is executed
if __name__ == '__main__':
   state = main()
