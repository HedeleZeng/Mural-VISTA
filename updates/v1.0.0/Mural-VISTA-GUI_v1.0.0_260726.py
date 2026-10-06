# -*- coding: utf-8 -*-
"""PySide6 desktop interface for the Mural-VISTA analysis pipeline."""

import importlib
import json
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path
from threading import Lock

import numpy as np
import pandas as pd
from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _ensure_standard_streams():
    """Provide valid streams when PyInstaller runs the GUI without a console."""
    if sys.stdin is None:
        sys.stdin = open(os.devnull, "r", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", buffering=1)
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", buffering=1)


_ensure_standard_streams()


APP_NAME = "Mural-VISTA"
APP_SUBTITLE = (
    "Mural cell-Vessel Interaction and Single-cell "
    "Topo-morphology Analysis"
)
ANALYSIS_MODULE_NAME = "Mural-VISTA_v1.0.0_260726"

PARAMETER_GROUPS = (
    (
        "Branch-level morphology features",
        (
            ("branch_length", "Branch length"),
            ("branch_curvature", "Branch curvature"),
            ("branch_torsion", "Branch torsion"),
            ("branch_tortuosity", "Branch tortuosity"),
            ("branch_volume", "Branch volume"),
            ("branch_area", "Branch area"),
            ("branch_diameter", "Branch diameter"),
            ("branch_level", "Branch level"),
        ),
    ),
    (
        "Branch tree-level morphology features",
        (
            ("branch_tree_max_length", "Branch tree max length"),
            ("branch_tree_aspect_ratio", "Branch tree aspect ratio"),
            (
                "branch_tree_fractal_dimension",
                "Branch tree fractal dimension",
            ),
            ("branch_tree_anisotropy", "Branch tree anisotropy"),
            ("branch_tree_sinuosity", "Branch tree sinuosity"),
            ("branch_tree_straightness", "Branch tree straightness"),
            ("branch_tree_max_level", "Branch tree max level"),
        ),
    ),
    (
        "Cell soma morphology features",
        (
            ("soma_volume", "Cell soma volume"),
            ("soma_surface_area", "Cell soma surface area"),
            ("soma_sphericity", "Cell soma sphericity"),
            ("soma_solidity", "Cell soma solidity"),
            (
                "soma_principal_axes_length",
                "Cell soma principal axes length",
            ),
        ),
    ),
    (
        "Whole-cell morphology features",
        (
            ("cell_volume", "Cell volume"),
            ("cell_surface_area", "Cell surface area"),
            ("cell_solidity", "Cell solidity"),
            ("cell_branch_solidity", "Cell branch solidity"),
            ("cell_compactness", "Cell compactness"),
            (
                "cell_euler_characteristic",
                "Cell Euler characteristic",
            ),
            (
                "cell_integral_absolute_mean_curvature",
                "Cell integral absolute mean curvature",
            ),
            ("cell_willmore_energy", "Cell Willmore energy"),
        ),
    ),
    (
        "Cell main-axis morphology features",
        (
            ("main_axis_length", "Main axis length"),
            ("main_axis_curvature", "Main axis curvature"),
            ("main_axis_torsion", "Main axis torsion"),
            ("main_axis_tortuosity", "Main axis tortuosity"),
        ),
    ),
    (
        "Mural cell-vessel spatial relations",
        (
            ("covered_vessel_area", "Covered vessel area"),
            (
                "vessel_center_curve_projection_length",
                "Vessel center curve projection length",
            ),
            (
                "projection_length_axis_length_ratio",
                "Projection length-axis length ratio",
            ),
            (
                "branch_vessel_center_curve_angle",
                "Branch-vessel center curve angle",
            ),
        ),
    ),
)

PARAMETER_LABELS = {
    parameter_id: label
    for _, parameters in PARAMETER_GROUPS
    for parameter_id, label in parameters
}

OUTPUT_FORMATS = (
    ("raw", "Raw data"),
    ("mean", "Mean"),
    ("median", "Median"),
    ("std", "Standard deviation"),
)

OUTPUT_FORMAT_LABELS = dict(OUTPUT_FORMATS)

DEFAULT_PARAMETER_JSON_FILENAMES = frozenset(
    {
        "branches_properties.json",
        "branch_length.json",
        "branch_tortuosity.json",
        "cell_body_properties.json",
        "cell_body_total_projection_length.json",
        "main_axis_properties.json",
        "branch_vessel_cl_angles.json",
        "branch_vessel_cl_angles_mean.json",
        "branch_vessel_cl_proj_lengths.json",
        "branch_vessel_cl_proj_angles.json",
        "cl_tree_max_branch_level.json",
        "cl_tree_max_tree_length.json",
        "cl_tree_aspect_ratio.json",
        "re_extract_properties.json",
    }
)

GENERATED_PARAMETER_JSON_FILENAMES = (
    DEFAULT_PARAMETER_JSON_FILENAMES
    | frozenset(
        f"{parameter_id}_raw.json"
        for parameter_id in PARAMETER_LABELS
    )
)


class NumpyJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def discover_datasets(input_dir):
    pattern = re.compile(r"^(.+)_fused_(green|gre|red)\.ply$", re.I)
    datasets = {}
    for file_path in Path(input_dir).rglob("*.ply"):
        match = pattern.match(file_path.name)
        if match is None:
            continue
        dataset_name = match.group(1)
        color_name = match.group(2).lower()
        datasets.setdefault(dataset_name, {})[color_name] = file_path
    return sorted(datasets.items())


def write_file_list(output_dir, datasets):
    rows = []
    for dataset_name, files in datasets:
        green_path = files.get("green", files.get("gre"))
        rows.append(
            {
                "Path": dataset_name,
                "Green file": str(green_path),
                "Red file": str(files.get("red", "")),
            }
        )
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_excel(
        output_dir / "file_list.xlsx",
        index=False,
    )


def load_or_create_file_list(input_dir, output_dir):
    discovered = discover_datasets(input_dir)
    file_list_path = Path(output_dir) / "file_list.xlsx"
    if not file_list_path.exists():
        write_file_list(output_dir, discovered)
        return discovered

    saved_names = (
        pd.read_excel(file_list_path)["Path"]
        .dropna()
        .astype(str)
        .tolist()
    )
    discovered_by_name = dict(discovered)
    return [
        (name, discovered_by_name[name])
        for name in saved_names
        if name in discovered_by_name
    ]


def parameter_values(state, parameter_id):
    branch_property_keys = {
        "branch_length": "branchlength",
        "branch_curvature": "branchcurvature",
        "branch_torsion": "branchtorsion",
        "branch_tortuosity": "branchtortuosity",
        "branch_volume": "volume",
        "branch_area": "area",
        "branch_diameter": "branchdiameter_mean",
        "branch_level": "tractIds",
    }
    if parameter_id in branch_property_keys:
        property_key = branch_property_keys[parameter_id]
        return [
            properties[property_key]
            for properties in state.branches_properties
        ]

    tree_attribute_names = {
        "branch_tree_max_length": "cl_tree_max_tree_length",
        "branch_tree_aspect_ratio": "cl_tree_aspect_ratio",
        "branch_tree_fractal_dimension": "cl_tree_fractal_dimension",
        "branch_tree_anisotropy": "cl_tree_anisotropy",
        "branch_tree_sinuosity": "cl_tree_sinuosity",
        "branch_tree_straightness": "cl_tree_straightness",
        "branch_tree_max_level": "cl_tree_max_branch_level",
    }
    if parameter_id in tree_attribute_names:
        return list(getattr(state, tree_attribute_names[parameter_id]))

    soma_property_keys = {
        "soma_volume": "volume",
        "soma_surface_area": "area",
        "soma_sphericity": "sphericity",
        "soma_solidity": "solidity",
        "soma_principal_axes_length": "principal_axes_projection",
    }
    if parameter_id in soma_property_keys:
        value = state.cell_body_properties[
            soma_property_keys[parameter_id]
        ]
        if isinstance(value, (list, tuple, np.ndarray)):
            return np.asarray(value).reshape(-1).tolist()
        return [value]

    cell_attribute_names = {
        "cell_volume": "overall_volume",
        "cell_surface_area": "overall_surface_area",
        "cell_solidity": "cell_solidity",
        "cell_branch_solidity": "branch_solidity",
        "cell_compactness": "compactness",
        "cell_euler_characteristic": "chi",
        "cell_integral_absolute_mean_curvature": "IAMC",
        "cell_willmore_energy": "W",
        "covered_vessel_area": "covered_area",
        "vessel_center_curve_projection_length": "total_length",
    }
    if parameter_id in cell_attribute_names:
        value = getattr(state, cell_attribute_names[parameter_id])
        return [] if value is None else [value]

    main_axis_property_keys = {
        "main_axis_length": "main_axis_length",
        "main_axis_curvature": "main_axis_curvature",
        "main_axis_torsion": "main_axis_torsion",
        "main_axis_tortuosity": "main_axis_tortuosity",
    }
    if parameter_id in main_axis_property_keys:
        value = state.main_axis_properties.get(
            main_axis_property_keys[parameter_id]
        )
        return [] if value is None else [value]

    if parameter_id == "projection_length_axis_length_ratio":
        axis_length = state.main_axis_properties.get("main_axis_length")
        if state.total_length is None or axis_length is None:
            return []
        return [state.total_length / axis_length]

    if parameter_id == "branch_vessel_center_curve_angle":
        return [
            value
            for branch_values in state.branch_vessel_cl_angles
            for value in branch_values
        ]

    raise KeyError(parameter_id)


def export_selected_parameters(state, selected_parameters):
    data_dir = Path(state.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in GENERATED_PARAMETER_JSON_FILENAMES:
        (data_dir / filename).unlink(missing_ok=True)

    exported_paths = []
    summary = {}
    for parameter_id, output_formats in selected_parameters.items():
        values = parameter_values(state, parameter_id)

        if "raw" in output_formats:
            raw_path = data_dir / f"{parameter_id}_raw.json"
            with open(raw_path, "w", encoding="utf-8") as file:
                json.dump(
                    values,
                    file,
                    indent=2,
                    cls=NumpyJsonEncoder,
                )
            exported_paths.append(raw_path)

        numeric_values = np.asarray(values, dtype=float)
        if "mean" in output_formats:
            summary[f"{parameter_id}_mean"] = (
                float(np.mean(numeric_values))
                if len(numeric_values)
                else None
            )
        if "median" in output_formats:
            summary[f"{parameter_id}_median"] = (
                float(np.median(numeric_values))
                if len(numeric_values)
                else None
            )
        if "std" in output_formats:
            summary[f"{parameter_id}_std"] = (
                float(np.std(numeric_values))
                if len(numeric_values)
                else None
            )

    if summary:
        summary_path = data_dir / "re_extract_properties.json"
        with open(summary_path, "w", encoding="utf-8") as file:
            json.dump(
                summary,
                file,
                indent=2,
                cls=NumpyJsonEncoder,
            )
        exported_paths.append(summary_path)

    return exported_paths


class ProcessingControl:
    def __init__(self):
        self.lock = Lock()
        self.active_name = None
        self.skip_name = None
        self.remove_names = set()

    def begin_dataset(self, dataset_name):
        with self.lock:
            self.active_name = dataset_name
            self.skip_name = None

    def request_skip(self, remove=False):
        with self.lock:
            if self.active_name is None:
                return None
            self.skip_name = self.active_name
            if remove:
                self.remove_names.add(self.active_name)
            return self.active_name

    def should_skip(self, dataset_name):
        with self.lock:
            return self.skip_name == dataset_name

    def finish_dataset(self, dataset_name):
        with self.lock:
            skip_requested = self.skip_name == dataset_name
            remove_requested = dataset_name in self.remove_names
            self.remove_names.discard(dataset_name)
            if self.active_name == dataset_name:
                self.active_name = None
            if self.skip_name == dataset_name:
                self.skip_name = None
            return skip_requested, remove_requested


class AnalysisWorker(QObject):
    dataset_started = Signal(int, int, str)
    dataset_finished = Signal(str, str)
    dataset_removed = Signal(str)
    log_message = Signal(str)
    batch_finished = Signal(int, int, int)
    failed = Signal(str)

    def __init__(
        self,
        datasets,
        start_index,
        input_dir,
        output_dir,
        selected_parameters,
        control,
    ):
        super().__init__()
        self.datasets = list(datasets)
        self.start_index = start_index
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.selected_parameters = {
            parameter_id: list(output_formats)
            for parameter_id, output_formats
            in selected_parameters.items()
        }
        self.control = control

    @Slot()
    def run(self):
        completed_count = 0
        skipped_count = 0
        removed_count = 0
        active_datasets = list(self.datasets)

        try:
            analysis = importlib.import_module(ANALYSIS_MODULE_NAME)
            config = analysis.AnalysisConfig(
                input_dir=self.input_dir,
                output_dir=self.output_dir,
                export_default_parameter_json=False,
            )

            for index in range(self.start_index, len(self.datasets)):
                dataset_name, files = self.datasets[index]
                self.control.begin_dataset(dataset_name)
                config.cancel_check = (
                    lambda name=dataset_name:
                    self.control.should_skip(name)
                )
                self.dataset_started.emit(
                    index + 1,
                    len(self.datasets),
                    dataset_name,
                )
                self.log_message.emit(
                    f"Processing {index + 1}/{len(self.datasets)}: "
                    f"{dataset_name}"
                )
                if sys.platform == "darwin":
                    QApplication.processEvents()

                was_cancelled = False
                try:
                    state = analysis.process_dataset(
                        dataset_name,
                        files,
                        config,
                        do_visualization=False,
                    )
                    analysis.raise_if_cancelled(config)
                    exported_paths = export_selected_parameters(
                        state,
                        self.selected_parameters,
                    )
                    self.log_message.emit(
                        f"{dataset_name}: wrote "
                        f"{len(exported_paths)} selected parameter "
                        "JSON file(s)."
                    )
                    analysis.save_workspace(state, config)
                    completed_count += 1
                except analysis.DatasetSkipped:
                    was_cancelled = True
                finally:
                    skip_requested, remove_requested = (
                        self.control.finish_dataset(dataset_name)
                    )

                if remove_requested:
                    active_datasets = [
                        dataset
                        for dataset in active_datasets
                        if dataset[0] != dataset_name
                    ]
                    write_file_list(
                        self.output_dir,
                        active_datasets,
                    )
                    removed_count += 1
                    self.dataset_removed.emit(dataset_name)
                    self.dataset_finished.emit(
                        dataset_name,
                        "Removed from file_list.xlsx",
                    )
                elif was_cancelled or skip_requested:
                    skipped_count += 1
                    self.dataset_finished.emit(
                        dataset_name,
                        "Skipped",
                    )
                else:
                    self.dataset_finished.emit(
                        dataset_name,
                        "Completed",
                    )

                if sys.platform == "darwin":
                    QApplication.processEvents()

            self.batch_finished.emit(
                completed_count,
                skipped_count,
                removed_count,
            )
        except Exception:
            self.failed.emit(traceback.format_exc())


class Mural_VISTA_Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.datasets = []
        self.selected_parameters = {}
        self.analysis_thread = None
        self.analysis_worker = None
        self.processing_control = None

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1180, 760)
        self.resize(1450, 920)
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(28, 22, 28, 22)
        main_layout.setSpacing(14)

        title = QLabel(APP_NAME)
        title.setObjectName("title")
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("subtitle")
        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)

        folder_group = QGroupBox("1. Data folders")
        folder_layout = QGridLayout(folder_group)
        folder_layout.setColumnStretch(1, 1)

        self.input_path_edit = QLineEdit()
        self.input_path_edit.setPlaceholderText(
            "Folder containing *_fused_green.ply files"
        )
        input_button = QPushButton("Browse...")
        input_button.clicked.connect(self._browse_input_folder)

        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText(
            "Folder for analysis results and file_list.xlsx"
        )
        output_button = QPushButton("Browse...")
        output_button.clicked.connect(self._browse_output_folder)

        folder_layout.addWidget(QLabel("Input folder"), 0, 0)
        folder_layout.addWidget(self.input_path_edit, 0, 1)
        folder_layout.addWidget(input_button, 0, 2)
        folder_layout.addWidget(QLabel("Output folder"), 1, 0)
        folder_layout.addWidget(self.output_path_edit, 1, 1)
        folder_layout.addWidget(output_button, 1, 2)
        main_layout.addWidget(folder_group)

        explore_frame = QFrame()
        explore_frame.setObjectName("info_card")
        explore_layout = QHBoxLayout(explore_frame)
        self.explore_button = QPushButton("Explore files")
        self.explore_button.setObjectName("primary_button")
        self.explore_button.clicked.connect(self.explore_files)
        self.file_count_label = QLabel("No folder explored")
        self.file_count_label.setObjectName("file_count")
        self.start_index_spin = QSpinBox()
        self.start_index_spin.setRange(0, 0)
        self.start_index_spin.setToolTip(
            "Zero-based dataset number at which processing begins"
        )
        explore_layout.addWidget(self.explore_button)
        explore_layout.addWidget(self.file_count_label, 1)
        explore_layout.addWidget(QLabel("Start number (0-based)"))
        explore_layout.addWidget(self.start_index_spin)
        main_layout.addWidget(explore_frame)

        selection_splitter = QSplitter(Qt.Orientation.Horizontal)
        selection_splitter.addWidget(self._build_parameter_panel())
        selection_splitter.addWidget(self._build_format_panel())
        selection_splitter.addWidget(self._build_selected_panel())
        selection_splitter.setStretchFactor(0, 5)
        selection_splitter.setStretchFactor(1, 2)
        selection_splitter.setStretchFactor(2, 4)
        selection_splitter.setSizes([560, 220, 450])
        main_layout.addWidget(selection_splitter, 1)

        progress_group = QGroupBox("3. Processing progress")
        progress_layout = QGridLayout(progress_group)
        self.current_number_label = QLabel("Cell 0 / 0")
        self.current_number_label.setObjectName("progress_number")
        self.current_cell_label = QLabel("Waiting to start")
        self.current_cell_label.setObjectName("current_cell")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)

        self.run_button = QPushButton("Run analysis")
        self.run_button.setObjectName("primary_button")
        self.run_button.clicked.connect(self.run_analysis)
        self.skip_button = QPushButton("Skip this cell")
        self.skip_button.clicked.connect(
            lambda: self.request_skip(False)
        )
        self.remove_button = QPushButton(
            "Skip and remove from file list"
        )
        self.remove_button.setObjectName("danger_button")
        self.remove_button.clicked.connect(
            lambda: self.request_skip(True)
        )
        self.skip_button.setEnabled(False)
        self.remove_button.setEnabled(False)

        progress_layout.addWidget(self.current_number_label, 0, 0)
        progress_layout.addWidget(self.current_cell_label, 0, 1, 1, 3)
        progress_layout.addWidget(self.progress_bar, 1, 0, 1, 4)
        progress_layout.addWidget(self.run_button, 2, 0)
        progress_layout.addWidget(self.skip_button, 2, 1)
        progress_layout.addWidget(self.remove_button, 2, 2, 1, 2)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(92)
        self.log_output.setPlaceholderText(
            "Processing messages will appear here."
        )
        progress_layout.addWidget(self.log_output, 3, 0, 1, 4)
        main_layout.addWidget(progress_group)

        self.setCentralWidget(central_widget)

    def _build_parameter_panel(self):
        group = QGroupBox("2A. Parameters")
        layout = QVBoxLayout(group)

        self.parameter_tree = QTreeWidget()
        self.parameter_tree.setHeaderHidden(True)
        self.parameter_tree.setAlternatingRowColors(True)
        for group_name, parameters in PARAMETER_GROUPS:
            group_item = QTreeWidgetItem([group_name])
            group_item.setFlags(
                group_item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsAutoTristate
            )
            group_item.setCheckState(0, Qt.CheckState.Unchecked)
            group_font = QFont()
            group_font.setBold(True)
            group_item.setFont(0, group_font)
            self.parameter_tree.addTopLevelItem(group_item)

            for parameter_id, label in parameters:
                parameter_item = QTreeWidgetItem([label])
                parameter_item.setFlags(
                    parameter_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                parameter_item.setCheckState(
                    0,
                    Qt.CheckState.Unchecked,
                )
                parameter_item.setData(
                    0,
                    Qt.ItemDataRole.UserRole,
                    parameter_id,
                )
                group_item.addChild(parameter_item)

        self.parameter_tree.expandAll()
        layout.addWidget(self.parameter_tree)

        button_row = QHBoxLayout()
        select_all_button = QPushButton("Select all")
        select_all_button.clicked.connect(
            lambda: self._set_all_parameters_checked(True)
        )
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(
            lambda: self._set_all_parameters_checked(False)
        )
        button_row.addWidget(select_all_button)
        button_row.addWidget(clear_button)
        layout.addLayout(button_row)
        return group

    def _build_format_panel(self):
        group = QGroupBox("2B. Output format")
        layout = QVBoxLayout(group)

        guidance = QLabel(
            "Choose one or more formats, then add the checked "
            "parameters."
        )
        guidance.setWordWrap(True)
        guidance.setObjectName("muted")
        layout.addWidget(guidance)

        self.format_list = QListWidget()
        for format_id, label in OUTPUT_FORMATS:
            item = QListWidgetItem(label)
            item.setFlags(
                item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, format_id)
            self.format_list.addItem(item)
        layout.addWidget(self.format_list)

        add_button = QPushButton("Add selected  →")
        add_button.setObjectName("primary_button")
        add_button.clicked.connect(self.add_selected_parameters)
        layout.addWidget(add_button)
        return group

    def _build_selected_panel(self):
        group = QGroupBox("2C. Selected parameters")
        layout = QVBoxLayout(group)

        self.selected_tree = QTreeWidget()
        self.selected_tree.setColumnCount(2)
        self.selected_tree.setHeaderLabels(
            ["Parameter", "Export"]
        )
        self.selected_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        header = self.selected_tree.header()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        layout.addWidget(self.selected_tree)

        button_row = QHBoxLayout()
        remove_button = QPushButton("Remove selected")
        remove_button.clicked.connect(
            self.remove_selected_parameters
        )
        clear_button = QPushButton("Clear all")
        clear_button.clicked.connect(
            self.clear_selected_parameters
        )
        button_row.addWidget(remove_button)
        button_row.addWidget(clear_button)
        layout.addLayout(button_row)
        return group

    def _apply_style(self):
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4f7f8;
                color: #17323a;
                font-family: "Segoe UI";
                font-size: 10pt;
            }
            QLabel#title {
                color: #123d45;
                font-size: 24pt;
                font-weight: 700;
            }
            QLabel#subtitle {
                color: #557079;
                font-size: 10.5pt;
                margin-bottom: 4px;
            }
            QLabel#file_count, QLabel#current_cell {
                color: #285b63;
                font-weight: 600;
            }
            QLabel#progress_number {
                color: #0b6f71;
                font-size: 11pt;
                font-weight: 700;
            }
            QLabel#muted {
                color: #6f8086;
            }
            QGroupBox {
                background: white;
                border: 1px solid #d6e0e3;
                border-radius: 8px;
                font-weight: 650;
                margin-top: 9px;
                padding-top: 11px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: #234d55;
            }
            QFrame#info_card {
                background: #e8f4f3;
                border: 1px solid #c7e0dd;
                border-radius: 8px;
            }
            QLineEdit, QSpinBox, QTextEdit, QTreeWidget, QListWidget {
                background: white;
                border: 1px solid #ccd9dc;
                border-radius: 5px;
                padding: 5px;
                selection-background-color: #69aead;
            }
            QTreeWidget::item, QListWidget::item {
                min-height: 23px;
            }
            QPushButton {
                background: #edf2f3;
                border: 1px solid #bdcdd1;
                border-radius: 5px;
                padding: 7px 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #e2ebed;
            }
            QPushButton:disabled {
                color: #9ba8ac;
                background: #f2f4f5;
            }
            QPushButton#primary_button {
                background: #0b7777;
                border-color: #0b7777;
                color: white;
            }
            QPushButton#primary_button:hover {
                background: #086969;
            }
            QPushButton#danger_button {
                background: #fff4f1;
                border-color: #e5b6a9;
                color: #a2432c;
            }
            QProgressBar {
                background: #e1e8ea;
                border: 0;
                border-radius: 6px;
                min-height: 14px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #2d9993;
                border-radius: 6px;
            }
            """
        )

    def _browse_input_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose input folder",
            self.input_path_edit.text(),
        )
        if folder:
            self.input_path_edit.setText(folder)

    def _browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose output folder",
            self.output_path_edit.text(),
        )
        if folder:
            self.output_path_edit.setText(folder)

    @Slot()
    def explore_files(self):
        input_path = self.input_path_edit.text().strip()
        output_path = self.output_path_edit.text().strip()
        if not input_path or not output_path:
            QMessageBox.information(
                self,
                "Choose folders",
                "Choose both the input and output folders first.",
            )
            return

        self.datasets = load_or_create_file_list(
            input_path,
            output_path,
        )
        count = len(self.datasets)
        self.start_index_spin.setRange(0, max(0, count - 1))
        if count:
            first_name = self.datasets[0][0]
            last_name = self.datasets[-1][0]
            self.file_count_label.setText(
                f"{count} cells ready  |  First: {first_name}  |  "
                f"Last: {last_name}"
            )
        else:
            self.file_count_label.setText(
                "No matching mural-cell files were found."
            )
        self.current_number_label.setText(f"Cell 0 / {count}")
        self.progress_bar.setRange(0, max(1, count))
        self.progress_bar.setValue(0)

    def _set_all_parameters_checked(self, checked):
        state = (
            Qt.CheckState.Checked
            if checked
            else Qt.CheckState.Unchecked
        )
        for group_index in range(
            self.parameter_tree.topLevelItemCount()
        ):
            group_item = self.parameter_tree.topLevelItem(group_index)
            group_item.setCheckState(0, state)

    def _checked_parameter_ids(self):
        checked_ids = []
        for group_index in range(
            self.parameter_tree.topLevelItemCount()
        ):
            group_item = self.parameter_tree.topLevelItem(group_index)
            for child_index in range(group_item.childCount()):
                parameter_item = group_item.child(child_index)
                if (
                    parameter_item.checkState(0)
                    == Qt.CheckState.Checked
                ):
                    checked_ids.append(
                        parameter_item.data(
                            0,
                            Qt.ItemDataRole.UserRole,
                        )
                    )
        return checked_ids

    def _checked_output_formats(self):
        checked_formats = []
        for row in range(self.format_list.count()):
            item = self.format_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                checked_formats.append(
                    item.data(Qt.ItemDataRole.UserRole)
                )
        return checked_formats

    @Slot()
    def add_selected_parameters(self):
        parameter_ids = self._checked_parameter_ids()
        output_formats = self._checked_output_formats()
        if not parameter_ids or not output_formats:
            QMessageBox.information(
                self,
                "Complete the selection",
                "Check at least one parameter and one output format.",
            )
            return

        for parameter_id in parameter_ids:
            current_formats = self.selected_parameters.setdefault(
                parameter_id,
                [],
            )
            for output_format in output_formats:
                if output_format not in current_formats:
                    current_formats.append(output_format)
        self._refresh_selected_tree()

    @Slot()
    def remove_selected_parameters(self):
        parameter_ids = {
            item.data(0, Qt.ItemDataRole.UserRole)
            for item in self.selected_tree.selectedItems()
        }
        for parameter_id in parameter_ids:
            self.selected_parameters.pop(parameter_id, None)
        self._refresh_selected_tree()

    @Slot()
    def clear_selected_parameters(self):
        self.selected_parameters.clear()
        self._refresh_selected_tree()

    def _refresh_selected_tree(self):
        self.selected_tree.clear()
        for parameter_id, output_formats in (
            self.selected_parameters.items()
        ):
            output_labels = [
                OUTPUT_FORMAT_LABELS[output_format]
                for output_format in output_formats
            ]
            item = QTreeWidgetItem(
                [
                    PARAMETER_LABELS[parameter_id],
                    ", ".join(output_labels),
                ]
            )
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                parameter_id,
            )
            self.selected_tree.addTopLevelItem(item)

    @Slot()
    def run_analysis(self):
        if not self.datasets:
            QMessageBox.information(
                self,
                "Explore files",
                "Explore the input folder before starting.",
            )
            return
        if not self.selected_parameters:
            QMessageBox.information(
                self,
                "Select exports",
                "Add at least one parameter and output format.",
            )
            return

        self.processing_control = ProcessingControl()
        if sys.platform == "darwin":
            self.analysis_thread = None
        else:
            self.analysis_thread = QThread(self)
        self.analysis_worker = AnalysisWorker(
            datasets=self.datasets,
            start_index=self.start_index_spin.value(),
            input_dir=self.input_path_edit.text().strip(),
            output_dir=self.output_path_edit.text().strip(),
            selected_parameters=self.selected_parameters,
            control=self.processing_control,
        )

        self.analysis_worker.dataset_started.connect(
            self._dataset_started
        )
        self.analysis_worker.dataset_finished.connect(
            self._dataset_finished
        )
        self.analysis_worker.dataset_removed.connect(
            self._dataset_removed
        )
        self.analysis_worker.log_message.connect(
            self.log_output.append
        )
        self.analysis_worker.batch_finished.connect(
            self._batch_finished
        )
        self.analysis_worker.failed.connect(self._batch_failed)

        if self.analysis_thread is None:
            self.analysis_worker.batch_finished.connect(
                self._thread_finished
            )
            self.analysis_worker.failed.connect(
                self._thread_finished
            )
        else:
            self.analysis_worker.moveToThread(self.analysis_thread)
            self.analysis_thread.started.connect(
                self.analysis_worker.run
            )
            self.analysis_worker.batch_finished.connect(
                self.analysis_thread.quit
            )
            self.analysis_worker.failed.connect(
                self.analysis_thread.quit
            )
            self.analysis_thread.finished.connect(
                self.analysis_worker.deleteLater
            )
            self.analysis_thread.finished.connect(
                self._thread_finished
            )
            self.analysis_thread.finished.connect(
                self.analysis_thread.deleteLater
            )

        self._set_running(True)
        self.log_output.clear()
        if self.analysis_thread is None:
            QTimer.singleShot(0, self.analysis_worker.run)
        else:
            self.analysis_thread.start()

    def _set_running(self, running):
        self.input_path_edit.setEnabled(not running)
        self.output_path_edit.setEnabled(not running)
        self.explore_button.setEnabled(not running)
        self.start_index_spin.setEnabled(not running)
        self.parameter_tree.setEnabled(not running)
        self.format_list.setEnabled(not running)
        self.selected_tree.setEnabled(not running)
        self.run_button.setEnabled(not running)
        self.skip_button.setEnabled(running)
        self.remove_button.setEnabled(running)

    @Slot(int, int, str)
    def _dataset_started(self, current, total, dataset_name):
        self.current_number_label.setText(
            f"Cell {current} / {total}"
        )
        self.current_cell_label.setText(dataset_name)
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)

    @Slot(str, str)
    def _dataset_finished(self, dataset_name, status):
        self.log_output.append(f"{dataset_name}: {status}")

    @Slot(str)
    def _dataset_removed(self, dataset_name):
        self.datasets = [
            dataset
            for dataset in self.datasets
            if dataset[0] != dataset_name
        ]

    @Slot(bool)
    def request_skip(self, remove):
        if self.processing_control is None:
            return
        dataset_name = self.processing_control.request_skip(remove)
        if dataset_name is None:
            return
        action = (
            "Skip and remove requested"
            if remove
            else "Skip requested"
        )
        self.log_output.append(
            f"{action}: {dataset_name}. "
            "Close any open 3D selection window if it remains visible."
        )
        if sys.platform != "darwin":
            pyvista_module = sys.modules.get("pyvista")
            if pyvista_module is not None:
                try:
                    pyvista_module.close_all()
                except RuntimeError:
                    pass

    @Slot(int, int, int)
    def _batch_finished(self, completed, skipped, removed):
        self._set_running(False)
        self.current_cell_label.setText("Batch finished")
        self.log_output.append(
            f"Finished: {completed} completed, {skipped} skipped, "
            f"{removed} removed."
        )
        self.start_index_spin.setRange(
            0,
            max(0, len(self.datasets) - 1),
        )

    @Slot(str)
    def _batch_failed(self, details):
        self._set_running(False)
        self.current_cell_label.setText("Processing stopped")
        self.log_output.append(details)
        QMessageBox.critical(
            self,
            "Analysis stopped",
            "The analysis stopped. See the processing messages for details.",
        )

    @Slot()
    def _thread_finished(self):
        self.analysis_worker = None
        self.analysis_thread = None
        self.processing_control = None


def run_self_test(report_path=None):
    report = {"status": "failed"}
    try:
        analysis = importlib.import_module(ANALYSIS_MODULE_NAME)
        import gudhi
        import pymeshfix
        import pyvista
        import trimesh
        import vtk
        from vmtk import vmtkscripts

        centerline_probe = vmtkscripts.vmtkCenterlines()
        centerline_probe.PrintLog(f"{APP_NAME} VMTK stream check")
        vmtk_output_stream = (
            centerline_probe.OutputStream is not None
            and hasattr(centerline_probe.OutputStream, "write")
        )
        if not vmtk_output_stream:
            raise RuntimeError("VMTK did not receive a writable output stream.")

        config = analysis.AnalysisConfig(
            input_dir=Path.cwd(),
            output_dir=Path.cwd(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = Path(temp_dir) / "check.xlsx"
            pd.DataFrame({"value": [1]}).to_excel(
                workbook_path,
                index=False,
            )
            workbook_value = int(
                pd.read_excel(workbook_path).iloc[0, 0]
            )

            selected_data_dir = Path(temp_dir) / "selected-json"
            selected_data_dir.mkdir()
            (
                selected_data_dir / "branches_properties.json"
            ).write_text('{"stale": true}', encoding="utf-8")
            selected_state = type("SelectedState", (), {})()
            selected_state.data_dir = selected_data_dir
            selected_state.overall_volume = 2.5
            export_selected_parameters(
                selected_state,
                {"cell_volume": ["raw", "mean"]},
            )
            selected_json_files = sorted(
                path.name
                for path in selected_data_dir.glob("*.json")
            )
            selected_summary_keys = sorted(
                json.loads(
                    (
                        selected_data_dir
                        / "re_extract_properties.json"
                    ).read_text(encoding="utf-8")
                )
            )
            if selected_json_files != [
                "cell_volume_raw.json",
                "re_extract_properties.json",
            ]:
                raise RuntimeError(
                    "Selected-only JSON export check failed."
                )
            if selected_summary_keys != ["cell_volume_mean"]:
                raise RuntimeError(
                    "Selected-only JSON summary check failed."
                )

        report = {
            "status": "ok",
            "application_name": APP_NAME,
            "analysis_config": config.__class__.__name__,
            "vtk_reader": vtk.vtkPLYReader.__name__,
            "pyvista": pyvista.__version__,
            "vmtk_centerlines": (
                vmtkscripts.vmtkCenterlines.__name__
            ),
            "vmtk_output_stream": vmtk_output_stream,
            "trimesh": trimesh.__version__,
            "gudhi_alpha_complex": gudhi.AlphaComplex.__name__,
            "pymeshfix": pymeshfix.__version__,
            "workbook_value": workbook_value,
            "analysis_default_parameter_json": (
                config.export_default_parameter_json
            ),
            "selected_json_files": selected_json_files,
            "selected_summary_keys": selected_summary_keys,
        }
        exit_code = 0
    except Exception:
        report["traceback"] = traceback.format_exc()
        exit_code = 1

    if report_path is not None:
        Path(report_path).write_text(
            json.dumps(report, indent=2),
            encoding="utf-8",
        )
    return exit_code


def main():
    if "--self-test" in sys.argv:
        argument_index = sys.argv.index("--self-test")
        report_path = (
            sys.argv[argument_index + 1]
            if argument_index + 1 < len(sys.argv)
            else None
        )
        raise SystemExit(run_self_test(report_path))

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setStyle("Fusion")
    window = Mural_VISTA_Window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
