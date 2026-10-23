# -*- coding: utf-8 -*-
"""Lazy TIFF virtual-stack viewer used by the Mural-VISTA GUI.

TIFF pages are exposed through tifffile's Zarr adapter and a Dask array.  This
keeps the source file on disk and reads only the plane(s) requested by napari,
similar to Fiji's Virtual Stack.  The viewer deliberately disables Dask's
``distributed`` auto-discovery because the local Windows installation can fail
while importing its SSL transport even though no distributed client is used.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


APP_VIEWER_TITLE = "Mural-VISTA raw z-stack"
TARGET_AXES = "TCZYX"
CHANNEL_COLORMAPS = (
    "green",
    "magenta",
    "cyan",
    "yellow",
    "red",
    "blue",
)


def configure_local_dask_scheduler():
    """Force in-process threaded Dask without importing ``distributed``.

    Dask 2026.7 checks whether ``distributed`` is installed before resolving
    even the strings ``threads`` and ``synchronous``.  On the affected Windows
    environment that check imports Tornado, which reads the certificate store
    and raises ``ssl.SSLError``.  Supplying the scheduler callable avoids that
    path; marking distributed unavailable also protects reader code that passes
    a scheduler name internally.
    """

    import dask
    import dask.base
    from dask.threaded import get as threaded_get

    if hasattr(dask.base, "_DISTRIBUTED_AVAILABLE"):
        dask.base._DISTRIBUTED_AVAILABLE = False
    if hasattr(dask.base, "_DistributedClient"):
        dask.base._DistributedClient = None
    if hasattr(dask.base, "_get_distributed_client"):
        dask.base._get_distributed_client = None

    dask.config.set(
        scheduler=threaded_get,
        **{"optimization.fuse.active": False},
    )
    return threaded_get


def _normalize_axes(data, axes):
    """Return a five-dimensional lazy array in TCZYX order."""

    import dask.array as da

    axis_names = list(str(axes).upper())
    if len(axis_names) != data.ndim:
        raise ValueError(
            f"TIFF axes {axes!r} do not match array shape {data.shape}."
        )

    if "C" not in axis_names and "S" in axis_names:
        axis_names[axis_names.index("S")] = "C"
    if "Z" not in axis_names:
        for fallback_axis in ("Q", "I"):
            if fallback_axis in axis_names:
                axis_names[axis_names.index(fallback_axis)] = "Z"
                break

    # Ignore only singleton metadata axes.  A non-singleton unknown axis is
    # ambiguous and should be reported instead of silently displaying it wrong.
    for axis_index in range(len(axis_names) - 1, -1, -1):
        axis_name = axis_names[axis_index]
        if axis_name in TARGET_AXES:
            continue
        if data.shape[axis_index] != 1:
            raise ValueError(
                f"Unsupported non-singleton TIFF axis {axis_name!r} in "
                f"axes {axes!r}."
            )
        data = data.take(0, axis=axis_index)
        axis_names.pop(axis_index)

    for axis_name in TARGET_AXES:
        matching_indices = [
            index
            for index, candidate in enumerate(axis_names)
            if candidate == axis_name
        ]
        while len(matching_indices) > 1:
            removable_index = next(
                (
                    index
                    for index in matching_indices[1:]
                    if data.shape[index] == 1
                ),
                None,
            )
            if removable_index is None:
                raise ValueError(
                    f"TIFF axes {axes!r} contain repeated axis "
                    f"{axis_name!r}."
                )
            data = data.take(0, axis=removable_index)
            axis_names.pop(removable_index)
            matching_indices = [
                index
                for index, candidate in enumerate(axis_names)
                if candidate == axis_name
            ]

    for axis_name in TARGET_AXES:
        if axis_name not in axis_names:
            data = da.expand_dims(data, axis=data.ndim)
            axis_names.append(axis_name)

    transpose_order = [axis_names.index(name) for name in TARGET_AXES]
    return data.transpose(transpose_order)


def _rational_as_float(value):
    if isinstance(value, tuple) and len(value) == 2:
        numerator, denominator = value
        return float(numerator) / float(denominator)
    return float(value)


def _read_spacing_microns(tiff_file, series):
    """Read best-effort Z/Y/X spacing without loading image pixels."""

    imagej_metadata = tiff_file.imagej_metadata or {}
    unit_name = str(imagej_metadata.get("unit", "")).strip().lower()
    unit_factors = {
        "um": 1.0,
        "µm": 1.0,
        "micron": 1.0,
        "microns": 1.0,
        "micrometer": 1.0,
        "micrometers": 1.0,
        "nm": 0.001,
        "mm": 1000.0,
        "cm": 10000.0,
        "inch": 25400.0,
        "inches": 25400.0,
    }
    metadata_factor = unit_factors.get(unit_name, 1.0)
    z_spacing = float(imagej_metadata.get("spacing", 1.0)) * metadata_factor
    y_spacing = 1.0
    x_spacing = 1.0

    try:
        first_page = series.pages[0]
        resolution_unit = str(
            first_page.tags["ResolutionUnit"].value
        ).upper()
        if "INCH" in resolution_unit:
            resolution_factor = 25400.0
        elif "CENTIMETER" in resolution_unit or "CM" in resolution_unit:
            resolution_factor = 10000.0
        else:
            resolution_factor = metadata_factor

        x_resolution = _rational_as_float(
            first_page.tags["XResolution"].value
        )
        y_resolution = _rational_as_float(
            first_page.tags["YResolution"].value
        )
        if x_resolution > 0:
            x_spacing = resolution_factor / x_resolution
        if y_resolution > 0:
            y_spacing = resolution_factor / y_resolution
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        pass

    return (z_spacing, y_spacing, x_spacing)


def _read_contrast_limits(tiff_file, channel_count, dtype):
    imagej_metadata = tiff_file.imagej_metadata or {}
    ranges = imagej_metadata.get("Ranges")
    if ranges is not None and len(ranges) >= channel_count * 2:
        return [
            (float(ranges[index * 2]), float(ranges[index * 2 + 1]))
            for index in range(channel_count)
        ]

    import numpy as np

    if np.issubdtype(dtype, np.integer):
        dtype_info = np.iinfo(dtype)
        default_limits = (float(dtype_info.min), float(dtype_info.max))
    elif np.issubdtype(dtype, np.bool_):
        default_limits = (0.0, 1.0)
    else:
        default_limits = (0.0, 1.0)
    return [default_limits] * channel_count


@dataclass
class LazyTiffStack:
    file_path: Path
    data: Any
    original_axes: str
    spacing_zyx: tuple[float, float, float]
    contrast_limits: list[tuple[float, float]]
    tiff_file: Any
    zarr_store: Any

    @property
    def properties(self):
        time_count, channel_count, z_count, y_count, x_count = self.data.shape
        return {
            "file_name": self.file_path.name,
            "file_path": str(self.file_path),
            "source_axes": self.original_axes,
            "dimension_order": TARGET_AXES,
            "shape_tczyx": tuple(int(value) for value in self.data.shape),
            "chunks_tczyx": tuple(
                tuple(int(value) for value in axis_chunks)
                for axis_chunks in self.data.chunks
            ),
            "data_type": str(self.data.dtype),
            "time_points": int(time_count),
            "channels": int(channel_count),
            "z_slices": int(z_count),
            "image_height": int(y_count),
            "image_width": int(x_count),
            "pixel_spacing_zyx": self.spacing_zyx,
            "loading": "lazy TIFF/Zarr virtual stack",
        }

    def close(self):
        try:
            close_store = getattr(self.zarr_store, "close", None)
            if close_store is not None:
                close_store()
        finally:
            self.tiff_file.close()


def open_lazy_tiff_stack(file_path, series_index=0):
    """Open one TIFF series lazily and return a managed TCZYX stack."""

    configure_local_dask_scheduler()

    import dask.array as da
    import tifffile
    import zarr

    file_path = Path(file_path).resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"Raw z-stack not found: {file_path}")

    tiff_file = tifffile.TiffFile(file_path)
    zarr_store = None
    try:
        if not 0 <= series_index < len(tiff_file.series):
            raise IndexError(
                f"series_index must be between 0 and "
                f"{len(tiff_file.series) - 1}."
            )
        series = tiff_file.series[series_index]
        original_axes = str(series.axes)
        zarr_store = series.aszarr()
        zarr_array = zarr.open(zarr_store, mode="r")
        lazy_data = da.from_zarr(zarr_array)
        lazy_data = _normalize_axes(lazy_data, original_axes)
        spacing_zyx = _read_spacing_microns(tiff_file, series)
        contrast_limits = _read_contrast_limits(
            tiff_file,
            int(lazy_data.shape[1]),
            lazy_data.dtype,
        )
        return LazyTiffStack(
            file_path=file_path,
            data=lazy_data,
            original_axes=original_axes,
            spacing_zyx=spacing_zyx,
            contrast_limits=contrast_limits,
            tiff_file=tiff_file,
            zarr_store=zarr_store,
        )
    except Exception:
        if zarr_store is not None:
            close_store = getattr(zarr_store, "close", None)
            if close_store is not None:
                close_store()
        tiff_file.close()
        raise


class RawStackViewer:
    """Own one reusable napari window and its current lazy TIFF resources."""

    def __init__(self, viewer=None):
        self.viewer = viewer
        self.stack: Optional[LazyTiffStack] = None
        self.layers = []
        self._retired_stacks = []

    def _ensure_viewer(self):
        import napari

        if self.viewer is not None:
            try:
                qt_window = self.viewer.window._qt_window
                if not qt_window.isVisible():
                    qt_window.show()
                    qt_window.raise_()
                    qt_window.activateWindow()
                return self.viewer
            except RuntimeError:
                self.viewer = None

        self.viewer = napari.Viewer(
            title=APP_VIEWER_TITLE,
            ndisplay=3,
        )
        return self.viewer

    def _remove_layers(self):
        self._remove_layer_list(self.layers)
        self.layers = []

    def _remove_layer_list(self, layers):
        if self.viewer is None:
            return
        for layer in list(layers):
            try:
                self.viewer.layers.remove(layer)
            except (KeyError, ValueError, RuntimeError):
                pass

    def load(self, file_path):
        new_stack = open_lazy_tiff_stack(file_path)
        try:
            viewer = self._ensure_viewer()
        except Exception:
            new_stack.close()
            raise
        old_stack = self.stack
        old_layers = list(self.layers)
        new_layers = []

        try:
            time_count, channel_count, z_count, _, _ = new_stack.data.shape
            z_spacing, y_spacing, x_spacing = new_stack.spacing_zyx
            for channel_index in range(channel_count):
                if time_count > 1:
                    channel_data = new_stack.data[:, channel_index]
                    layer_scale = (1.0, z_spacing, y_spacing, x_spacing)
                else:
                    channel_data = new_stack.data[0, channel_index]
                    layer_scale = (z_spacing, y_spacing, x_spacing)

                if channel_index < len(old_layers) and any(
                    candidate is old_layers[channel_index] for candidate in viewer.layers
                ):
                    # Keep Qt layer controls and VisPy visuals alive. Repeatedly
                    # destroying/recreating them during a stack switch can
                    # trigger deferred native-widget deletion on Windows.
                    layer = old_layers[channel_index]
                    layer.data = channel_data
                    layer.scale = layer_scale
                    layer.contrast_limits = new_stack.contrast_limits[channel_index]
                    layer.metadata = new_stack.properties
                    layer.name = f"Channel {channel_index + 1}"
                    layer.visible = True
                else:
                    layer = viewer.add_image(
                        channel_data,
                        name=f"Channel {channel_index + 1}",
                        colormap=CHANNEL_COLORMAPS[
                            channel_index % len(CHANNEL_COLORMAPS)
                        ],
                        scale=layer_scale,
                        contrast_limits=new_stack.contrast_limits[channel_index],
                        blending="additive",
                        cache=True,
                        metadata=new_stack.properties,
                    )
                new_layers.append(layer)

            viewer.title = (
                f"{APP_VIEWER_TITLE} — {new_stack.file_path.name}"
            )
            viewer.dims.ndisplay = 3
            viewer.dims.axis_labels = (
                ("T", "Z", "Y", "X")
                if time_count > 1
                else ("Z", "Y", "X")
            )
            try:
                z_axis = 1 if time_count > 1 else 0
                viewer.dims.set_current_step(z_axis, int(z_count) // 2)
            except (AttributeError, IndexError, TypeError, ValueError):
                pass
            viewer.reset_view()
        except Exception:
            self._remove_layer_list(list({id(layer): layer for layer in old_layers + new_layers}.values()))
            self.layers = []
            self.stack = None
            self._retired_stacks.append(new_stack)
            if old_stack is not None:
                self._retired_stacks.append(old_stack)
            self.release_retired_stacks()
            raise

        # Retain unused controls as hidden, empty layers when channel counts
        # differ. This avoids the same native deferred-deletion crash while
        # releasing the previous file's data and GPU volume.
        import numpy as np
        unused_layers = old_layers[channel_count:]
        for layer in unused_layers:
            layer.visible = False
            layer.data = np.zeros((1, 1, 1), dtype=np.uint8)
            layer.metadata = {}
            layer.name = "Unused channel"
        self.layers = new_layers + unused_layers
        self.stack = new_stack
        if old_stack is not None:
            self._retired_stacks.append(old_stack)
        self.release_retired_stacks()
        return new_stack.properties

    def release_retired_stacks(self):
        """Never close a TIFF while napari's slice workers still read it."""
        if not self._retired_stacks:
            return
        slicer = getattr(self.viewer, "_layer_slicer", None)
        if slicer is not None:
            try:
                slicer.wait_until_idle(timeout=0)
            except TimeoutError:
                return
        for stack in self._retired_stacks:
            stack.close()
        self._retired_stacks.clear()

    def close(self, remove_layers=True):
        if remove_layers:
            self._remove_layers()
        slicer = getattr(self.viewer, "_layer_slicer", None)
        if slicer is not None:
            slicer.wait_until_idle()
        if self.stack is not None:
            self.stack.close()
            self.stack = None
        self.release_retired_stacks()


def _write_socket_message(socket, payload):
    encoded = (json.dumps(payload) + "\n").encode("utf-8")
    socket.write(encoded)
    socket.flush()


def run_ipc_viewer(server_name):
    """Run the persistent napari helper process connected to the GUI."""

    import faulthandler
    faulthandler.enable()

    os.environ.setdefault("QT_API", "pyside6")
    os.environ.setdefault("NAPARI_DISABLE_PLUGIN_AUTOLOAD", "1")
    numba_cache_dir = (
        Path(tempfile.gettempdir()) / "Mural-VISTA-numba-cache"
    )
    numba_cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("NUMBA_CACHE_DIR", str(numba_cache_dir))
    configure_local_dask_scheduler()

    import napari
    from qtpy.QtCore import QCoreApplication, QEvent, QObject, QTimer
    from qtpy.QtNetwork import QLocalSocket
    from qtpy.QtWidgets import QApplication

    viewer_manager = RawStackViewer()
    viewer_manager._ensure_viewer()
    application = QApplication.instance()
    application.setQuitOnLastWindowClosed(False)

    socket = QLocalSocket()
    receive_buffer = bytearray()

    def notify_window_closed():
        _write_socket_message(socket, {"status": "window_closed"})

    class WindowCloseHandler(QObject):
        """Hide without destroying Qt/VisPy or scheduling a delayed quit."""

        def eventFilter(self, watched, event):
            if event.type() == QEvent.Type.Close:
                event.ignore()
                watched.hide()
                notify_window_closed()
                return True
            return super().eventFilter(watched, event)

    qt_window = viewer_manager.viewer.window._qt_window
    close_handler = WindowCloseHandler(qt_window)
    qt_window.installEventFilter(close_handler)
    resource_timer = QTimer(qt_window)
    resource_timer.setInterval(500)
    resource_timer.timeout.connect(viewer_manager.release_retired_stacks)
    resource_timer.start()
    shutdown_started = False

    def shutdown_viewer():
        nonlocal shutdown_started
        if shutdown_started:
            return
        shutdown_started = True
        resource_timer.stop()
        qt_window.hide()
        qt_window.status_thread.terminate()
        qt_window.status_thread.wait()
        viewer_manager.viewer.window._qt_viewer.dims.stop()
        viewer_manager.viewer._layer_slicer.shutdown()
        viewer_manager.close(remove_layers=False)
        # This helper is read-only and owns no analysis outputs. Napari 0.5.5
        # with PySide6 on Windows can crash in native Qt/CRT teardown even
        # after Viewer.close() or os._exit(). After stopping readers and
        # closing TIFF handles, let the OS reclaim its native GUI resources.
        # Only an explicit shutdown/disconnect takes this path; runtime
        # failures retain their real exit code and are reported by the parent.
        _write_socket_message(socket, {"status": "shutdown_complete"})
        socket.waitForBytesWritten(250)
        sys.stdout.flush()
        sys.stderr.flush()
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel32.TerminateProcess.restype = wintypes.BOOL
            kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 0)
        os._exit(0)

    def handle_message(payload):
        action = payload.get("action")
        if action == "load":
            file_path = payload.get("path")
            try:
                properties = viewer_manager.load(file_path)
                _write_socket_message(
                    socket,
                    {
                        "status": "loaded",
                        "path": str(file_path),
                        "shape_tczyx": properties["shape_tczyx"],
                        "chunks_tczyx": properties["chunks_tczyx"],
                        "ndisplay": viewer_manager.viewer.dims.ndisplay,
                        "pid": os.getpid(),
                    },
                )
            except Exception:
                _write_socket_message(
                    socket,
                    {
                        "status": "error",
                        "path": str(file_path),
                        "message": traceback.format_exc(),
                    },
                )
        elif action == "close":
            shutdown_viewer()
        elif action == "show":
            viewer_manager._ensure_viewer()
        elif action == "close_window":
            qt_window.hide()
            notify_window_closed()

    def read_messages():
        receive_buffer.extend(bytes(socket.readAll()))
        while b"\n" in receive_buffer:
            line, _, remainder = receive_buffer.partition(b"\n")
            receive_buffer[:] = remainder
            if not line.strip():
                continue
            try:
                handle_message(json.loads(line.decode("utf-8")))
            except Exception:
                _write_socket_message(
                    socket,
                    {"status": "error", "message": traceback.format_exc()},
                )

    socket.connected.connect(
        lambda: _write_socket_message(socket, {"status": "ready"})
    )
    socket.readyRead.connect(read_messages)
    socket.disconnected.connect(shutdown_viewer)
    application.aboutToQuit.connect(shutdown_viewer)
    socket.connectToServer(str(server_name))

    napari.run()
    return 0


def explore_microscopy_volume(file_path, series_index=0):
    """Standalone compatibility entry point for exploring one lazy TIFF."""

    os.environ.setdefault("QT_API", "pyside6")
    configure_local_dask_scheduler()
    import napari

    viewer = napari.Viewer(title=APP_VIEWER_TITLE, ndisplay=3)
    manager = RawStackViewer(viewer)
    properties = manager.load(file_path)
    # Keep the TIFF and Zarr store alive for as long as the viewer lives.
    viewer._mural_vista_raw_stack_manager = manager
    return viewer, properties


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) >= 2 and argv[0] == "--ipc-server":
        return run_ipc_viewer(argv[1])
    if not argv:
        raise SystemExit(
            "Usage: napari_viewer_lazy.py <stack.tif> or "
            "--ipc-server <server-name>"
        )

    import napari

    explore_microscopy_volume(argv[0])
    napari.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
