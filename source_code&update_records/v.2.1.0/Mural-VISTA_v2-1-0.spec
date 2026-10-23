# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

project_dir = Path(SPECPATH)/ "Mural-VISTA_v2" / "v2.1.0"
gui_name = "Mural-VISTA-GUI_v2-1-0_261023.py"
datas = []
binaries = []
hiddenimports = [
    "Mural-VISTA_v2-1-0_261023", "napari_viewer_lazy", "openpyxl",
    "napari_builtins", "napari_builtins.io", "napari_builtins.io._read",
    "napari_builtins.io._write", "napari_builtins._ndims_balls",
    "napari_builtins._skimage_data",
]
datas += collect_data_files("napari_builtins", include_py_files=False)
# README.txt and legacy image resources are required on a machine with no cache.
datas += collect_data_files("skimage", include_py_files=False)
for package_name in (
    "vmtk", "pyvista", "gudhi", "pymeshfix", "napari", "napari_svg",
    "vispy", "dask", "tifffile", "zarr", "numcodecs", "imagecodecs",
    "magicgui", "superqt", "npe2", "app_model",
):
    package_datas, package_binaries, package_hiddenimports = collect_all(package_name)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hiddenimports
hiddenimports += collect_submodules("vmtk")

a = Analysis(
    [str(project_dir / gui_name)],
    pathex=[str(project_dir)], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["distributed", "dask.distributed", "napari_console", "qtconsole",
              "PyQt5", "PyQt6", "PySide2", "IPython", "jupyter", "notebook"],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="Mural-VISTA",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[], name="Mural-VISTA")
