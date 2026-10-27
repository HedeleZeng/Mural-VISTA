[English](../README.md) | [简体中文](README.zh-Simp.md) | [繁體中文](README.zh-Trad.md) | [日本語](README.ja.md)

# Mural-VISTA

用於評估血管壁細胞與血管交互作用，以及進行多尺度單細胞拓撲形態分析的工具

# 最新版本：v2.1.0（261023）

**血管壁細胞－血管交互作用與單細胞拓撲形態分析**

Mural-VISTA 分析血管壁細胞的三維表面形態。如果同時提供已對位的血管網格，還可以分析細胞與血管的空間關係。程式擷取中心線，分離分支和胞體，計算形態學與拓撲學指標，並匯出數值結果及衍生網格。

此原始碼的工作流程是**互動式**的。程式會開啟 VMTK/PyVista 三維視窗，由使用者選擇中心線端點、移除不需要的網格區域，並確認分割結果。因此，它不適合無人值守或無圖形介面的批次執行。

## 輸入

將 Python 檔案開頭附近的 `DEFAULT_INPUT_DIR` 設定為存放網格的資料夾。程式會在該資料夾及其子資料夾中搜尋副檔名為小寫 `.ply` 的檔案。

每組資料使用以下命名方式：

```text
<dataset>_fused_green.ply    必要的血管壁細胞表面網格
<dataset>_fused_red.ply      選用的參考血管表面網格
```

血管壁細胞網格也可以命名為 `<dataset>_fused_gre.ply`。例如：

```text
input_folder/
├── cell_01_fused_green.ply
├── cell_01_fused_red.ply
├── cell_02_fused_green.ply
└── cell_02_fused_red.ply
```

輸入網格應為三角化表面。同一組資料的壁細胞和血管表面網格必須使用相同的座標系和單位。輸出的長度、面積和體積單位由輸入網格的單位決定。

血管網格為選用輸入。沒有它時，Mural-VISTA 仍會計算細胞形態指標，但不會計算血管覆蓋、投影及分支與血管關係的指標。

## 基本流程

對於每組偵測到的資料，程式會依序執行：

1. 讀取 green/`gre` PLY 網格，並轉換為供 VMTK 使用的 ASCII VTP 表面。
2. 由使用者移除網格缺陷，然後修復、平滑、清理並細分表面。
3. 由使用者選擇來源點和目標點，擷取 VMTK 中心線。
4. 根據中心線建立管狀模型，並請使用者確認擷取結果，或重新選擇中心線端點。
5. 以互動方式分離分支、主軸或初級突起，以及胞體。
6. 計算分支、分支樹、胞體、主軸及整個細胞的指標。
7. 如果存在紅色血管網格，計算細胞與血管的覆蓋、投影和角度指標。
8. 儲存數值 JSON 檔案、衍生網格、中心線資料集，以及可供下次執行重複使用的快取。

## 輸出

使用預設設定執行原始程式時，結果儲存在輸入資料夾中。如果透過其他 Python 程式呼叫，也可以透過 `AnalysisConfig.output_dir` 指定輸出根目錄。

輸出根目錄包含：

- `file_list.xlsx`：偵測到的資料集清單；
- 相容於 VMTK 的網格和前處理網格，例如 `<green_stem>.vtp` 和 `<green_stem>_clipped.ply`；
- 儲存的中心線選點：`<green_stem>_seeds.json` 和 `<green_stem>_main_axis_seeds.json`；
- 分支、胞體及主軸區域的衍生 PLY 表面。

每組資料還會有獨立的資料夾：

```text
<output>/<dataset>/
├── re_extract_properties.json       綜合彙整指標
├── branches_properties.json         各分支的指標
├── cell_body_properties.json        胞體指標
├── main_axis_properties.json        主軸指標
├── branch_*.json                    分支及其與血管關係的數值
├── cl_tree_*.json                   分支樹數值
├── clipped_mesh.pkl                 可重複使用的分割快取
├── workspace.pkl                    儲存的分析工作區
├── branches_surface/                各分支的表面檔案（.vtu）
├── branches_centerline/             中心線檔案（.vtu）
└── branches_tube/                   各分支的管狀模型檔案（.vtp）
```

輸出指標包括：分支長度、直徑、曲率、撓率、迂曲度、表面積和體積；分支樹結構；胞體體積、面積、球形度、實心度和主軸；細胞主軸的幾何特徵；整個細胞的形狀和拓撲特徵；以及在提供血管網格時計算的血管壁細胞與血管的空間關係指標。

再次執行時，Mural-VISTA 會重複使用相容的裁切網格、已選種子點、分割快取和中心線。只有需要重新執行對應的互動步驟時，才應刪除相關快取。

## 使用即用型 Windows GUI

本專案也提供配套的 64 位元 Windows 圖形介面：`Mural-VISTA_v2.1.0_Windows_x64.zip`。壓縮檔內已包含 Python 和所需的科學運算函式庫，使用者無需安裝 Python 或 Conda。

使用方法：

1. 從 Mural-VISTA 的 GitHub Release 或 Zenodo 紀錄下載 ZIP 壓縮檔。
2. **完整解壓縮** ZIP 壓縮檔。
3. 啟動 `Mural-VISTA.exe`。

請將 `Mural-VISTA.exe` 與其 `_internal` 資料夾放在一起，不要單獨複製或散布 EXE。GUI 提供資料夾瀏覽、資料集搜尋、進度顯示，以及參數和匯出內容選擇；核心分析流程仍會開啟互動式 VMTK/PyVista 視窗。

## 使用 Python 執行

**環境需求**

本專案已在 Python 3.10 及 `envi_lib_list.txt` 記錄的環境中測試。主要的非標準函式庫相依套件包括：

- VTK 和 PyVista；
- VMTK 1.5.0，使用本發行版提供的修改版 `vmtkcenterlines.py`；
- NumPy、pandas、SciPy、NetworkX、trimesh、PyMeshFix 和 GUDHI；
- openpyxl，供 pandas 寫入 `file_list.xlsx`。

執行時需要圖形桌面環境。開始長時間分析前，可以使用以下指令檢查環境：

```bash
python -c "import vtk, pyvista, vmtk, numpy, pandas, scipy, networkx, trimesh, pymeshfix, gudhi, openpyxl"
```

**修改後的 VMTK 功能**

Mural-VISTA 使用 VMTK 的**修改版** `vmtkcenterlines.py`。
（[VMTK 原始檔案](https://github.com/vmtk/vmtk/blob/master/vmtkScripts/vmtkcenterlines.py)）
修改後，在選擇目標點時仍能清楚區分來源種子點，並可以取得所選來源點和目標點的座標，以便 Mural-VISTA 儲存和重複使用這些選點。

配套的修改版檔案隨本軟體一同發佈於 GitHub 和 Zenodo 封存版本中。請使用與分析腳本屬於**同一 Mural-VISTA 發行版**的檔案。

執行原始碼前：

1. 在 Python 環境中安裝 VMTK。
2. 尋找其安裝目錄：

   ```bash
   python -c "import pathlib, vmtk; print(pathlib.Path(vmtk.__file__).resolve().parent)"
   ```

3. 備份已安裝的 `vmtkcenterlines.py`。
4. 用本發行版提供的修改版 `vmtkcenterlines.py` 取代它，檔名必須保持完全一致。

**執行原始程式**

1. 啟用已設定好的 Python 環境。
2. 修改 `Mural-VISTA_v2-1-0_261023.py` 中的 `DEFAULT_INPUT_DIR`。
3. 在終端機中啟動程式：

   ```bash
   python Mural-VISTA_v2-1-0_261023.py
   ```

4. 保持終端機開啟，並完成每一步互動式三維操作。終端機會顯示進度和目前資料集名稱。

## 引用

如果 Mural-VISTA 對您的研究有所幫助，**我們將非常感謝您引用本專案**。

請引用：

1. 實際使用的 Mural-VISTA 軟體版本。
2. 配套的 Mural-VISTA 研究論文：

   Zeng, H., et al.,
   Mural-VISTA: A tool for mural cell-vessel interaction assessment and multiscale single-cell topo-morphological analysis.
   bioRxiv, 2026.
   DOI: 10.64898/2026.08.27.747487

3. VMTK：

   Izzo, R., et al.,
   The Vascular Modeling Toolkit: A Python Library for the Analysis of Tubular Structures in Medical Images.
   Journal of Open Source Software, 2018. 3(25): p. 745.
   DOI: 10.21105/joss.00745

## 專案連結

- [GitHub 儲存庫與發行版](https://github.com/HedeleZeng/Mural-VISTA.git)
- Zenodo 封存版本：10.5281/zenodo.22124716
- [bioRxiv 封存版本](https://www.biorxiv.org/content/10.64898/2026.08.27.747487v1)

  Zeng, H., et al., Mural-VISTA: A tool for mural cell-vessel interaction assessment and multiscale single-cell topo-morphological analysis. bioRxiv, 2026.

## 授權條款

著作權所有 © 2026 Hedele Zeng。

除非另有說明，本專案開發的原創程式碼採用 BSD 3-Clause License（BSD 三條款授權）。

本專案使用第三方軟體，並在註明的情況下包含這些軟體；它們分別遵循各自的授權條款。第三方元件保留原有的著作權和授權條款，不會重新授權為 BSD 三條款授權。

詳情請參閱 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)。

本專案的部分功能依賴 GPL 授權的軟體，包括 PyMeshFix/MeshFix，以及 GUDHI AlphaComplex 使用的 GPLv3 相依套件。重新散布本軟體的組合版本或綑綁版本時，散布者有責任遵守適用的第三方授權條款。
