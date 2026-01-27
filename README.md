# ChemEng - 化学工学計算モジュール

AI対話ベースで要件を収集し、OSSライブラリで化学工学計算を実行するモジュール。

## 機能

- **物性推算**: 蒸気圧、密度、粘度、熱容量など（thermo/chemicals）
- **相平衡計算**: VLE、泡点、露点、フラッシュ計算
- **単位操作設計**: 蒸留塔、熱交換器、反応器（開発中）
- **反応工学**: 反応速度、化学平衡（Cantera、開発中）

## インストール

```bash
cd chemeng
pip install -e .

# オプション依存関係
pip install -e ".[cantera]"    # Cantera（反応工学）
pip install -e ".[coolprop]"   # CoolProp（冷媒物性）
pip install -e ".[api]"        # FastAPI（REST API）
pip install -e ".[all]"        # 全て
```

## クイックスタート

### 物性推算

```python
from chemeng.engines.thermo_engine import ThermoEngine

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

### 要件定義

```python
from chemeng.core.requirement import RequirementSpec, Substance, Condition, CalculationType

# 蒸留計算の要件を定義
req = RequirementSpec(
    description="エタノール-水系の蒸留塔設計",
    calculation_type=CalculationType.DISTILLATION,
    substances=[
        Substance(name="ethanol", cas_number="64-17-5"),
        Substance(name="water", cas_number="7732-18-5"),
    ],
    inlet_conditions=[
        Condition(
            temperature=350.0,
            pressure=101325.0,
            flow_rate=100.0,
            composition={"ethanol": 0.4, "water": 0.6},
        )
    ],
    targets={"distillate_purity": 0.95},
)
```

## 対応ライブラリ

| ライブラリ | 用途 | 状態 |
|-----------|------|------|
| thermo/chemicals | 物性推算、VLE | ✅ 実装済み |
| Cantera | 反応速度、化学平衡 | 🚧 開発中 |
| CoolProp | 冷媒物性 | 🚧 開発中 |

## テスト

```bash
cd chemeng
pip install -e ".[dev]"
pytest tests/ -v
```

## ディレクトリ構造

```
chemeng/
├── core/               # コアデータクラス
│   ├── requirement.py  # 要件定義
│   └── skill.py        # スキル定義
├── engines/            # 計算エンジン
│   ├── base.py         # 基底クラス
│   └── thermo_engine.py
├── skills/             # 計算スキル（開発中）
│   ├── schema/         # スキーマ(YAML)
│   └── templates/      # テンプレート(Python)
├── interface/          # インターフェース（開発中）
│   ├── cli.py
│   └── api.py
└── tests/              # テスト
```

## ライセンス

MIT
