# Third-Party Software and Licenses

This project uses the following third-party open-source software. Each third-party component remains subject to its respective copyright and license terms.

| Software            | Version used | License                                               | Use in this project                                                                       |
| ------------------- | ------------ | ----------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| VTK                 | 9.2.6        | BSD 3-Clause                                          | Mesh processing and VTK data structures                                                   |
| PyVista             | 0.45.3       | MIT                                                   | Mesh processing and visualization                                                         |
| VMTK                | 1.5.0        | BSD 3-Clause                                          | Centerline and vascular mesh analysis; selected source code was modified for this project |
| PyMeshFix           | 0.17.1       | GNU GPL v3                                            | Mesh defect repair                                                                        |
| Trimesh             | 4.12.2       | MIT                                                   | Convex-hull and mesh operations                                                           |
| NumPy               | 2.2.6        | BSD 3-Clause                                          | Numerical calculations                                                                    |
| SciPy               | 1.15.2       | BSD 3-Clause                                          | Scientific and statistical calculations                                                   |
| pandas              | 2.3.3        | BSD 3-Clause                                          | Data handling and tabular data processing                                                 |
| NetworkX            | 3.4.2        | BSD 3-Clause                                          | Graph-based analysis                                                                      |
| GUDHI               | 3.11.0       | MIT; AlphaComplex has GPLv3 dependency                | Alpha-complex / alpha-shape analysis                                                      |
| PySide6             | 6.8.1        | LGPLv3 / GPLv3 / Qt Commercial License                | Graphical user interface                                                                  |
| PyInstaller         | 6.21.0       | GPLv2 with a special exception; some files Apache-2.0 | Packaging of the Windows executable                                                       |
| Python              | 3.10         | Python Software Foundation License                    | Runtime environment                                                                       |

## Modified VMTK Code

This repository contains code derived from VMTK (Vascular Modeling Toolkit), originally licensed under the BSD 3-Clause License.

The VMTK-derived code has been modified for this project. The original VMTK copyright and license notices are retained in accordance with the BSD 3-Clause License. Modifications made specifically for this project are identified in the relevant source files.

VMTK copyright:

Copyright (c) 2004–2018, Luca Antiga, David Steinman, Simone Manini, Richard Izzo.
All rights reserved.

See the VMTK license included with the relevant source files for the complete license terms.

## GPL-Licensed Components

PyMeshFix/MeshFix is distributed under the GNU General Public License version 3 (GPLv3) for free-software use.

The GUDHI AlphaComplex functionality used in this project relies on GPLv3-licensed dependencies, including CGAL. Although GUDHI itself is primarily distributed under the MIT License, GUDHI identifies AlphaComplex as "MIT (GPL v3)" for licensing purposes.

These components retain their original licenses. Nothing in the BSD 3-Clause License applied to original code in this repository is intended to supersede or modify the license terms of these third-party components.

## PySide6

PySide6 is provided under the LGPLv3, GPLv3, or Qt commercial licensing options. This project uses the open-source distribution of PySide6. Applicable Qt/PySide6 license notices should be retained when redistributing binary builds containing PySide6.

## PyInstaller

PyInstaller is distributed primarily under GPLv2 with a special exception permitting executables generated using PyInstaller to be distributed under licenses selected by the application author, subject to compliance with the licenses of bundled dependencies.

## Full License Texts

Where third-party source code is redistributed or included in binary distributions, the corresponding copyright notices and complete license texts should be retained in this repository or accompanying distribution materials.
