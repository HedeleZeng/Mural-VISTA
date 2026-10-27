[English](../README.md) | [简体中文](README.zh-Simp.md) | [繁體中文](README.zh-Trad.md) | [日本語](README.ja.md)

# Mural-VISTA

用于评估血管壁细胞与血管相互作用，以及开展多尺度单细胞拓扑形态分析的工具

# 最新版本：v2.1.0（261023）

**血管壁细胞－血管相互作用与单细胞拓扑形态分析**

Mural-VISTA 分析血管壁细胞的三维表面形态。如果同时提供已配准的血管网格，还可以分析细胞与血管的空间关系。程序提取中心线，分离分支和胞体，计算形态学与拓扑学指标，并导出数值结果及派生网格。

此源代码的工作流程是**交互式**的。程序会打开 VMTK/PyVista 三维窗口，由用户选择中心线端点、移除不需要的网格区域，并确认分割结果。因此，它不适合无人值守或无图形界面的批量运行。

## 输入

将 Python 文件开头附近的 `DEFAULT_INPUT_DIR` 设置为存放网格的文件夹。程序会在该文件夹及其子文件夹中搜索扩展名为小写 `.ply` 的文件。

每组数据使用以下命名方式：

```text
<dataset>_fused_green.ply    必需的血管壁细胞表面网格
<dataset>_fused_red.ply      可选的参考血管表面网格
```

血管壁细胞网格也可以命名为 `<dataset>_fused_gre.ply`。例如：

```text
input_folder/
├── cell_01_fused_green.ply
├── cell_01_fused_red.ply
├── cell_02_fused_green.ply
└── cell_02_fused_red.ply
```

输入网格应为三角化表面。同一组数据的血管壁细胞和血管表面网格必须使用相同的坐标系和单位。输出的长度、面积和体积单位由输入网格的单位决定。

血管网格为可选输入。没有它时，Mural-VISTA 仍会计算细胞形态指标，但不会计算血管覆盖、投影及分支与血管关系的指标。

## 基本流程

对于每组检测到的数据，程序会依次执行：

1. 读取 green/`gre` PLY 网格，并转换为供 VMTK 使用的 ASCII VTP 表面。
2. 由用户移除网格缺陷，然后修复、平滑、清理并细分表面。
3. 由用户选择源点和目标点，提取 VMTK 中心线。
4. 根据中心线构建管状模型，并请用户确认提取结果，或重新选择中心线端点。
5. 以交互方式分离分支、主轴或初级突起，以及胞体。
6. 计算分支、分支树、胞体、主轴及整个细胞的指标。
7. 如果存在血管网格，计算细胞与血管的覆盖、投影和角度指标。
8. 保存数值 JSON 文件、派生网格、中心线数据集，以及可供下次运行复用的缓存。

## 输出

使用默认配置运行源程序时，结果保存在输入文件夹中。如果通过其他 Python 程序调用，也可以通过 `AnalysisConfig.output_dir` 指定输出根目录。

输出根目录包含：

- `file_list.xlsx`：检测到的数据集列表；
- 兼容 VMTK 的网格和预处理网格，例如 `<green_stem>.vtp` 和 `<green_stem>_clipped.ply`；
- 保存的中心线选点：`<green_stem>_seeds.json` 和 `<green_stem>_main_axis_seeds.json`；
- 分支、胞体及主轴区域的派生 PLY 表面。

每组数据还会有独立的文件夹：

```text
<output>/<dataset>/
├── re_extract_properties.json       综合汇总指标
├── branches_properties.json         各分支的指标
├── cell_body_properties.json        胞体指标
├── main_axis_properties.json        主轴指标
├── branch_*.json                    分支及其与血管关系的数值
├── cl_tree_*.json                   分支树数值
├── clipped_mesh.pkl                 可复用的分割缓存
├── workspace.pkl                    保存的分析工作区
├── branches_surface/                各分支的表面文件（.vtu）
├── branches_centerline/             中心线文件（.vtu）
└── branches_tube/                   各分支的管状模型文件（.vtp）
```

输出指标包括：分支长度、直径、曲率、挠率、迂曲度、表面积和体积；分支树结构；胞体体积、面积、球形度、实心度和主轴；细胞主轴的几何特征；整个细胞的形状和拓扑特征；以及在提供血管网格时计算的血管壁细胞与血管的空间关系指标。

再次运行时，Mural-VISTA 会复用兼容的裁剪网格、已选种子点、分割缓存和中心线。只有需要重新执行对应的交互步骤时，才应删除相关缓存。

## 使用即用型 Windows GUI

本项目也提供配套的 64 位 Windows 图形界面：`Mural-VISTA_v2.1.0_Windows_x64.zip`。压缩包内已包含 Python 和所需的科学计算库，用户无需安装 Python 或 Conda。

使用方法：

1. 从 Mural-VISTA 的 GitHub Release 或 Zenodo 记录下载 ZIP 压缩包。
2. **完整解压** ZIP 压缩包。
3. 启动 `Mural-VISTA.exe`。

请将 `Mural-VISTA.exe` 与其 `_internal` 文件夹放在一起，不要单独复制或分发 EXE。GUI 提供文件夹浏览、数据集查找、进度显示，以及参数和导出内容选择；核心分析流程仍会打开交互式 VMTK/PyVista 窗口。

## 使用 Python 运行

**环境要求**

本项目已在 Python 3.10 及 `envi_lib_list.txt` 记录的环境中测试。主要的非标准库依赖包括：

- VTK 和 PyVista；
- VMTK 1.5.0，使用本发行版提供的修改版 `vmtkcenterlines.py`；
- NumPy、pandas、SciPy、NetworkX、trimesh、PyMeshFix 和 GUDHI；
- openpyxl，供 pandas 写入 `file_list.xlsx`。

运行时需要图形桌面环境。开始长时间分析前，可以使用以下命令检查环境：

```bash
python -c "import vtk, pyvista, vmtk, numpy, pandas, scipy, networkx, trimesh, pymeshfix, gudhi, openpyxl"
```

**修改后的 VMTK 功能**

Mural-VISTA 使用 VMTK 的**修改版** `vmtkcenterlines.py`。
（[VMTK 原始文件](https://github.com/vmtk/vmtk/blob/master/vmtkScripts/vmtkcenterlines.py)）
修改后，在选择目标点时仍能清楚区分源种子点，并可以获取所选源点和目标点的坐标，以便 Mural-VISTA 保存和复用这些选点。

配套的修改版文件随本软件一同发布于 GitHub 和 Zenodo 归档中。请使用与分析脚本属于**同一 Mural-VISTA 发行版**的文件。

运行源代码前：

1. 在 Python 环境中安装 VMTK。
2. 查找其安装目录：

   ```bash
   python -c "import pathlib, vmtk; print(pathlib.Path(vmtk.__file__).resolve().parent)"
   ```

3. 备份已安装的 `vmtkcenterlines.py`。
4. 用本发行版提供的修改版 `vmtkcenterlines.py` 替换它，文件名必须保持完全一致。

**运行源程序**

1. 激活已配置好的 Python 环境。
2. 修改 `Mural-VISTA_v2-1-0_261023.py` 中的 `DEFAULT_INPUT_DIR`。
3. 在终端中启动程序：

   ```bash
   python Mural-VISTA_v2-1-0_261023.py
   ```

4. 保持终端打开，并完成每一步交互式三维操作。终端会显示进度和当前数据集名称。

## 引用

如果 Mural-VISTA 对您的研究有所帮助，**我们将非常感谢您引用本项目**。

请引用：

1. 实际使用的 Mural-VISTA 软件版本。
2. 配套的 Mural-VISTA 研究论文：

   Zeng, H., et al.,
   Mural-VISTA: A tool for mural cell-vessel interaction assessment and multiscale single-cell topo-morphological analysis.
   bioRxiv, 2026.
   DOI: 10.64898/2026.08.27.747487

3. VMTK：

   Izzo, R., et al.,
   The Vascular Modeling Toolkit: A Python Library for the Analysis of Tubular Structures in Medical Images.
   Journal of Open Source Software, 2018. 3(25): p. 745.
   DOI: 10.21105/joss.00745

## 项目链接

- [GitHub 仓库与发行版](https://github.com/HedeleZeng/Mural-VISTA.git)
- Zenodo 归档：10.5281/zenodo.22124716
- [bioRxiv 归档](https://www.biorxiv.org/content/10.64898/2026.08.27.747487v1)

  Zeng, H., et al., Mural-VISTA: A tool for mural cell-vessel interaction assessment and multiscale single-cell topo-morphological analysis. bioRxiv, 2026.

## 许可证

版权所有 © 2026 Hedele Zeng。

除非另有说明，本项目开发的原创代码采用 BSD 3-Clause License（BSD 三条款许可证）。

本项目使用第三方软件，并在注明的情况下包含这些软件；它们分别遵循各自的许可证。第三方组件保留原有的版权和许可条款，不会重新授权为 BSD 三条款许可证。

详情请参阅 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)。

本项目的部分功能依赖 GPL 许可的软件，包括 PyMeshFix/MeshFix，以及 GUDHI AlphaComplex 使用的 GPLv3 依赖项。重新分发本软件的组合版本或捆绑版本时，分发者有责任遵守适用的第三方许可条款。
