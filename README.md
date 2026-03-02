# ChemEng - Chemical Engineering Laboratory

化学工学計算 Web アプリケーション。ブラウザ上で物性推算・蒸留塔設計・物質収支など7種の計算をインタラクティブに実行できます。

> **Python 3.10 以上** が必要です。

---

## Quick Start

### Windows

```
git clone https://github.com/Taguchi-1989/chemEng.git
cd chemEng
ChemEng_Start.bat
```

`ChemEng_Start.bat` が仮想環境の作成・依存インストール・サーバー起動・ブラウザオープンをすべて自動で行います。

### macOS / Linux

```bash
git clone https://github.com/Taguchi-1989/chemEng.git
cd chemEng
bash start.sh
```

### 手動セットアップ（全OS共通）

```bash
git clone https://github.com/Taguchi-1989/chemEng.git
cd chemEng

# 仮想環境を作成・有効化
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 依存パッケージをインストール
pip install -r requirements_full.txt

# サーバー起動
python server.py --port 8000
```

ブラウザで http://localhost:8000 を開きます。

### Docker

```bash
git clone https://github.com/Taguchi-1989/chemEng.git
cd chemEng
docker build -t chemeng .
docker run -p 8000:8000 chemeng
```

---

## 計算機能（7種類）

| 機能 | 説明 |
|------|------|
| **物性推算** | 蒸気圧、密度、粘度、熱容量など |
| **蒸留塔設計** | McCabe-Thiele法による段数・還流比計算 |
| **物質収支** | プロセス単位での入出力バランス計算 |
| **熱収支** | 顕熱・潜熱・相変化を考慮した熱計算 |
| **液液抽出** | 抽出段数・回収率の計算 |
| **ガス吸収** | 吸収塔の設計計算 |
| **LCOH計算** | 水素製造原価（電解・SMR等）の経済性評価 |

## Web UI 機能

| 機能 | 説明 |
|------|------|
| **ダークモード** | ライト/ダークテーマ切替 |
| **ダッシュボード** | 複数ケースの比較・グラフ表示 |
| **履歴機能** | 過去20件の計算履歴を保存・再利用 |
| **レポート出力** | HTML形式の計算レポート生成 |
| **インポート/エクスポート** | JSON/CSVでのデータ入出力 |
| **プロンプトテンプレート** | LLM連携用のテンプレート生成 |

### LLM連携ワークフロー

```
1. Templateボタンでプロンプトテンプレートをダウンロード
       ↓
2. 自社CSVデータ/音声入力データを用意
       ↓
3. テンプレート + データをClaude等のLLMに投入
       ↓
4. LLMが出力したJSONをインポートボタンから読み込み
       ↓
5. フォーム自動入力 → ワンクリックで計算実行
```

---

## テスト

```bash
pip install pytest
pytest tests/ -v
```

## Python API

### 物性推算

```python
from engines.thermo_engine import ThermoEngine

engine = ThermoEngine()

# エタノールの蒸気圧（350K）
P_vap = engine.get_property("ethanol", "vapor_pressure", {"temperature": 350.0})
print(f"Vapor pressure: {P_vap:.0f} Pa")

# 物質情報
info = engine.get_substance_info("water")
print(f"Critical temperature: {info['critical_temperature']:.1f} K")
```

### 相平衡計算

```python
# エタノール-水系のVLE
result = engine.calculate_equilibrium(
    substances=["ethanol", "water"],
    composition={"ethanol": 0.4, "water": 0.6},
    conditions={"temperature": 350.0, "pressure": 101325.0},
)
print(f"K-values: {result['K_values']}")

# 泡点計算
result = engine.calculate_bubble_point(
    substances=["ethanol", "water"],
    composition={"ethanol": 0.5, "water": 0.5},
    pressure=101325.0,
)
print(f"Bubble point: {result['bubble_point_temperature']:.1f} K")
```

---

## ディレクトリ構造

```
chemEng/
├── ChemEng_Start.bat   # Windows用起動スクリプト
├── start.sh            # macOS/Linux用起動スクリプト
├── server.py           # FastAPIサーバー
├── core/               # コアデータクラス
│   ├── requirement.py  # 要件定義
│   ├── skill.py        # スキル定義
│   └── registry.py     # スキルレジストリ
├── engines/            # 計算エンジン
│   ├── base.py         # 基底クラス
│   └── thermo_engine.py
├── skills/             # 計算スキル
│   ├── schema/         # スキーマ(YAML)
│   ├── templates/      # テンプレート(Python)
│   └── defaults/       # デフォルト値
├── interface/          # インターフェース
│   ├── cli.py          # CLI
│   ├── api.py          # REST API
│   └── web/            # Web UI
│       ├── index.html
│       ├── css/
│       └── js/
└── tests/              # テスト
```

## 対応ライブラリ

| ライブラリ | 用途 | 状態 |
|-----------|------|------|
| thermo/chemicals | 物性推算、VLE | 実装済み |
| Cantera | 反応速度、化学平衡 | 開発中 |
| CoolProp | 冷媒物性 | 開発中 |

---

## セキュリティ・プライバシー

### 機密情報について

**本プロジェクトには機密情報は一切含まれていません。**

- すべてのソースコードは公開情報およびオープンソースライブラリのみを使用して作成
- 物性データは [thermo](https://github.com/CalebBell/thermo) / [chemicals](https://github.com/CalebBell/chemicals) ライブラリ（MIT License）から取得
- 計算アルゴリズムは公開された学術文献および標準的な化学工学の教科書に基づく
- 企業固有のデータ、プロセス情報、ノウハウは含まれていない

### テレメトリ・外部通信

**本アプリケーションはユーザーデータを外部に送信しません。**

| 項目 | 状態 | 説明 |
|------|------|------|
| アナリティクス | なし | Google Analytics等のトラッキングコードなし |
| テレメトリ | なし | 使用状況の自動送信機能なし |
| 外部API呼び出し | なし | 計算はすべてローカルで実行 |
| Cookie/LocalStorage | 最小限 | UIテーマ・履歴・ダッシュボードの保存のみ（ブラウザ内完結） |

**外部CDN利用（オプション）:**
- Google Fonts (`fonts.googleapis.com`) - フォント配信のみ
- Chart.js (`cdn.jsdelivr.net`) - グラフ描画ライブラリ

---

## ライセンス

MIT License

Copyright (c) 2025 ZEAL-BOOT-CAMP

### 依存ライブラリのライセンス

| ライブラリ | ライセンス | 著作権者 |
|-----------|----------|---------|
| [thermo](https://github.com/CalebBell/thermo) | MIT | Caleb Bell and Contributors |
| [chemicals](https://github.com/CalebBell/chemicals) | MIT | Caleb Bell and Contributors |
| [pydantic](https://github.com/pydantic/pydantic) | MIT | Pydantic Services Inc. |
| [FastAPI](https://github.com/tiangolo/fastapi) | MIT | Sebastián Ramírez |
| [PyYAML](https://github.com/yaml/pyyaml) | MIT | Ingy döt Net, Kirill Simonov |
| [Chart.js](https://github.com/chartjs/Chart.js) | MIT | Chart.js Contributors |
| [uvicorn](https://github.com/encode/uvicorn) | BSD-3-Clause | Encode OSS Ltd. |
| [scipy](https://github.com/scipy/scipy) | BSD-3-Clause | SciPy Developers |
| [numpy](https://github.com/numpy/numpy) | BSD-3-Clause | NumPy Developers |
| [fluids](https://github.com/CalebBell/fluids) | MIT | Caleb Bell |

## クレジット

- **開発**: ZEAL-BOOT-CAMP
- **物性データベース**: [Chemical Engineering Design Library (ChEDL)](https://github.com/CalebBell/thermo) by Caleb Bell
- **熱力学計算**: thermo / chemicals ライブラリ
