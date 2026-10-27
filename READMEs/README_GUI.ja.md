[English](../README_GUI.md) | [简体中文](README_GUI.zh-Simp.md) | [繁體中文](README_GUI.zh-Trad.md) | [日本語](README_GUI.ja.md)

# Mural-VISTA GUI

Mural-VISTA GUI は、PySide6 を使用したデスクトップ用のグラフィカルインターフェースです。

## GUI の操作手順

1. `<cell>_fused_green.ply`（または `_fused_gre.ply`）を含む入力フォルダーを選択します。必要に応じて `<cell>_fused_red.ply` も同じフォルダーに置きます。
2. 出力フォルダーを選択し、**Explore files（ファイルを検索）** をクリックします。
3. **Start number（開始番号）** を入力します。番号は 0 から始まります。
4. 必要に応じて、次のオプションを選択します。

   - **Expand the mural cell mesh（血管壁細胞のメッシュを拡張）**：0 以上の拡張距離を入力します。単位はメッシュと同じです。
   - **Open the corresponding raw z-stack image for cell structure reference（細胞構造の参照用に対応する元の Z スタック画像を開く）**：`<cell>_fused.tif`、`.tiff`、`.ome.tif`、または `.ome.tiff` ファイルを、メッシュと同じフォルダーに置きます。

5. パラメーターと出力形式を選択し、**Add selected（選択項目を追加）** をクリックします。
6. **Run analysis（解析を実行）** をクリックし、対話式の三次元選択操作を完了します。

**Skip this cell（この細胞をスキップ）** を選択すると、次の安全な処理段階の区切りで現在の細胞の解析が停止します。GUI は使用中の PyVista ウィンドウを閉じようとします。VMTK または三次元選択ウィンドウが残っている場合は、そのウィンドウを閉じてスキップを完了してください。

**Skip and remove from file list（スキップしてファイル一覧から削除）** は、出力フォルダーの `file_list.xlsx` からもその細胞を削除します。次回のファイル検索では保存済みの一覧を読み込むため、その細胞は引き続き対象から除外されます。

## 選択した結果の出力

- **Raw data（生データ）**：その細胞の出力フォルダーに `<parameter_id>_raw.json` を保存します。
- **Mean（平均値）**、**Median（中央値）**、**Standard deviation（標準偏差）**：その細胞の `re_extract_properties.json` に保存します。このファイルには、GUI で選択した集計形式のみが含まれます。
- 生データのみを選択した場合は、`re_extract_properties.json` を作成しません。
- 現在の選択結果を保存する前に、その細胞の出力フォルダーにある前回のパラメーター結果 JSON のうち、Mural-VISTA が生成する既知のファイルのみを削除します。関係のないユーザーの JSON ファイルは保持します。

前処理済みメッシュ、シード点ファイル、派生 PLY ファイルは、選択した出力ルートフォルダーに保存します。各細胞の JSON、pickle、VTU、VTP の結果は、`<output folder>/<cell name>/` に保存します。

処理に使用する `*_seeds.json` と `*_main_axis_seeds.json` は、対話操作で選択した中心線の点をキャッシュするため保持します。メッシュ、pickle キャッシュ、分枝データセット、`workspace.pkl` も保持します。

## Windows 用アプリケーションです

Qt、VTK、VMTK には多数のネイティブ DLL が含まれるため、単一フォルダー形式でパッケージ化しています。パッケージ版の使用時に Python のインストールは不要ですが、配布時には EXE とともに `dist\Mural-VISTA` フォルダー全体を含める必要があります。
