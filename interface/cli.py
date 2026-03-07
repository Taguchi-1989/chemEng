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
    try:
        from chemeng.engines import select_engine
    except ImportError:
        from engines import select_engine

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
        try:
            from chemeng.engines import get_engine
        except ImportError:
            from engines import get_engine
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
    try:
        from chemeng.core import get_registry
    except ImportError:
        from core import get_registry

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
    try:
        from chemeng.core import get_registry
    except ImportError:
        from core import get_registry

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
    try:
        from chemeng.engines import get_available_engines, get_engine
    except ImportError:
        from engines import get_available_engines, get_engine

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


def cmd_data(args):
    """物性データ管理コマンド"""
    try:
        from chemeng.data.property_db import get_property_db
        from chemeng.fetchers import get_available_fetchers, get_fetcher, search_all
    except ImportError:
        from data.property_db import get_property_db
        from fetchers import get_available_fetchers, get_fetcher, search_all

    action = args.data_action

    if action == "sources":
        fetchers = get_available_fetchers()
        if not fetchers:
            print("利用可能なデータソースがありません")
            return
        print("\n=== データソース / Data Sources ===")
        for f in fetchers:
            cap = f.capabilities
            available = "OK" if f.is_available() else "N/A"
            print(f"\n  {f.name} [{available}]")
            print(f"    名前: {cap.source_name}")
            print(f"    URL: {cap.source_url}")
            print(f"    化合物数: {cap.compound_count}")
            print(f"    レート制限: {cap.rate_limit}")
            print(f"    APIキー: {'必要' if cap.requires_api_key else '不要'}")

    elif action == "search":
        query = args.query
        source = getattr(args, "source", None)
        print(f"\n検索中: {query} ...")

        if source:
            fetcher = get_fetcher(source)
            if not fetcher:
                print(f"Error: ソース '{source}' が見つかりません", file=sys.stderr)
                return
            try:
                results = fetcher.search(query, max_results=getattr(args, "max", 5))
                _print_search_results({source: results})
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
        else:
            results = search_all(query, max_per_source=getattr(args, "max", 3))
            _print_search_results(results)

    elif action == "fetch":
        substance = args.substance
        source = getattr(args, "source", "pubchem")
        fetcher = get_fetcher(source)
        if not fetcher:
            print(f"Error: ソース '{source}' が見つかりません", file=sys.stderr)
            return

        print(f"\n{source} から {substance} のデータを取得中...")
        try:
            record = fetcher.fetch_properties(substance)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return

        _print_substance_record(record)

        if not getattr(args, "no_save", False):
            db = get_property_db()
            saved = db.add_or_update(record)
            prop_count = sum(len(v) for v in saved.properties.values())
            print(f"\nローカルDBに保存しました ({prop_count} properties)")

    elif action == "list":
        db = get_property_db()
        records = db.list_all(category=getattr(args, "category", None))
        if not records:
            print("\nローカルDBにデータがありません")
            print("  data fetch <物質名> --source pubchem で追加できます")
            return
        print(f"\n=== ローカルDB ({db.count()} substances) ===")
        for r in records:
            prop_count = len(r.properties)
            sources = ", ".join(r.sources_used) if r.sources_used else "N/A"
            print(f"  {r.name}")
            print(f"    CAS: {r.cas or 'N/A'} | Formula: {r.formula or 'N/A'} | "
                  f"MW: {r.molecular_weight or 'N/A'}")
            print(f"    物性数: {prop_count} | ソース: {sources}")

    elif action == "show":
        substance = args.substance
        db = get_property_db()
        record = db.get(substance)
        if not record:
            print(f"ローカルDBに '{substance}' が見つかりません")
            return
        _print_substance_record(record)

    elif action == "delete":
        substance = args.substance
        db = get_property_db()
        if db.delete(substance):
            print(f"'{substance}' を削除しました")
        else:
            print(f"'{substance}' が見つかりません")


def _print_search_results(results: dict[str, list]) -> None:
    """検索結果を表示"""
    total = sum(len(v) for v in results.values())
    if total == 0:
        print("  該当なし")
        return

    print(f"\n=== 検索結果 ({total} hits) ===")
    for source, items in results.items():
        if not items:
            continue
        print(f"\n[{source}] ({len(items)} results):")
        for i, r in enumerate(items, 1):
            mw = f"{r.molecular_weight:.2f}" if r.molecular_weight else "N/A"
            print(f"  {i}. {r.name}")
            line = f"     CAS: {r.cas or 'N/A'} | Formula: {r.formula or 'N/A'} | MW: {mw}"
            if r.source_id:
                line += f" | ID: {r.source_id}"
            print(line)


def _print_substance_record(record) -> None:
    """物質レコード詳細を表示"""
    print(f"\n=== {record.name} ===")
    if record.name_ja:
        print(f"  日本語名: {record.name_ja}")
    print(f"  CAS: {record.cas or 'N/A'}")
    print(f"  Formula: {record.formula or 'N/A'}")
    if record.molecular_weight:
        print(f"  MW: {record.molecular_weight:.2f} g/mol")
    if record.smiles:
        print(f"  SMILES: {record.smiles}")
    if record.pubchem_cid:
        print(f"  PubChem CID: {record.pubchem_cid}")
    if record.sources_used:
        print(f"  ソース: {', '.join(record.sources_used)}")

    if record.properties:
        print(f"\n  物性値 ({len(record.properties)} types):")
        for prop_name, values in sorted(record.properties.items()):
            for v in values:
                cond = ""
                if v.temperature:
                    cond += f" @ {v.temperature:.1f} K"
                if v.pressure and v.pressure != 101325.0:
                    cond += f", {v.pressure:.0f} Pa"
                conf = f"[{v.source}, {v.confidence}]" if v.source else ""
                print(f"    {prop_name}: {v.value:.4g} {v.unit}{cond}  {conf}")


def cmd_info(args):
    """物質情報コマンド"""
    try:
        from chemeng.engines import select_engine
    except ImportError:
        from engines import select_engine

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
    print("  data search|fetch|list|show|sources|delete")
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
            print("  data sources                          - データソース一覧")
            print("  data search <物質名> [--source <src>] - 外部ソース検索")
            print("  data fetch <物質名> [--source <src>]  - データ取得＆保存")
            print("  data list                             - ローカルDB一覧")
            print("  data show <物質名>                    - 物質詳細表示")
            print("  data delete <物質名>                  - データ削除")
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

        elif cmd == "data":
            if len(parts) < 2:
                print("Usage: data <search|fetch|list|show|sources|delete> [args]")
                continue
            sub = parts[1].lower()
            if sub == "sources":
                data_args = argparse.Namespace(data_action="sources")
            elif sub == "search" and len(parts) >= 3:
                source = None
                max_results = 5
                for i, p in enumerate(parts):
                    if p == "--source" and i + 1 < len(parts):
                        source = parts[i + 1]
                    if p == "--max" and i + 1 < len(parts):
                        max_results = int(parts[i + 1])
                data_args = argparse.Namespace(
                    data_action="search", query=parts[2],
                    source=source, max=max_results,
                )
            elif sub == "fetch" and len(parts) >= 3:
                source = "pubchem"
                for i, p in enumerate(parts):
                    if p == "--source" and i + 1 < len(parts):
                        source = parts[i + 1]
                data_args = argparse.Namespace(
                    data_action="fetch", substance=parts[2],
                    source=source, no_save=False,
                )
            elif sub == "list":
                category = None
                for i, p in enumerate(parts):
                    if p == "--category" and i + 1 < len(parts):
                        category = parts[i + 1]
                data_args = argparse.Namespace(
                    data_action="list", category=category,
                )
            elif sub == "show" and len(parts) >= 3:
                data_args = argparse.Namespace(
                    data_action="show", substance=parts[2],
                )
            elif sub == "delete" and len(parts) >= 3:
                data_args = argparse.Namespace(
                    data_action="delete", substance=parts[2],
                )
            else:
                print("Usage: data <search|fetch|list|show|sources|delete> [args]")
                continue
            try:
                cmd_data(data_args)
            except SystemExit:
                pass

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

    # data コマンド
    data_parser = subparsers.add_parser("data", help="物性データ管理")
    data_sub = data_parser.add_subparsers(dest="data_action")

    data_search = data_sub.add_parser("search", help="物質を検索")
    data_search.add_argument("query", help="物質名、CAS番号、または分子式")
    data_search.add_argument("--source", help="検索ソース (pubchem, thermo, all)")
    data_search.add_argument("--max", type=int, default=5, help="最大結果数")

    data_fetch = data_sub.add_parser("fetch", help="外部ソースからデータ取得")
    data_fetch.add_argument("substance", help="物質名またはCAS番号")
    data_fetch.add_argument("--source", default="pubchem", help="データソース")
    data_fetch.add_argument("--no-save", action="store_true", help="ローカルに保存しない")

    data_sub.add_parser("list", help="ローカルDB内の物質一覧")
    data_sub.add_parser("sources", help="利用可能なデータソース一覧")

    data_show = data_sub.add_parser("show", help="物質の詳細データ表示")
    data_show.add_argument("substance", help="物質名")

    data_del = data_sub.add_parser("delete", help="ローカルDBから物質を削除")
    data_del.add_argument("substance", help="物質名")

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
    elif args.command == "data":
        cmd_data(args)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
