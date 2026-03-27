# VRM2GmodPlayermodel

**VRM/VRCモデルをGarry's Modプレイヤーモデルに変換するBlenderアドオン**

*Convert VRM/VRC models to Garry's Mod playermodels with one click.*

<!-- TODO: スクリーンショット/デモGIFをここに追加 -->
<!-- ![Demo](docs/demo.gif) -->

---

## [日本語](#日本語) | [English](#english)

---

## 日本語

### 特徴

- **ワンクリック変換** — VRMモデルをインポートしてボタン一つでGModプレイヤーモデルに
- **表情（Flex）対応** — VRMの表情シェイプキーを自動検出し、GModのFlex表情システムに変換（96+コントローラー対応）
- **スマートテクスチャ処理** — テクスチャ自動検出 → 近傍ファイル検索 → 単色フォールバックの3段階システム
- **物理モデル自動生成** — 17個のコリジョンボックスを自動設定
- **変換後診断** — ボーン完全性、階層、プロポーション、ウェイトの自動検証
- **バッチ変換** — コマンドラインから複数モデル一括変換
- **男性/女性ボディタイプ** — アニメーションセットの自動切り替え
- **指の簡略化** — SIMPLE/DETAILED/FROZENの3モード

### 動作環境

- **Blender** 4.2以上（5.0/5.1推奨）
- **Garry's Mod**（studiomdl.exe が必要）
- **VRM Extension for Blender**（VRMインポート用）
- **VTFCmd.exe**（オプション — なくても純Pythonフォールバックで動作）

### インストール

#### Blender 4.2+ Extension形式（推奨）

1. [Releases](../../releases) から最新の `VRM2GmodPlayermodel-vX.X.X.zip` をダウンロード
2. Blender → 編集 → プリファレンス → アドオン → 「インストール...」
3. ダウンロードした .zip を選択
4. アドオン一覧で「VRM to GMod Playermodel」を有効化

#### 手動インストール

1. このリポジトリをクローンまたはダウンロード
2. `VRM2GmodPlayermodel` フォルダを以下にコピー：
   - Windows: `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\`
3. Blenderのプリファレンスでアドオンを有効化

### 初期設定

アドオン設定（プリファレンス → アドオン → VRM to GMod Playermodel）で以下を設定：

| 設定 | 説明 | 例 |
|------|------|----|
| studiomdl.exe パス | Valveのモデルコンパイラ | `...\GarrysMod\bin\studiomdl.exe` |
| VTFCmd.exe パス | テクスチャ変換（オプション） | `...\VTFCmd\VTFCmd.exe` |
| GMod addons フォルダ | アドオン出力先 | `...\GarrysMod\garrysmod\addons\` |
| デフォルト出力先 | 作業ファイル出力先 | 任意のフォルダ |

### 使い方

1. VRMモデルをBlenderにインポート（ファイル → インポート → VRM）
2. サイドバー（Nキー）→ **VRM2GMod** タブを開く
3. モデル名や出力先を設定
4. **「フル変換」** ボタンをクリック
5. 完了！GModで使えるプレイヤーモデルが生成されます

### パイプライン概要

```
VRM Import → Bone Remap → Mesh Prepare → A-Pose → SMD/VTA Export
  → Material Convert → Physics Generate → QC Generate → studiomdl Compile
```

### バッチ変換（CLI）

```bash
blender --background --python batch_convert.py -- --input model.vrm --output ./out --model-name mymodel
```

---

## English

### Features

- **One-Click Conversion** — Import a VRM model and convert to a GMod playermodel with a single button
- **Facial Expressions (Flex)** — Auto-detects VRM shape keys and converts them to GMod's Flex system (96+ controllers)
- **Smart Texture Handling** — 3-tier fallback: auto-detect → neighbor search → solid color
- **Auto Physics Generation** — 17 collision boxes auto-configured
- **Post-Conversion Diagnostics** — Automatic validation of bones, hierarchy, proportions, and weights
- **Batch Conversion** — Convert multiple models via command line
- **Male/Female Body Types** — Automatic animation set switching
- **Finger Simplification** — SIMPLE / DETAILED / FROZEN modes

### Requirements

- **Blender** 4.2+ (5.0/5.1 recommended)
- **Garry's Mod** (studiomdl.exe required)
- **VRM Extension for Blender** (for VRM import)
- **VTFCmd.exe** (optional — pure Python fallback available)

### Installation

#### Blender 4.2+ Extension Format (Recommended)

1. Download the latest `VRM2GmodPlayermodel-vX.X.X.zip` from [Releases](../../releases)
2. Blender → Edit → Preferences → Add-ons → "Install..."
3. Select the downloaded .zip
4. Enable "VRM to GMod Playermodel" in the add-on list

#### Manual Installation

1. Clone or download this repository
2. Copy the `VRM2GmodPlayermodel` folder to:
   - Windows: `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\`
3. Enable the add-on in Blender Preferences

### Setup

Configure in Add-on Preferences (Preferences → Add-ons → VRM to GMod Playermodel):

| Setting | Description | Example |
|---------|-------------|---------|
| studiomdl.exe Path | Valve's model compiler | `...\GarrysMod\bin\studiomdl.exe` |
| VTFCmd.exe Path | Texture converter (optional) | `...\VTFCmd\VTFCmd.exe` |
| GMod addons Folder | Addon output directory | `...\GarrysMod\garrysmod\addons\` |
| Default Output Path | Working file output | Any folder |

### Usage

1. Import a VRM model in Blender (File → Import → VRM)
2. Open the sidebar (N key) → **VRM2GMod** tab
3. Set model name and output path
4. Click **"Full Convert"**
5. Done! A GMod-ready playermodel is generated

### Pipeline Overview

```
VRM Import → Bone Remap → Mesh Prepare → A-Pose → SMD/VTA Export
  → Material Convert → Physics Generate → QC Generate → studiomdl Compile
```

### Batch Conversion (CLI)

```bash
blender --background --python batch_convert.py -- --input model.vrm --output ./out --model-name mymodel
```

---

## Supported Input Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| VRM 1.0 | `.vrm` | Via Blender VRM Extension |
| VRChat Avatar | `.blend` | Pre-rigged .blend files |
| Existing GMod Model | `.blend` | Re-export / repair mode |

## Troubleshooting

### studiomdl.exe が見つからない
Garry's Mod の `bin` フォルダ内にあります。Steam → GarrysMod → プロパティ → ローカルファイル → 参照で確認できます。

### テクスチャが真っ白になる
テクスチャのパスが壊れている可能性があります。マテリアルパネルで手動テクスチャを設定してください。

### モデルが小さすぎる/大きすぎる
VRM2GModパネルの「ターゲット身長」を調整してください。デフォルトはSource Engineの標準体格です。

## 注意事項 / Disclaimer

**このツールはすべてのVRMモデルの変換を保証するものではありません。**
VRMモデルは制作者によってボーン構造・シェイプキー・マテリアル構成が大きく異なるため、
すべてのモデルに対応することは技術的に不可能です。
変換がうまくいかない場合もあります。ご了承ください。

また、**モデルの権利は元の制作者に帰属します。**
変換・使用にあたっては、各モデルの利用規約を必ず確認してください。
本ツールはモデルの無断利用を推奨・助長するものではありません。
**他の方が制作したモデルを、制作者の許容範囲を超える形でSteam Workshop等にアップロードする行為はおやめください。**

**This tool does not guarantee successful conversion of all VRM models.**
VRM models vary widely in bone structure, shape keys, and material setup depending on the creator,
making universal compatibility technically impossible.
Conversion may fail for some models. We appreciate your understanding.

**Model rights belong to their original creators.**
Please check each model's terms of use before converting or using them.
This tool does not encourage or facilitate unauthorized use of models.
**Do not upload models created by others to Steam Workshop or similar platforms beyond what the original creator permits.**

## Contributing

不具合の報告や機能リクエストは [Issues](../../issues) へお気軽にどうぞ。
ただし、**特定モデルの変換失敗については個別対応が難しい場合があります。**
プルリクエストは歓迎です。

Bug reports and feature requests are welcome via [Issues](../../issues).
However, **we may not be able to address conversion failures for specific models individually.**
Pull requests are appreciated.

## License

[MIT License](LICENSE) - Copyright (c) 2026 Pescorr
