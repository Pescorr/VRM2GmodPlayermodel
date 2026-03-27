# PescorrV2（PesmatV）表情追加アップグレード 引継書

## この文書の目的
ユーザーの長年愛用しているGModプレイヤーモデル「PescorrV2」に**表情（flex animation）を追加する**ための完全な技術資料です。このモデルはVRM2GmodPlayermodelツールで変換したものではなく、手動でGModにインポートされた既存モデルです。

---

## 1. モデル情報

### ファイルパス
| 項目 | パス |
|---|---|
| Blenderファイル | `R:\SteamLibrary\steamapps\common\GarrysMod\garrysmod\addons\pescorr\decompile\pesmatV\pescorrV2.blend` |
| デコンパイル済みSMD | `R:\SteamLibrary\steamapps\common\GarrysMod\garrysmod\addons\pescorr\decompile\pesmatV\pesmat.smd` |
| デコンパイル済みQC | `R:\SteamLibrary\steamapps\common\GarrysMod\garrysmod\addons\pescorr\decompile\pesmatV\pesmat.qc` |
| 物理SMD | `R:\SteamLibrary\steamapps\common\GarrysMod\garrysmod\addons\pescorr\decompile\pesmatV\pm_physics.smd` |
| マテリアル（VMT/VTF） | `R:\SteamLibrary\steamapps\common\GarrysMod\garrysmod\pescorrserver_2926346656\materials\models\pesmat\` |
| アドオン出力先 | `R:\SteamLibrary\steamapps\common\GarrysMod\garrysmod\addons\pescorr\` |
| studiomdl | `R:\SteamLibrary\steamapps\common\GarrysMod\bin\studiomdl.exe` |
| GMod game_dir | `R:\SteamLibrary\steamapps\common\GarrysMod\garrysmod` |

### モデル構造（Blender内）
```
pesmat (Collection)
├── pes_bone (Armature) — ValveBiped 68ボーン（既にGMod用に設定済み）
│   ├── pesmat.002 (Mesh) — 体メッシュ、2346頂点、Shape Keyなし
│   ├── 体.001 (Mesh) — 頭メッシュA、6521頂点、34 Shape Keys
│   └── 体.006 (Mesh) — 頭メッシュB、4187頂点、34 Shape Keys
└── smd_bone_vis (Mesh) — ボーン可視化用（親なし、無視してよい）
```

### 重要な注意点
- **体と頭が別メッシュ**になっている（VRM2GmodPlayermodelツールでは統合を前提としているため、そのままでは使えなかった）
- 体メッシュ（pesmat.002）にはShape Keyがない
- 頭メッシュ（体.001, 体.006）にShape Keyがある
- VRM2GmodPlayermodelツールの通常パイプラインは使わない。このモデル専用のスクリプトが必要

### オブジェクトのトランスフォーム（重要！）
```
pesmat.002:  scale=(1.0, 1.0, 1.0),  location=(0, 0, 0)
体.001:      scale=(87.15, 87.15, 87.15), location=(0, -13.38, 0)
体.006:      scale=(87.15, 87.15, 87.15), location=(0, -13.38, 0)
```
- 体.001と体.006は**スケール87.15**で、Y=-13.38のオフセットがある
- ただし`matrix_world`は体.001で1.0（parent_inverseがスケールを打ち消している）
- 体.006では`matrix_world`の対角が87.15（parent_inverseが異なる）
- この非一貫性がBlender→SMD座標変換の障害になった

### マテリアル構成
SMD内のマテリアル名: `2.001`, `3.001`, `4.001`, `5.001`, `6.001`
VMTファイル名: `2.vmt`, `3.vmt`, `4.vmt`, `5.vmt`, `6.vmt`
QCの`$cdmaterials`: `"models\pesmat\"`

studiomdlはSMDのマテリアル名から`.001`を除去してVMTを検索する。

### Shape Key一覧（体.001, 体.006共通、34個）
```
Basis（参照ポーズ）
--- 口 ---
aa, ih, oh, ou, E
--- 目 ---
目閉じ, 半目, 笑い
--- 眉 ---
困り眉毛, 真剣
--- その他多数 ---
```

### 推奨flex割当
| Shape Key名 | flex名 | グループ |
|---|---|---|
| aa | aa | Phoneme |
| ih | ih | Phoneme |
| oh | oh | Phoneme |
| ou | ou | Phoneme |
| E | ee | Phoneme |
| 目閉じ | blink | Eyes |
| 半目 | blink_right | Eyes |
| 笑い | happy | Expressions |
| 困り眉毛 | sad | Expressions |

---

## 2. 正しいアプローチ（前回の教訓から）

### やるべきこと
1. **Blenderでメッシュを統合**（体.001 + 体.006 + pesmat.002 → 1つのメッシュ）
2. **統合メッシュからSMDとVTAを両方出力**（頂点順序が自動一致）
3. **QCにflexセクションを追記**（元のQCベースで`$bodygroup`→`$model`+flexfileに変更）
4. **studiomdlでコンパイル**
5. **マテリアルがズレていたらVMTを修正**（後から直せる）

### やってはいけないこと
- ❌ 元のSMDをそのまま使いつつVTAだけ別で生成する → 頂点順序の一致が困難
- ❌ Blender頂点→SMD頂点の座標変換マッチング → スケール/parent_inverseの問題で複雑化
- ❌ マテリアル問題とVTA問題を同時に解決しようとする → 分けて対処

### マテリアル問題の対処法
メッシュ統合後にSMDを再出力すると、マテリアルスロットの順序が変わりマテリアル割当がズレる。
対処: VMTファイルの`$basetexture`参照先を入れ替えるだけで直る。モデルの再コンパイルは不要。

正解の見た目:
- グレーの肌
- 赤い目
- 青い服
- 白い髪

---

## 3. メッシュ統合時の注意点

### Shape Keyの扱い
- pesmat.002にはShape Keyがない
- 体.001と体.006にはShape Keyがある
- Blenderで結合すると、Shape KeyのないメッシュにはBasisが自動追加され、他のShape Keyではdelta=0になる
- これは正常動作（体のShape Keyは変化なし、頭のShape Keyだけ動く）

### スケールの統一
- 結合前に全メッシュのTransformをApply（Ctrl+A → All Transforms）する必要がある可能性
- 体.001/体.006のscale=87.15を適用してから結合しないとメッシュがズレる

### 結合の手順
1. 全メッシュを選択
2. 体.001（Shape Keyがある方）をアクティブに設定
3. Ctrl+J で結合
4. 結合後のメッシュからSMD + VTAを出力

---

## 4. QCの修正箇所

元のQC（`pesmat.qc`）から変更する部分:

### 変更前（表情なし）
```qc
$bodygroup "TallBody"
{
    studio "pesmat.smd"
}
```

### 変更後（表情あり）
```qc
$model "TallBody" "pesmat.smd" {
    flexfile "pesmat_flex.vta" {
        defaultflex frame 0
        flex "aa" frame 1
        flex "ih" frame 2
        flex "oh" frame 3
        flex "ou" frame 4
        flex "ee" frame 5
        flex "blink" frame 6
        flex "blink_right" frame 7
        flex "happy" frame 8
        flex "sad" frame 9
    }

    flexcontroller Phoneme aa "range" 0 1
    flexcontroller Phoneme ih "range" 0 1
    flexcontroller Phoneme oh "range" 0 1
    flexcontroller Phoneme ou "range" 0 1
    flexcontroller Phoneme ee "range" 0 1
    flexcontroller Eyes blink "range" 0 1
    flexcontroller Eyes blink_right "range" 0 1
    flexcontroller Expressions happy "range" 0 1
    flexcontroller Expressions sad "range" 0 1

    %aa = aa
    %ih = ih
    %oh = oh
    %ou = ou
    %ee = ee
    %blink = blink
    %blink_right = blink_right
    %happy = happy
    %sad = sad
}
```

### 削除する行
```qc
$proceduralbones "pesmat.vrd"
```
（.vrdファイルが存在しないとコンパイルエラーになる）

### その他はそのまま維持
- `$modelname`, `$cdmaterials`, `$attachment`, `$definebone`, `$bonemerge`
- `$ikchain`, `$sequence`, `$includemodel`
- `$collisionjoints`, `$collisiontext`

---

## 5. VTA生成の技術的要件

### VTAフォーマット
```
version 1
nodes
  0 "ValveBiped.Bip01_Pelvis" -1
  ...（SMDと同じボーン定義）
end
skeleton
  time 0
    0 <x> <y> <z> <rx> <ry> <rz>
    ...（各flexフレームのtime分だけ繰り返す）
  time 1
    0 <x> <y> <z> <rx> <ry> <rz>
    ...（time 0と同じ値）
  ...
end
vertexanimation
  time 0
    0 <x> <y> <z> <nx> <ny> <nz>
    1 <x> <y> <z> <nx> <ny> <nz>
    ...（全頂点の参照位置 — SMDの頂点順序と一致必須）
  time 1
    42 <x> <y> <z> <nx> <ny> <nz>
    ...（変化した頂点のみ — 絶対位置、deltaではない）
  ...
end
```

### 重要な仕様
- `skeleton`セクションにflexフレーム数+1（time 0 ~ time N）のエントリが必須（studiomdlのendframe制限）
- ボーンデータはtime 0と同一で可（ボーンは動かない）
- `vertexanimation`のtime 0は全頂点の絶対位置（SMDの`triangles`セクションと同じ順序）
- time N は変化した頂点のみ（絶対位置、studiomdlが`time_N - time_0`でdeltaを計算）
- delta < 0.0001 の頂点はスキップ可能

### VTAとSMDの頂点順序一致
**最重要**: VTAのvertex indexとSMDのtrianglesセクションの暗黙的な頂点indexは**完全に一致**しなければならない。

最も確実な方法: **同じBlenderメッシュから同じイテレーション順序でSMDとVTAを出力する**（`mesh.loop_triangles`を同じ順序で走査）。

VRM2GmodPlayermodelツールの`utils/smd_export.py`にある`write_reference_smd()`と`write_flex_vta()`は同じイテレーション順序を使用しており、この一致は保証されている。

---

## 6. コンパイルとデプロイ

### コンパイルコマンド
studiomdlのコンパイルは`utils/studiomdl_compile.py`の`compile_model()`関数を使用。

### デプロイ先
コンパイル成功後、以下にファイルをコピー:
```
R:\SteamLibrary\...\addons\pescorr\models\player\pesmat\
  ├── pesmat.mdl
  ├── pesmat.dx90.vtx
  ├── pesmat.dx80.vtx
  ├── pesmat.sw.vtx（存在する場合）
  ├── pesmat.vvd
  └── pesmat.phy
```

### Lua登録スクリプト
```lua
-- pesmat_playermodel.lua → addons/pescorr/lua/autorun/
player_manager.AddValidModel("pesmat", "models/player/pesmat.mdl")
list.Set("PlayerOptionsModel", "pesmat", "models/player/pesmat.mdl")

if SERVER then
    util.PrecacheModel("models/player/pesmat.mdl")
end
```

---

## 7. 前回の試行で発生した問題と解決状況

| 問題 | 状況 | 原因 |
|---|---|---|
| メッシュ統合後にマテリアルがズレた | 未解決（後からVMT修正で対応可能） | 統合でマテリアルスロット順序が変化 |
| SMD座標変換不一致 | **解決不要** | 元のSMDを使おうとしたため発生。統合メッシュから両方出力すれば問題ない |
| VTAコンパイルエラー | 解決済み | skeletonセクションのtimeエントリ不足（endframe制限） |
| flexcontroller構文エラー | 解決済み | 正しい構文: `flexcontroller Group Name "range" 0 1` |
| T-poseグリッチ | 解決済み | A-pose変換後のShape Keyデータ不整合 |

---

## 8. 推奨実装手順

1. Blenderで`pescorrV2.blend`を開く
2. 全メッシュのTransformをApply
3. 3メッシュを1つに統合（体.001をアクティブにして結合）
4. VRM2GmodPlayermodelの`write_reference_smd()`でSMD出力
5. VRM2GmodPlayermodelの`write_flex_vta()`でVTA出力
6. 元のQCをベースに`$bodygroup`→`$model`+flexfileに変更、`$proceduralbones`削除
7. 元の物理SMD（pm_physics.smd）をcompileディレクトリにコピー
8. studiomdlでコンパイル
9. マテリアルがズレていたらVMTの`$basetexture`参照を入れ替えて修正
10. `addons/pescorr/models/`にコピー

### バッチスクリプトの雛形
`R:\AI\VRM2GmodPlayermodel\convert_pescorr.py` に途中まで実装済み。
メッシュ統合→SMD+VTA出力の方式に書き換えて使用する。
