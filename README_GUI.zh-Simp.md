[English](README_GUI.md) | [简体中文](README_GUI.zh-Simp.md) | [繁體中文](README_GUI.zh-Trad.md) | [日本語](README_GUI.ja.md)

# Mural-VISTA GUI

Mural-VISTA GUI 是基于 PySide6 的桌面图形界面。

## GUI 操作流程

1. 选择输入文件夹，其中应包含 `<cell>_fused_green.ply`（或 `_fused_gre.ply`），以及可选的 `<cell>_fused_red.ply`。
2. 选择输出文件夹，点击 **Explore files（浏览文件）**。
3. 输入 **Start number（起始编号）**，编号从 0 开始。
4. 根据需要选择以下选项：

   - **Expand the mural cell mesh（扩张血管壁细胞网格）**：输入非负的扩张距离，单位与网格一致。
   - **Open the corresponding raw z-stack image for cell structure reference（打开对应的原始 Z 轴图像堆栈，供参考细胞结构）**：将 `<cell>_fused.tif`、`.tiff`、`.ome.tif` 或 `.ome.tiff` 文件放在网格所在的文件夹中。

5. 选择参数和输出格式，点击 **Add selected（添加所选项）**。
6. 点击 **Run analysis（运行分析）**，完成交互式三维选取操作。

**Skip this cell（跳过此细胞）** 会在下一个安全的处理阶段边界停止当前细胞的分析。GUI 会尝试关闭正在使用的 PyVista 窗口；如果 VMTK 或三维选取窗口仍然显示，请关闭该窗口以完成跳过操作。

**Skip and remove from file list（跳过并从文件列表中移除）** 还会从输出文件夹的 `file_list.xlsx` 中移除该细胞。下次浏览文件时会读取已保存的列表，因此该细胞仍会被排除。

## 所选结果的导出

- **Raw data（原始数据）**：在该细胞的输出文件夹中写入 `<parameter_id>_raw.json`。
- **Mean（均值）**、**Median（中位数）** 和 **Standard deviation（标准差）**：写入该细胞的 `re_extract_properties.json`。此文件只包含 GUI 中选中的汇总格式。
- 仅选择原始数据时，不会生成 `re_extract_properties.json`。
- 写入当前所选结果前，GUI 只会删除该细胞输出文件夹中上次运行生成的、已知属于 Mural-VISTA 的参数结果 JSON 文件。用户其他无关的 JSON 文件会保留。

预处理网格、种子点文件和派生 PLY 文件保存在所选输出根目录下。各细胞的 JSON、pickle、VTU 和 VTP 结果保存在 `<output folder>/<cell name>/` 中。

程序会保留运行所需的 `*_seeds.json` 和 `*_main_axis_seeds.json`，因为它们缓存了交互式中心线选点。网格、pickle 缓存、分支数据集和 `workspace.pkl` 也会保留。

## 这是 Windows 应用程序

由于 Qt、VTK 和 VMTK 包含许多原生 DLL，本程序采用单文件夹打包方式。使用打包好的程序时无需安装 Python，但分发时必须将 EXE 与完整的 `dist\Mural-VISTA` 文件夹一起提供。
