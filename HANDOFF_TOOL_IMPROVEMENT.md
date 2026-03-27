# VRM2GmodPlayermodel ツール改善 引継書

## この文書の目的
この引継書は、VRM2GmodPlayermodelアドオンを**様々なVRM/VRCモデルでテストし、問題を発見・修正してツールとしての完成度を高める**ための次の会話に向けた完全な技術資料です。

---

## 1. プロジェクト概要

**VRM/VRCモデル → Garry's Mod プレイヤーモデル ワンクリック変換ツール**

- Blender 5.0/5.1 アドオン（Python）
- 開発ディレクトリ: `R:\AI\VRM2GmodPlayermodel\`
- Blender: `G:\SteamLibrary\steamapps\common\Blender\blender.exe`（Steam版 5.1）
- studiomdl: `R:\SteamLibrary\steamapps\common\GarrysMod\bin\studiomdl.exe`
- GMod: `R:\SteamLibrary\steamapps\common\GarrysMod\garrysmod\`

### 同期先（コード修正後は3箇所全てに反映が必要）
```
開発: R:\AI\VRM2GmodPlayermodel\
5.0:  C:\Users\Pescorr\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\VRM2GmodPlayermodel\
5.1:  C:\Users\Pescorr\AppData\Roaming\Blender Foundation\Blender\5.1\scripts\addons\VRM2GmodPlayermodel\
```

同期コマンド:
```bash
cp -r "R:/AI/VRM2GmodPlayermodel/data" "R:/AI/VRM2GmodPlayermodel/operators" "R:/AI/VRM2GmodPlayermodel/ui" "R:/AI/VRM2GmodPlayermodel/utils" "R:/AI/VRM2GmodPlayermodel/__init__.py" "R:/AI/VRM2GmodPlayermodel/preferences.py" "C:/Users/Pescorr/AppData/Roaming/Blender Foundation/Blender/5.0/scripts/addons/VRM2GmodPlayermodel/"
cp -r "R:/AI/VRM2GmodPlayermodel/data" "R:/AI/VRM2GmodPlayermodel/operators" "R:/AI/VRM2GmodPlayermodel/ui" "R:/AI/VRM2GmodPlayermodel/utils" "R:/AI/VRM2GmodPlayermodel/__init__.py" "R:/AI/VRM2GmodPlayermodel/preferences.py" "C:/Users/Pescorr/AppData/Roaming/Blender Foundation/Blender/5.1/scripts/addons/VRM2GmodPlayermodel/"
```

---

## 2. 変換パイプライン（全8ステップ）

```
Step 1:   bone_remap      VRM骨格 → ValveBiped（68ボーン）変換
Step 2:   mesh_prepare     メッシュ結合・三角面化・スケール×39.37・ウェイト制限(3)
Step 2.5: A-pose変換       T-pose → Source Engine A-pose
────────── ここまでが破壊的変換（再実行不可）──────────
Step 3:   SMD export       参照メッシュSMD書き出し
Step 3.5: VTA export       Shape Key → flex VTA書き出し（表情）
Step 4:   Proportion Trick 投影スケルトン方式SMD生成
Step 5:   Material convert テクスチャ → VMT/VTF
Step 6:   Physics generate 17コリジョンボックス生成
Step 7:   QC generate      Source Engineコンパイル設定
Step 7.5: .blend保存       compile/ディレクトリに保存
Step 8:   studiomdl compile MDLコンパイル
Step 8.5: Lua生成 + Gmodコピー
```

### 重要な技術的詳細

#### 投影スケルトン方式（Proportion Trick）
- `reference.smd` = male_07標準骨格（HL2市民モデル）
- `proportions.smd` = VRMモデルの実際の骨格
- QC: `$animation a_proportions "proportions" subtract a_reference 0` → delta → `$sequence proportions a_proportions predelta autoplay`
- ragdollシーケンスは**必ず"reference"を使用**（"proportions"だとpredelta二重適用で腕が崩壊）

#### SMD座標系
- Blender (X=右, Y=奥, Z=上) → SMD (X=前, Y=左, Z=上)
- スケール: Blender 1.0m = Source 39.3701 units

#### flexcontroller QC構文（重要！）
```qc
$model "body" "model.smd" {
    flexfile "model_flex.vta" {
        defaultflex frame 0
        flex "blink" frame 1
        flex "aa" frame 2
    }
    flexcontroller Eyes blink "range" 0 1
    flexcontroller Phoneme aa "range" 0 1
    %blink = blink
    %aa = aa
}
```
- グループ名: `Eyes`（瞬き・視線）, `Phoneme`（母音）, `Expressions`（感情）
- **注意**: `flexcontroller range 0 1 "name"` は間違い。正しくは `flexcontroller Group name "range" 0 1`

---

## 3. 現在の機能一覧

### オペレータ
| bl_idname | ファイル | 機能 |
|---|---|---|
| `vrm2gmod.bone_remap` | `operators/bone_remap.py` | VRM→ValveBipedボーンリマップ |
| `vrm2gmod.mesh_prepare` | `operators/mesh_prepare.py` | メッシュ結合・準備 |
| `vrm2gmod.material_convert` | `operators/material_convert.py` | マテリアル変換 |
| `vrm2gmod.physics_generate` | `operators/physics_generate.py` | 物理モデル生成 |
| `vrm2gmod.qc_generate` | `operators/qc_generate.py` | QCファイル生成 |
| `vrm2gmod.convert_full` | `operators/convert_full.py` | フルパイプライン |
| `vrm2gmod.re_export` | `operators/convert_full.py` | 修正済み再出力（Step 3-8のみ） |
| `vrm2gmod.select_bone_weight` | `operators/weight_paint.py` | ウェイトペイント用ボーン選択 |
| `vrm2gmod.detect_shape_keys` | `operators/flex_detect.py` | Shape Key検出 |
| `vrm2gmod.flex_deselect_all` | `operators/flex_detect.py` | flex全解除 |
| `vrm2gmod.flex_select_standard` | `operators/flex_detect.py` | VRM標準のみ選択 |

### UIパネル
| パネル | 内容 |
|---|---|
| `VRM2GMOD_PT_MainPanel` | メイン設定・変換ボタン |
| `VRM2GMOD_PT_PathSettings` | studiomdl/Gmodパス設定（折りたたみ） |
| `VRM2GMOD_PT_WeightPaint` | ボーン別ウェイトペイント選択（折りたたみ） |
| `VRM2GMOD_PT_FlexExport` | 表情エクスポート設定（折りたたみ） |

### 表情システム（Flex）
- Shape Key検出 → プルダウンでGMod表情ターゲットを割当
- プルダウン選択肢: blink(3), emotions(6), visemes(5), look(4), カスタム, スキップ
- VRM標準名（happy, blink等）は自動マッチ
- 日本語名（まばたき、あ等）は手動割当が必要
- GMod上限: 96個のflex controller

---

## 4. テスト済みモデルと結果

### kachua（VRMモデル）
- パス: `R:\SteamLibrary\...\addons\kachua\kachua\Catchua.vrm`
- 出力: `R:\SteamLibrary\...\addons\kachua\`
- **結果**: 骨格・テクスチャ正常、表情動作確認済み（瞬き・口パク）
- **既知の問題**: 親指のウェイトが伸びる（ThumbMetacarpal→Finger0マージによる）
- **修正履歴**: テクスチャ統一問題（日本語マテリアル名→衝突回避ナンバリング）、Pelvis原点問題（tail_local使用）

### laguna（VRC/.blendモデル）
- パス: `R:\SteamLibrary\...\addons\laguna\laguna_v1.01\blend\laguna_v1.00a.blend`
- 出力: `R:\SteamLibrary\...\addons\laguna\`
- **結果**: 完璧。表情も正常動作

### バッチコンバートスクリプト（GUIなしでテスト可能）
```bash
"G:/SteamLibrary/steamapps/common/Blender/blender.exe" --background --python "R:/AI/VRM2GmodPlayermodel/batch_convert.py" -- "<VRMパス>" "<モデル名>" "<出力先>"
```

---

## 5. 既知の問題と改善候補

### 高優先度
| 問題 | 原因 | 対策案 |
|---|---|---|
| 親指の伸び（kachua） | ThumbMetacarpal→ThumbProximalマージで手のひら頂点が指に引っ張られる | Metacarpal→Handに変更、または距離ベース分配 |
| 日本語Shape Keyが自動認識されない | `get_flex_target()`がVRM英語名のみマッチ | 日本語→flex自動マッピング辞書追加 |
| パイプライン中のShape Key名変化 | mesh_prepareでShape Key名が変わる可能性 | パイプライン内で再検出＋ユーザー割当保持 |

### 中優先度
| 問題 | 原因 | 対策案 |
|---|---|---|
| 1頂点のウェイト数が3超過 | VRMは4+ボーンウェイト対応 | mesh_prepareで3に制限（実装済みだが検証必要） |
| 微小ウェイト（<0.01）のアーティファクト | ウェイト正規化不足 | 微小ウェイト除去＋再正規化 |
| マージ後のウェイト合計が1.0超過 | マージ時の正規化不足 | マージ後に全頂点ウェイト正規化 |

### 低優先度・将来目標
- VRC Bodygroupサポート（服装切替）
- eyeポーザー（GMod標準の目線追従）
- 自動weight paint改善（IK連動の自動ウェイト修正）

---

## 6. 重要な教訓（過去の失敗から学んだこと）

### studiomdlコンパイル後のファイル同期（最重要）
studiomdlは `garrysmod/models/` にコンパイル結果を出力する。**アドオンの `addons/*/models/` にも手動コピーが必要**。Gmodはアドオンファイルを優先ロードするため、アドオン側が古いと修正が反映されない。

### Blender 5.0と5.1の同期
コード修正後は開発+5.0+5.1の**3箇所**に反映が必要。5.1ディレクトリへのコピーを忘れると修正が反映されない（過去にこれで数時間ロス）。

### VTA skeletonセクションのendframe制限
GMod版studiomdlのVTAパーサーでは、skeletonセクションにflexフレーム数分のtimeエントリが必要。不足すると`Frame MdlError`で中断。

### A-pose変換とShape Keyの関係
A-pose変換（`apply_a_pose`）時にBasis Shape Keyは更新されるが、他のShape Keyは更新されない場合がある。VTA生成時にShape Keyのdeltaを計算する際、Basis→A-pose変換が正しく反映されていないと、flex適用時にT-poseグリッチが発生する。現在のコードでは修正済み。

---

## 7. ファイル構成

```
R:\AI\VRM2GmodPlayermodel\
├── __init__.py              # モジュール登録
├── preferences.py           # アドオン設定（studiomdlパス等）
├── operators/
│   ├── bone_remap.py        # VRM→ValveBipedボーンリマップ
│   ├── mesh_prepare.py      # メッシュ結合・準備
│   ├── material_convert.py  # マテリアル変換（VMT/VTF）
│   ├── physics_generate.py  # 物理モデル生成
│   ├── qc_generate.py       # QCファイル生成
│   ├── convert_full.py      # フルパイプライン + 再出力
│   ├── weight_paint.py      # ウェイトペイント選択
│   └── flex_detect.py       # Shape Key検出・flex割当
├── ui/
│   └── panel.py             # UIパネル（設定、パス、ウェイト、flex）
├── data/
│   ├── bone_mapping.py      # ボーンマッピング・階層・参照位置
│   ├── flex_mapping.py      # 表情マッピング・プルダウン定義
│   ├── physics_presets.py   # 物理ボックス定義
│   ├── qc_templates.py      # QCテンプレート
│   └── vmt_templates.py     # VMTテンプレート
├── utils/
│   ├── bone_utils.py        # ボーンユーティリティ（find_armature等）
│   ├── smd_export.py        # SMD/VTA書き出し（最も複雑）
│   ├── studiomdl_compile.py # studiomdlラッパー
│   ├── pose_correction.py   # A-pose変換
│   ├── lua_generate.py      # Luaスクリプト生成
│   ├── vtf_convert.py       # VTF変換ラッパー
│   └── vtf_writer.py        # Pure Python VTF書き出し
├── tests/                   # テスト・診断スクリプト
├── batch_convert.py          # バッチVRM変換スクリプト
└── batch_convert_blend.py    # バッチ.blend変換スクリプト
```

---

## 8. 今回の会話での成果（2026-03-23）

### 指ウェイト簡略化機能（実装済み・テスト済み）

3つの指モードを追加し、GMod内で動作確認済み:

| モード | 動作 | デフォルト |
|---|---|---|
| **簡略（1関節）** | 4指は1関節、親指はHandに統合 | ✅ デフォルト |
| **詳細（3関節）** | 従来動作。品質は高いが変形リスク | |
| **固定（パー）** | 全指ウェイト→Hand。常にパー | |

**変更ファイル:**
- `data/bone_mapping.py` — `FINGER_SIMPLE_MERGE`, `FINGER_FROZEN_MERGE` 定数
- `utils/bone_utils.py` — `simplify_finger_weights()` 関数
- `ui/panel.py` — `finger_mode` EnumProperty + UIドロップダウン
- `operators/bone_remap.py` — Step 9.5として呼出

**親指の伸び**: SIMPLEモードでもまだ若干伸びる場合がある。完全解決には親指ウェイトをHandに統合する変更が必要だが、まだ未適用（`FINGER_SIMPLE_MERGE`の末尾にFinger0→Hand統合を追加すれば解決）。

### Blender Source Tools修正
`io_scene_valvesource/GUI.py` L439: `type='GRID'` → `type='DEFAULT'`（Blender 5.1互換性）

### Shape Key検出修正
`flex_detect.py`: 全メッシュを再帰的に探索するよう修正。子オブジェクト（MorphBase.baked等）のShape Keyも正しく検出。

---

## 8.5 マテリアル変換パイプライン改善（2026-03-23 実装済み）

### 解決した問題
- 日本語マテリアル名 → studiomdl/VTFTools失敗 → **Phase 1で解決済み**（連番命名）
- Blenderがテクスチャパスを見失う → 紫一色 → **Phase 2で解決**（近隣検索+単色フォールバック）
- SMDとVMTのマテリアル名不一致 → GModで紫 → **Phase 1で解決済み**（共通モジュール）
- テクスチャのないマテリアル（単色）→ GModで紫 → **Phase 2で解決**（4×4 PNG自動生成）

### 実装内容（3フェーズ全て完了）

**Phase 1: マテリアル名統一 ✅ 前回実装済み**
- `utils/material_names.py` — 唯一の名前マッピング情報源
- 連番命名: `model_00`, `model_01`... 衝突・Unicode問題ゼロ

**Phase 2: テクスチャ取得改善 ✅ 今回実装**
- `utils/texture_utils.py` 新規作成:
  - `search_texture_nearby()` — 近隣ディレクトリでテクスチャファイルを検索
  - `extract_base_color()` — マテリアルノードから単色を抽出
  - `generate_solid_color_png()` — Pure Python 4×4 PNG生成（75バイト）
  - `check_texture_status()` — マテリアルのテクスチャ状態チェック
- `operators/material_convert.py` 改修:
  - `_save_texture()` Strategy 5追加: 近隣ディレクトリ検索
  - `_process_material()`: テクスチャ解決順序を3段階に整理
    1. ユーザー手動オーバーライド
    2. ノードツリーからの抽出（既存）
    3. 単色フォールバック（4×4 PNG自動生成）
  - `_detect_alpha_mode()`: アルファ検出を独立メソッドに分離
  - `execute()`: テクスチャオーバーライドマップ構築 + 変換後ステータス更新

**Phase 3: 手動テクスチャ割り当てUI ✅ 今回実装**
- `ui/panel.py`:
  - `VRM2GMOD_MaterialItem` PropertyGroup（ステータス・オーバーライドパス・単色カラー）
  - `VRM2GMOD_OT_ScanMaterials` オペレータ（テクスチャスキャン）
  - `VRM2GMOD_PT_MaterialOverview` パネル（マテリアル概要表示）
  - ステータスアイコン: ✓ OK / ⚠ MISSING / 🎨 SOLID / 📁 OVERRIDE
  - `override_texture` FILE_PATH プロパティで手動PNG指定可能

### テスト結果（kachuaモデル）
- 11マテリアル全てにVMT/VTF生成成功
- 2つの単色マテリアル自動検出・PNG生成:
  - `kachua_test_01`: #FFFFFF（白、おそらく白目/ハイライト）
  - `kachua_test_04`: #140905（暗赤茶、おそらく口内/影）

### バックアップ
- `R:\AI\VRM2GmodPlayermodel_backup_20260323_pre_material\` — Phase 1実装前
- `R:\AI\VRM2GmodPlayermodel_backup_20260323_pre_phase2\` — Phase 2/3実装前

---

## 8.6 ボーン修正・診断システム（2026-03-23 実装済み）

### 改善1: Pelvis XY自動補正 ✅
- `utils/smd_export.py`: `_compute_bone_offsets()` と `_write_skeleton_projected()` でPelvis XY成分を0にクランプ
- VRMのHipsボーンが原点から前方/側方にオフセットしている場合でも、Source Engine上でモデルが中央に配置される
- Pescorrモデルの猫背問題を根本解決（Y=10.28SU→0）

### 改善2: body_type FEMALE対応 ✅
- `data/bone_mapping.py`: `INCLUDEMODEL_PATHS` → `INCLUDEMODEL_PATHS_MALE` / `INCLUDEMODEL_PATHS_FEMALE` に分離
- `operators/qc_generate.py`: `body_type` プロパティに応じてアニメーションセット（`m_anm.mdl` vs `f_anm.mdl`等）を切替
- VRMモデル（大半がfemale体型）で適切なアニメーションセット使用可能に
- 指の姿勢もfemaleアニメーションで自然になる可能性

### 改善3: .blend欠損ボーン安全策 ✅
- `operators/bone_remap.py`: `_rescue_missing_limb_bones()` メソッド追加（Step 6.5）
- .blendソースからの変換でVRMメタデータがなく、パターン推測でUpperArm/Forearm/Thigh/Calfが未検出の場合に自動復元
- ボーン階層構造からチェーン候補を特定し、ValveBiped名にリネーム
- `_find_chain_candidate()` + `_subtree_contains()` で正しいチェーンを特定

### 改善4: 診断レポートシステム ✅
- `utils/conversion_diagnostics.py` 新規作成: `run_diagnostics()` 関数
  - ボーン完全性チェック（必須21本）
  - 階層一致チェック
  - プロポーション検証（male_07比30%〜200%）
  - Pelvis位置チェック
  - ウェイト割当チェック
- `operators/convert_full.py`: パイプライン最後に診断呼び出し + 結果保存
- `ui/panel.py`: `VRM2GMOD_PT_Diagnostics` パネル + `VRM2GMOD_DiagnosticItem` PropertyGroup

### テスト結果
- kachua VRM (FEMALE): QCにf_anm.mdl/female_shared.mdl正常出力、Pelvis XY=0,0確認
- Blender 5.1アドオン登録: 全新プロパティ・オペレータ正常

### バックアップ
- `R:\AI\VRM2GmodPlayermodel_backup_20260323_pre_bone_fix\`

---

## 9. 次のタスク候補

### 高優先度
| 問題 | 対策案 |
|---|---|
| 親指の伸び（kachua） | `FINGER_SIMPLE_MERGE`にFinger0→Hand統合を追加 |
| Quiple .blendの再テスト | 改善3適用後に.blendから再変換テスト |
| Pescorr VRMの再テスト | 改善1適用後に猫背解消確認（GModで実動作テスト） |

### 中優先度
| 問題 | 対策案 |
|---|---|
| 指のA-pose補正 | `pose_correction.py`に指屈曲追加（DETAILED時のみ） |
| VTFファイルサイズ最適化 | DXT5圧縮対応（VTFCmd未使用時はBGRA8888で巨大） |
| 新しいVRM/VRCモデルでのテスト | batch_convert.pyで複数モデルテスト |

### 低優先度
- VRC Bodygroupサポート
- eyeポーザー（目線追従）
- 自動weight paint改善

---

## 10. 改善テストの進め方

1. 新しいVRM/VRCモデルを用意
2. `batch_convert.py`でバッチ変換（Blender GUIなしでテスト可能）
3. GMod上でモデルを確認
4. 問題を特定 → 該当オペレータのコードを修正
5. 3箇所に同期 → 再テスト

### テストチェックリスト
- [ ] 骨格が正常（T-poseにならない、手足が正しい位置）
- [ ] テクスチャが正しい（紫にならない、割当が正しい）
- [ ] 表情が動作する（瞬き、口パク）
- [ ] ラグドールが動作する（物理が崩壊しない）
- [ ] プレイヤーモデルとして選択可能（Luaスクリプト）
- [ ] 指が正常（伸びていない）
