#!/usr/bin/env python3
"""
data_tool.py

A small CLI tool to:
 - read CSV or JSON files
 - print a quick summary (rows, columns, sample values)
 - convert CSV -> JSON and JSON -> CSV
 - validate a simple schema (optional)

Usage examples:
    python data_tool.py summary sample.csv
    python data_tool.py convert-to-json sample.csv -o out.json
    python data_tool.py convert-to-csv sample.json -o out.csv
    python data_tool.py validate sample.csv --schema schema.json

The tool uses only Python standard library (no pandas) so it's easy to run.
"""

from __future__ import annotations
import csv
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys


def read_csv(path: Path, max_rows: Optional[int] = 20) -> List[Dict[str, Any]]:
    with path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = []
        for i, r in enumerate(reader):
            rows.append(r)
            if max_rows and i + 1 >= max_rows:
                break
    return rows


def read_json(path: Path, max_rows: Optional[int] = 20) -> List[Dict[str, Any]]:
    with path.open(encoding='utf-8') as f:
        data = json.load(f)
    # accept either list of objects or single object
    if isinstance(data, list):
        return data[:max_rows] if max_rows else data
    if isinstance(data, dict):
        return [data]
    raise ValueError("JSON root must be an object or an array of objects")


def summarize_rows(rows: List[Dict[str, Any]], show: int = 5) -> None:
    if not rows:
        print("No rows to summarize.")
        return

    # collect column names
    columns = list(rows[0].keys())
    print(f"Columns ({len(columns)}): {columns}")
    print(f"Total sample rows: {len(rows)} (showing up to {show})\n")

    # show sample rows
    for i, r in enumerate(rows[:show]):
        print(f"Row {i+1}:")
        for c in columns:
            v = r.get(c, "")
            vstr = str(v)
            # trim long strings
            if len(vstr) > 80:
                vstr = vstr[:77] + "..."
            print(f"  {c}: {vstr}")
        print("")


def csv_to_json(in_path: Path, out_path: Path) -> None:
    with in_path.open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    with out_path.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(data)} records to {out_path}")


def json_to_csv(in_path: Path, out_path: Path) -> None:
    with in_path.open(encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, dict):
        # single object -> write one-row CSV
        data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON must be an array of objects or a single object")
    # union all field names
    fields = set()
    for item in data:
        if isinstance(item, dict):
            fields.update(item.keys())
    fields = sorted(fields)
    with out_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in data:
            # convert nested structures to JSON strings
            row = {}
            for k in fields:
                v = item.get(k, "")
                if isinstance(v, (dict, list)):
                    row[k] = json.dumps(v, ensure_ascii=False)
                else:
                    row[k] = v
            writer.writerow(row)
    print(f"Wrote {len(data)} records to {out_path}")


def validate_schema(rows: List[Dict[str, Any]], schema: Dict[str, str]) -> List[str]:
    """
    Very small schema validation:
    schema is dict field -> type_name (one of: str, int, float)
    Returns list of error strings (empty if valid)
    """
    errors = []
    for i, r in enumerate(rows):
        for field, tname in schema.items():
            val = r.get(field)
            if val is None or val == "":
                errors.append(f"row {i+1}: missing {field}")
                continue
            if tname == "int":
                try:
                    int(val)
                except Exception:
                    errors.append(f"row {i+1}: field {field} expected int, got {val!r}")
            elif tname == "float":
                try:
                    float(val)
                except Exception:
                    errors.append(f"row {i+1}: field {field} expected float, got {val!r}")
            elif tname == "str":
                # everything can be a str, but we keep this for completeness
                pass
            else:
                errors.append(f"unknown schema type for {field}: {tname}")
    return errors


def load_schema(path: Path) -> Dict[str, str]:
    """Load a simple JSON schema mapping field->type"""
    with path.open(encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Schema must be a JSON object mapping field -> type")
    return data


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="data_tool.py",
                                     description="Small CSV/JSON reading & conversion tool")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sp_summary = sub.add_parser("summary", help="Print quick summary of CSV or JSON file")
    sp_summary.add_argument("path", type=Path)

    sp_tojson = sub.add_parser("convert-to-json", help="Convert CSV -> JSON")
    sp_tojson.add_argument("csv_path", type=Path)
    sp_tojson.add_argument("-o", "--output", type=Path, required=True)

    sp_tocsv = sub.add_parser("convert-to-csv", help="Convert JSON -> CSV")
    sp_tocsv.add_argument("json_path", type=Path)
    sp_tocsv.add_argument("-o", "--output", type=Path, required=True)

    sp_validate = sub.add_parser("validate", help="Validate CSV/JSON against a simple schema")
    sp_validate.add_argument("path", type=Path)
    sp_validate.add_argument("--schema", type=Path, required=True)

    args = parser.parse_args(argv)

    try:
        if args.cmd == "summary":
            p = args.path
            if not p.exists():
                print("File not found:", p, file=sys.stderr)
                return 2
            if p.suffix.lower() in [".csv"]:
                rows = read_csv(p, max_rows=20)
            elif p.suffix.lower() in [".json"]:
                rows = read_json(p, max_rows=20)
            else:
                # try both
                try:
                    rows = read_json(p)
                except Exception:
                    rows = read_csv(p)
            summarize_rows(rows, show=5)
            return 0

        elif args.cmd == "convert-to-json":
            csv_to_json(args.csv_path, args.output)
            return 0

        elif args.cmd == "convert-to-csv":
            json_to_csv(args.json_path, args.output)
            return 0

        elif args.cmd == "validate":
            p = args.path
            if p.suffix.lower() == ".csv":
                rows = read_csv(p, max_rows=None)
            elif p.suffix.lower() == ".json":
                rows = read_json(p, max_rows=None)
            else:
                # guess
                try:
                    rows = read_json(p, max_rows=None)
                except Exception:
                    rows = read_csv(p, max_rows=None)
            schema = load_schema(args.schema)
            errors = validate_schema(rows, schema)
            if not errors:
                print("Validation passed ✅")
                return 0
            else:
                print("Validation found errors:")
                for e in errors[:200]:
                    print(" -", e)
                return 3
    except Exception as exc:
        print("Error:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
