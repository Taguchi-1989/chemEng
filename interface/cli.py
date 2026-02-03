#!/usr/bin/env python3
"""
ChemEng CLI - 化学工学計算コマンドラインツール

Usage:
    python -m chemeng                           # インタラクティブモード
    python -m chemeng property ethanol vapor_pressure --T 350
    python -m chemeng calculate distillation --params params.yaml
    python -m chemeng skill list
    python -m chemeng engine list
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


def load_params(path: str) -> dict[str, Any]:
    """パラメータファイルを読み込み"""
    p = Path(path)
    if not p.exists():
        print(f"Error: File not found: {path}", file=sys.stderr)
        sys.exit(1)

    with open(p, encoding="utf-8") as f:
        if p.suffix in (".yaml", ".yml"):
            return yaml.safe_load(f)
        elif p.suffix == ".json":
            return json.load(f)
        else:
            print(f"Error: Unsupported file format: {p.suffix}", file=sys.stderr)
            sys.exit(1)


def print_result(result: dict[str, Any], format: str = "text"):
    """結果を出力"""
    if format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return

    if result.get("success", True):
        outputs = result.get("outputs", result)
        print("\n=== 計算結果 ===")
        for key, value in outputs.items():
            if isinstance(value, dict):
                print(f"\n{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            elif isinstance(value, list):
                print(f"\n{key}:")
                for item in value:
                    print(f"  - {item}")
            else:
                print(f"{key}: {value}")

        warnings = result.get("warnings", [])
        if warnings:
            print("\n⚠ 警告:")
            for w in warnings:
                print(f"  - {w}")
    else:
        print("\n❌ エラー:", file=sys.stderr)
        for e in result.get("errors", ["Unknown error"]):
            print(f"  - {e}", file=sys.stderr)


def cmd_property(args):
    """物性値取得コマンド"""
    from chemeng.engines import select_engine

    substance = args.substance
    property_name = args.property

    conditions = {}
    if args.T:
        conditions["temperature"] = args.T
    if args.P:
        conditions["pressure"] = args.P
    if args.Q is not None:
        conditions["quality"] = args.Q

    # エンジン選択
    if args.engine:
        from chemeng.engines import get_engine
        engine = get_engine(args.engine)
        if not engine:
            print(f"Error: Engine not found: {args.engine}", file=sys.stderr)
            sys.exit(1)
    else:
        engine = select_engine(substance=substance, property_name=property_name)

    if not engine:
        print("Error: No calculation engine available", file=sys.stderr)
        sys.exit(1)

    try:
        value = engine.get_property(substance, property_name, conditions)

        result = {
            "success": True,
            "outputs": {
                "substance": substance,
                "property": property_name,
                "value": value,
                "conditions": conditions,
                "engine": engine.name,
            },
        }

        if args.json:
            print_result(result, "json")
        else:
            print(f"\n{property_name}({substance}) = {value}")
            print(f"  条件: T={conditions.get('temperature', 'N/A')} K, "
                  f"P={conditions.get('pressure', 'N/A')} Pa")
            print(f"  エンジン: {engine.name}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_calculate(args):
    """計算実行コマンド"""
    from chemeng.core import get_registry

    skill_id = args.skill
    registry = get_registry()

    # パラメータ読み込み
    if args.params:
        params = load_params(args.params)
    elif args.param:
        # --param key=value 形式
        params = {}
        for p in args.param:
            if "=" in p:
                key, value = p.split("=", 1)
                # 数値変換を試みる
                try:
                    value = float(value)
                except ValueError:
                    pass
                params[key] = value
    else:
        params = {}

    # スキル実行
    result = registry.execute(skill_id, params)

    if args.json:
        print_result(result.to_dict(), "json")
    else:
        print_result(result.to_dict())

    if not result.success:
        sys.exit(1)


def cmd_skill(args):
    """スキル管理コマンド"""
    from chemeng.core import get_registry

    registry = get_registry()

    if args.action == "list":
        skills = registry.list_skills()
        if not skills:
            print("利用可能なスキルがありません")
            return

        print("\n=== 利用可能なスキル ===")
        for skill in skills:
            print(f"\n{skill.id}")
            print(f"  名前: {skill.name}")
            print(f"  説明: {skill.description}")
            print(f"  タイプ: {skill.calculation_type}")
            print(f"  エンジン: {', '.join(skill.required_engines)}")

    elif args.action == "show":
        if not args.skill_id:
            print("Error: --skill-id required", file=sys.stderr)
            sys.exit(1)

        skill = registry.get_skill(args.skill_id)
        if not skill:
            print(f"Error: Skill not found: {args.skill_id}", file=sys.stderr)
            sys.exit(1)

        print(f"\n=== {skill.id} ===")
        print(f"名前: {skill.name}")
        print(f"説明: {skill.description}")
        print(f"タイプ: {skill.calculation_type}")
        print(f"バージョン: {skill.version}")
        print(f"エンジン: {', '.join(skill.required_engines)}")

        print("\n入力パラメータ:")
        for p in skill.input_schema:
            req = "[必須]" if p.required else "[任意]"
            default = f" (デフォルト: {p.default})" if p.default is not None else ""
            unit = f" [{p.unit}]" if p.unit else ""
            print(f"  {p.name}{unit} {req}{default}")
            if p.description:
                print(f"    {p.description}")

        print("\n出力:")
        for p in skill.output_schema:
            unit = f" [{p.unit}]" if p.unit else ""
            print(f"  {p.name}{unit}")
            if p.description:
                print(f"    {p.description}")


def cmd_engine(args):
    """エンジン管理コマンド"""
    from chemeng.engines import get_available_engines, get_engine

    if args.action == "list":
        engines = get_available_engines()
        if not engines:
            print("利用可能なエンジンがありません")
            print("\n以下のライブラリをインストールしてください:")
            print("  pip install thermo chemicals  # 物性推算")
            print("  pip install cantera           # 反応工学")
            print("  pip install CoolProp          # 冷媒物性")
            return

        print("\n=== 利用可能なエンジン ===")
        for engine in engines:
            cap = engine.capabilities
            print(f"\n{engine.name}")
            print(f"  物性: {', '.join(cap.property_types[:5])}...")
            print(f"  計算: {', '.join(cap.calculation_types)}")
            print(f"  対象: {cap.supported_substances}")

    elif args.action == "show":
        if not args.engine_name:
            print("Error: --engine-name required", file=sys.stderr)
            sys.exit(1)

        engine = get_engine(args.engine_name)
        if not engine:
            print(f"Error: Engine not found: {args.engine_name}", file=sys.stderr)
            sys.exit(1)

        cap = engine.capabilities
        print(f"\n=== {engine.name} ===")
        print(f"利用可能: {engine.is_available()}")
        print("\n物性タイプ:")
        for p in cap.property_types:
            print(f"  - {p}")
        print("\n計算タイプ:")
        for c in cap.calculation_types:
            print(f"  - {c}")
        print(f"\n対象物質: {cap.supported_substances}")


def cmd_info(args):
    """物質情報コマンド"""
    from chemeng.engines import select_engine

    substance = args.substance
    engine = select_engine(substance=substance)

    if not engine:
        print("Error: No calculation engine available", file=sys.stderr)
        sys.exit(1)

    try:
        if hasattr(engine, "get_substance_info"):
            info = engine.get_substance_info(substance)
        elif hasattr(engine, "get_fluid_info"):
            info = engine.get_fluid_info(substance)
        else:
            print(f"Error: Engine {engine.name} does not support substance info")
            sys.exit(1)

        print(f"\n=== {substance} ===")
        for key, value in info.items():
            if value is not None:
                print(f"  {key}: {value}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def interactive_mode():
    """インタラクティブモード"""
    print("=" * 50)
    print("  ChemEng - 化学工学計算ツール")
    print("=" * 50)
    print("\nコマンド:")
    print("  property <物質> <物性> [--T <温度>] [--P <圧力>]")
    print("  calculate <スキル> [--param key=value ...]")
    print("  skill list")
    print("  engine list")
    print("  info <物質>")
    print("  help")
    print("  quit")
    print()

    while True:
        try:
            line = input("chemeng> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        if cmd in ("quit", "exit", "q"):
            print("Bye!")
            break

        elif cmd == "help":
            print("\nコマンド一覧:")
            print("  property <物質> <物性> --T <温度K> --P <圧力Pa>")
            print("    例: property ethanol vapor_pressure --T 350")
            print("  calculate <スキル> --param key=value")
            print("    例: calculate property_estimation --param substance=water --param property=density --param temperature=300")
            print("  skill list / skill show <id>")
            print("  engine list / engine show <name>")
            print("  info <物質>")
            print("  quit")

        elif cmd == "property" and len(parts) >= 3:
            # 簡易パース
            args = argparse.Namespace(
                substance=parts[1],
                property=parts[2],
                T=None,
                P=None,
                Q=None,
                engine=None,
                json=False,
            )
            for i, p in enumerate(parts):
                if p == "--T" and i + 1 < len(parts):
                    args.T = float(parts[i + 1])
                elif p == "--P" and i + 1 < len(parts):
                    args.P = float(parts[i + 1])
            try:
                cmd_property(args)
            except SystemExit:
                pass

        elif cmd == "skill":
            if len(parts) > 1 and parts[1] == "list":
                args = argparse.Namespace(action="list", skill_id=None)
                cmd_skill(args)
            elif len(parts) > 2 and parts[1] == "show":
                args = argparse.Namespace(action="show", skill_id=parts[2])
                cmd_skill(args)

        elif cmd == "engine":
            if len(parts) > 1 and parts[1] == "list":
                args = argparse.Namespace(action="list", engine_name=None)
                cmd_engine(args)

        elif cmd == "info" and len(parts) >= 2:
            args = argparse.Namespace(substance=parts[1])
            try:
                cmd_info(args)
            except SystemExit:
                pass

        else:
            print(f"Unknown command: {cmd}")
            print("Type 'help' for available commands")


def main():
    parser = argparse.ArgumentParser(
        description="ChemEng - 化学工学計算CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  %(prog)s property ethanol vapor_pressure --T 350
  %(prog)s calculate distillation --params distillation.yaml
  %(prog)s skill list
  %(prog)s engine list
        """,
    )

    subparsers = parser.add_subparsers(dest="command")

    # property コマンド
    prop_parser = subparsers.add_parser("property", help="物性値を取得")
    prop_parser.add_argument("substance", help="物質名またはCAS番号")
    prop_parser.add_argument("property", help="物性名")
    prop_parser.add_argument("--T", type=float, help="温度 (K)")
    prop_parser.add_argument("--P", type=float, help="圧力 (Pa)")
    prop_parser.add_argument("--Q", type=float, help="乾き度 (0-1)")
    prop_parser.add_argument("--engine", help="使用するエンジン")
    prop_parser.add_argument("--json", action="store_true", help="JSON出力")

    # calculate コマンド
    calc_parser = subparsers.add_parser("calculate", help="計算を実行")
    calc_parser.add_argument("skill", help="スキルID")
    calc_parser.add_argument("--params", "-p", help="パラメータファイル (YAML/JSON)")
    calc_parser.add_argument("--param", action="append", help="パラメータ (key=value)")
    calc_parser.add_argument("--json", action="store_true", help="JSON出力")

    # skill コマンド
    skill_parser = subparsers.add_parser("skill", help="スキル管理")
    skill_parser.add_argument("action", choices=["list", "show"], help="アクション")
    skill_parser.add_argument("--skill-id", help="スキルID")

    # engine コマンド
    engine_parser = subparsers.add_parser("engine", help="エンジン管理")
    engine_parser.add_argument("action", choices=["list", "show"], help="アクション")
    engine_parser.add_argument("--engine-name", help="エンジン名")

    # info コマンド
    info_parser = subparsers.add_parser("info", help="物質情報を取得")
    info_parser.add_argument("substance", help="物質名")

    args = parser.parse_args()

    if args.command == "property":
        cmd_property(args)
    elif args.command == "calculate":
        cmd_calculate(args)
    elif args.command == "skill":
        cmd_skill(args)
    elif args.command == "engine":
        cmd_engine(args)
    elif args.command == "info":
        cmd_info(args)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
