[English](README.md) | [简体中文](README.zh-Simp.md) | [繁體中文](README.zh-Trad.md) | [日本語](README.ja.md)

# Mural-VISTA

血管壁細胞と血管の相互作用の評価、およびマルチスケールでの単一細胞のトポロジー・形態解析のためのツール

# 最新バージョン：v2.1.0（261023）

**血管壁細胞と血管の相互作用、および単一細胞のトポロジー・形態解析**

Mural-VISTA は、血管壁細胞の三次元表面形態を解析します。位置合わせ済みの血管メッシュを併せて入力すると、細胞と血管の空間的関係も解析できます。中心線の抽出、分枝と細胞体の分離、形態・トポロジー指標の計算を行い、数値結果と派生メッシュを出力します。

ソースコードによる解析は**対話式**です。VMTK/PyVista の三次元ウィンドウを開き、ユーザーが中心線の端点を選択し、不要なメッシュ領域を除去し、領域分割の結果を確認します。無人実行や、グラフィカル環境のない状態でのバッチ処理を想定したものではありません。

## 入力

Python ファイルの冒頭付近にある `DEFAULT_INPUT_DIR` に、メッシュを保存したフォルダーを指定します。指定フォルダーとそのサブフォルダーから、拡張子が小文字の `.ply` ファイルを検索します。

各データセットのファイル名は、次の形式にしてください。

```text
<dataset>_fused_green.ply    必須：血管壁細胞の表面メッシュ
<dataset>_fused_red.ply      任意：参照血管の表面メッシュ
```

血管壁細胞のメッシュには `<dataset>_fused_gre.ply` という名前も使用できます。例：

```text
input_folder/
├── cell_01_fused_green.ply
├── cell_01_fused_red.ply
├── cell_02_fused_green.ply
└── cell_02_fused_red.ply
```

入力メッシュには、三角形分割された表面を使用してください。同じデータセットの壁細胞メッシュと血管メッシュは、同じ座標系と単位を使用する必要があります。出力される長さ、面積、体積の単位は、入力メッシュの単位に基づきます。

血管メッシュがなくても細胞形態の指標は計算されますが、血管被覆、投影、分枝と血管の関係に関する指標は計算されません。

## 基本的な流れ

検出した各データセットに対して、次の処理を行います。

1. green/`gre` の PLY メッシュを読み込み、VMTK で使用する ASCII 形式の VTP 表面に変換します。
2. ユーザーがメッシュの欠陥部分を除去した後、表面の修復、平滑化、クリーンアップ、細分化を行います。
3. ユーザーが始点と終点を選択し、VMTK の中心線を抽出します。
4. 中心線に基づくチューブモデルを作成します。ユーザーは抽出結果を承認するか、中心線の端点を選び直します。
5. 対話操作で、分枝、主軸または一次突起、細胞体を分離します。
6. 分枝、分枝樹、細胞体、主軸、細胞全体の指標を計算します。
7. 血管メッシュがある場合は、細胞と血管の被覆、投影、角度の指標を計算します。
8. 数値結果の JSON ファイル、派生メッシュ、中心線データセット、次回以降に再利用できるキャッシュを保存します。

## 出力

ソースプログラムを既定の設定で実行すると、結果は入力フォルダーに保存されます。別の Python プログラムから呼び出す場合は、`AnalysisConfig.output_dir` で出力ルートフォルダーを指定することもできます。

出力ルートフォルダーには、次のファイルが保存されます。

- `file_list.xlsx`：検出したデータセットの一覧。
- `<green_stem>.vtp` や `<green_stem>_clipped.ply` など、VMTK 対応メッシュおよび前処理済みメッシュ。
- 保存した中心線の選択点：`<green_stem>_seeds.json` と `<green_stem>_main_axis_seeds.json`。
- 分枝、細胞体、主軸領域の派生 PLY 表面。

各データセットには、専用のフォルダーも作成されます。

```text
<output>/<dataset>/
├── re_extract_properties.json       指標の統合サマリー
├── branches_properties.json         各分枝の指標
├── cell_body_properties.json        細胞体の指標
├── main_axis_properties.json        主軸の指標
├── branch_*.json                    分枝および血管との関係の数値
├── cl_tree_*.json                   分枝樹の数値
├── clipped_mesh.pkl                 再利用可能な領域分割キャッシュ
├── workspace.pkl                    保存した解析ワークスペース
├── branches_surface/                各分枝の表面ファイル（.vtu）
├── branches_centerline/             中心線ファイル（.vtu）
└── branches_tube/                   各分枝のチューブファイル（.vtp）
```

出力指標には、分枝の長さ、直径、曲率、捩率、蛇行度、表面積、体積、分枝樹の構造、細胞体の体積、面積、球形度、ソリディティ（充実度）、主軸、細胞主軸の幾何学的特徴、細胞全体の形状とトポロジーが含まれます。赤色メッシュを入力した場合は、血管壁細胞と血管の空間的関係に関する指標も出力されます。

再実行時には、互換性のある切り抜き済みメッシュ、選択済みシード点、領域分割キャッシュ、中心線が再利用されます。対応する対話操作をやり直す必要がある場合にのみ、関連するキャッシュを削除してください。

## すぐに使える Windows GUI

64 ビット版 Windows 向けの GUI も、`Mural-VISTA_v2.1.0_Windows_x64.zip` として提供しています。Python と必要な科学計算ライブラリが同梱されているため、Python や Conda をインストールする必要はありません。

使用方法：

1. Mural-VISTA の GitHub Release または Zenodo のレコードから ZIP ファイルをダウンロードします。
2. ZIP ファイルを**すべて展開**します。
3. `Mural-VISTA.exe` を起動します。

`Mural-VISTA.exe` と `_internal` フォルダーは、必ず同じ場所に置いてください。EXE 単体でのコピーや配布はできません。GUI では、フォルダーの参照、データセットの検索、進捗表示、パラメーターや出力内容の選択ができます。解析の主要な処理では、引き続き VMTK/PyVista の対話式ウィンドウが開きます。

## Python で実行する

**動作環境**

Python 3.10 と、`envi_lib_list.txt` に記載された環境でテストしています。主な外部ライブラリは次のとおりです。

- VTK、PyVista。
- VMTK 1.5.0。本リリースに含まれる修正版 `vmtkcenterlines.py` を使用します。
- NumPy、pandas、SciPy、NetworkX、trimesh、PyMeshFix、GUDHI。
- openpyxl。pandas が `file_list.xlsx` を書き出す際に使用します。

グラフィカルなデスクトップ環境が必要です。長時間の解析を始める前に、次のコマンドで環境を確認してください。

```bash
python -c "import vtk, pyvista, vmtk, numpy, pandas, scipy, networkx, trimesh, pymeshfix, gudhi, openpyxl"
```

**VMTK の修正版について**

Mural-VISTA は、VMTK の `vmtkcenterlines.py` の**修正版**を使用します。
（[VMTK の元のファイル](https://github.com/vmtk/vmtk/blob/master/vmtkScripts/vmtkcenterlines.py)）
この修正により、終点を選択する際にも始点のシードを見分けやすくし、選択した始点と終点の座標を取得できるようにしています。Mural-VISTA は、その座標を保存して再利用します。

対応する修正版ファイルは、本ソフトウェアとともに GitHub および Zenodo のアーカイブで配布しています。解析スクリプトと**同じ Mural-VISTA リリース**に含まれるファイルを使用してください。

ソースコードを使用する場合：

1. Python 環境に VMTK をインストールします。
2. パッケージの保存先を確認します。

   ```bash
   python -c "import pathlib, vmtk; print(pathlib.Path(vmtk.__file__).resolve().parent)"
   ```

3. インストール済みの `vmtkcenterlines.py` をバックアップします。
4. 本リリースに含まれる修正版 `vmtkcenterlines.py` で置き換えます。ファイル名は変更しないでください。

**ソースプログラムの実行**

1. 準備した Python 環境を有効化します。
2. `Mural-VISTA_v2-1-0_261023.py` の `DEFAULT_INPUT_DIR` を編集します。
3. ターミナルからプログラムを起動します。

   ```bash
   python Mural-VISTA_v2-1-0_261023.py
   ```

4. ターミナルを開いたまま、各段階の対話式三次元操作を完了してください。進捗と現在のデータセット名はターミナルに表示されます。

## 引用

Mural-VISTA が研究に役立ちましたら、**引用をいただければ幸いです**。

次の内容をご引用ください。

1. 実際に使用した Mural-VISTA のソフトウェアバージョン。
2. 関連する Mural-VISTA の研究論文：

   Zeng, H., et al.,
   Mural-VISTA: A tool for mural cell-vessel interaction assessment and multiscale single-cell topo-morphological analysis.
   bioRxiv, 2026.
   DOI: 10.64898/2026.08.27.747487

3. VMTK：

   Izzo, R., et al.,
   The Vascular Modeling Toolkit: A Python Library for the Analysis of Tubular Structures in Medical Images.
   Journal of Open Source Software, 2018. 3(25): p. 745.
   DOI: 10.21105/joss.00745

## プロジェクトのリンク

- [GitHub リポジトリとリリース](https://github.com/HedeleZeng/Mural-VISTA.git)
- Zenodo アーカイブ：10.5281/zenodo.22124716
- [bioRxiv アーカイブ](https://www.biorxiv.org/content/10.64898/2026.08.27.747487v1)

  Zeng, H., et al., Mural-VISTA: A tool for mural cell-vessel interaction assessment and multiscale single-cell topo-morphological analysis. bioRxiv, 2026.

## ライセンス

Copyright © 2026 Hedele Zeng.

特に記載のない限り、本プロジェクトで開発した独自のコードは BSD 3-Clause License に基づいて提供します。

本プロジェクトでは、それぞれのライセンスに基づいて配布されるサードパーティ製ソフトウェアを使用し、明記された場合には同梱しています。サードパーティ製コンポーネントには元の著作権表示とライセンス条件が引き続き適用され、BSD 3-Clause License に変更されることはありません。

詳細は [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) をご覧ください。

一部の機能は、PyMeshFix/MeshFix や、GUDHI AlphaComplex が使用する GPLv3 の依存ライブラリなど、GPL ライセンスのソフトウェアに依存しています。本ソフトウェアを組み合わせた形、または同梱した形で再配布する場合、再配布者は適用されるサードパーティのライセンス条件を遵守する責任を負います。
