[English](README_GUI.md) | [简体中文](README_GUI.zh-Simp.md) | [繁體中文](README_GUI.zh-Trad.md) | [日本語](README_GUI.ja.md)

# Mural-VISTA GUI

Mural-VISTA GUI 是基於 PySide6 的桌面圖形介面。

## GUI 操作流程

1. 選擇輸入資料夾，其中應包含 `<cell>_fused_green.ply`（或 `_fused_gre.ply`），以及選用的 `<cell>_fused_red.ply`。
2. 選擇輸出資料夾，點選 **Explore files（瀏覽檔案）**。
3. 輸入 **Start number（起始編號）**，編號從 0 開始。
4. 根據需要選擇以下選項：

   - **Expand the mural cell mesh（擴張血管壁細胞網格）**：輸入非負的擴張距離，單位與網格一致。
   - **Open the corresponding raw z-stack image for cell structure reference（開啟對應的原始 Z 軸影像堆疊，供參考細胞結構）**：將 `<cell>_fused.tif`、`.tiff`、`.ome.tif` 或 `.ome.tiff` 檔案放在網格所在的資料夾中。

5. 選擇參數和輸出格式，點選 **Add selected（新增所選項目）**。
6. 點選 **Run analysis（執行分析）**，完成互動式三維選取操作。

**Skip this cell（跳過此細胞）** 會在下一個安全的處理階段邊界停止目前細胞的分析。GUI 會嘗試關閉正在使用的 PyVista 視窗；如果 VMTK 或三維選取視窗仍然顯示，請關閉該視窗以完成跳過操作。

**Skip and remove from file list（跳過並從檔案清單中移除）** 還會從輸出資料夾的 `file_list.xlsx` 中移除該細胞。下次瀏覽檔案時會讀取已儲存的清單，因此該細胞仍會被排除。

## 所選結果的匯出

- **Raw data（原始資料）**：在該細胞的輸出資料夾中寫入 `<parameter_id>_raw.json`。
- **Mean（平均值）**、**Median（中位數）** 和 **Standard deviation（標準差）**：寫入該細胞的 `re_extract_properties.json`。此檔案只包含 GUI 中選取的彙整格式。
- 僅選擇原始資料時，不會產生 `re_extract_properties.json`。
- 寫入目前所選結果前，GUI 只會刪除該細胞輸出資料夾中上次執行產生的、已知屬於 Mural-VISTA 的參數結果 JSON 檔案。使用者其他無關的 JSON 檔案會保留。

前處理網格、種子點檔案和衍生 PLY 檔案儲存在所選輸出根目錄下。各細胞的 JSON、pickle、VTU 和 VTP 結果儲存在 `<output folder>/<cell name>/` 中。

程式會保留執行所需的 `*_seeds.json` 和 `*_main_axis_seeds.json`，因為它們快取了互動式中心線選點。網格、pickle 快取、分支資料集和 `workspace.pkl` 也會保留。

## 這是 Windows 應用程式

由於 Qt、VTK 和 VMTK 包含許多原生 DLL，本程式採用單資料夾封裝方式。使用封裝好的程式時無需安裝 Python，但散布時必須將 EXE 與完整的 `dist\Mural-VISTA` 資料夾一起提供。
