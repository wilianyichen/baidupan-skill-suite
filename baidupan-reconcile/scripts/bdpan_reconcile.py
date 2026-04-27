#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""百度网盘差异对账工具。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.bdpan_inventory import (
    BaiduPanInventoryClient,
    build_local_tree,
    format_mtime,
    format_size,
    normalize_remote_path,
)
from common.bdpan_manifest import now_iso, read_json, write_json
from common.bdpan_runtime import configure_runtime, describe_token_search_order, load_access_token

configure_runtime()


def load_token() -> str:
    try:
        return load_access_token(__file__)
    except (FileNotFoundError, KeyError) as exc:
        print(f"❌ {exc}")
        print("已检查：")
        for candidate in describe_token_search_order(__file__):
            print(f"  - {candidate}")
        sys.exit(1)


def normalize_name(name: str, entry_type: str, ignore_extension: bool, case_insensitive: bool) -> str:
    value = Path(name).stem if ignore_extension and entry_type == "file" else name
    return value.lower() if case_insensitive else value


def child_maps(node: dict, ignore_extension: bool, case_insensitive: bool) -> tuple[dict[str, dict], list[dict]]:
    buckets: dict[str, list[dict]] = {}
    for child in node.get("children", {}).values():
        key = normalize_name(child["name"], child["type"], ignore_extension, case_insensitive)
        buckets.setdefault(key, []).append(child)

    unique: dict[str, dict] = {}
    collisions: list[dict] = []
    for key, items in buckets.items():
        if len(items) == 1:
            unique[key] = items[0]
        else:
            collisions.append(
                {
                    "normalized_name": key,
                    "entries": [{"path": item["path"], "name": item["name"], "type": item["type"]} for item in items],
                }
            )
    return unique, collisions


def compare_trees(
    left_root: dict,
    right_root: dict,
    *,
    left_kind: str,
    right_kind: str,
    left_label: str,
    right_label: str,
    ignore_extension: bool,
    case_insensitive: bool,
) -> dict:
    report = {
        "tool": "baidupan-reconcile",
        "generated_at": now_iso(),
        "left_kind": left_kind,
        "right_kind": right_kind,
        "left_label": left_label,
        "right_label": right_label,
        "left_root": left_root["path"],
        "right_root": right_root["path"],
        "ignore_extension": ignore_extension,
        "case_insensitive": case_insensitive,
        "matched_dirs": 0,
        "matched_files": 0,
        "left_only_dirs": [],
        "right_only_dirs": [],
        "left_only_files": [],
        "right_only_files": [],
        "partial_file_diffs": [],
        "whole_dir_diffs": [],
        "type_mismatches": [],
        "left_collisions": [],
        "right_collisions": [],
        "folder_diffs": [],
    }

    def compare_dirs(left_node: dict, right_node: dict, rel_path: str = "") -> None:
        left_map, left_collisions = child_maps(left_node, ignore_extension, case_insensitive)
        right_map, right_collisions = child_maps(right_node, ignore_extension, case_insensitive)
        folder_diff = {
            "folder": rel_path or ".",
            "left_path": left_node["path"],
            "right_path": right_node["path"],
            "mtime": max(int(left_node.get("mtime", 0)), int(right_node.get("mtime", 0))),
            "left_only_dirs": [],
            "right_only_dirs": [],
            "left_only_files": [],
            "right_only_files": [],
            "type_mismatches": [],
            "left_collisions": left_collisions,
            "right_collisions": right_collisions,
        }

        if left_collisions:
            report["left_collisions"].append({"folder": rel_path or ".", "entries": left_collisions})
        if right_collisions:
            report["right_collisions"].append({"folder": rel_path or ".", "entries": right_collisions})

        left_keys = set(left_map)
        right_keys = set(right_map)

        for key in sorted(left_keys - right_keys):
            child = left_map[key]
            payload = {
                "relative_path": (rel_path + "/" + child["name"]).strip("/"),
                "path": child["path"],
                "name": child["name"],
                "type": child["type"],
                "mtime": int(child.get("mtime", 0)),
                "size": int(child.get("size", 0)),
            }
            if child["type"] == "dir":
                report["left_only_dirs"].append(payload)
                report["whole_dir_diffs"].append({"side": "left", **payload})
                folder_diff["left_only_dirs"].append(payload)
            else:
                report["left_only_files"].append(payload)
                report["partial_file_diffs"].append({"side": "left", "folder": rel_path or ".", **payload})
                folder_diff["left_only_files"].append(payload)

        for key in sorted(right_keys - left_keys):
            child = right_map[key]
            payload = {
                "relative_path": (rel_path + "/" + child["name"]).strip("/"),
                "path": child["path"],
                "name": child["name"],
                "type": child["type"],
                "mtime": int(child.get("mtime", 0)),
                "size": int(child.get("size", 0)),
            }
            if child["type"] == "dir":
                report["right_only_dirs"].append(payload)
                report["whole_dir_diffs"].append({"side": "right", **payload})
                folder_diff["right_only_dirs"].append(payload)
            else:
                report["right_only_files"].append(payload)
                report["partial_file_diffs"].append({"side": "right", "folder": rel_path or ".", **payload})
                folder_diff["right_only_files"].append(payload)

        for key in sorted(left_keys & right_keys):
            left_child = left_map[key]
            right_child = right_map[key]
            if left_child["type"] != right_child["type"]:
                mismatch = {
                    "relative_path": (rel_path + "/" + left_child["name"]).strip("/"),
                    "left_type": left_child["type"],
                    "right_type": right_child["type"],
                    "left_path": left_child["path"],
                    "right_path": right_child["path"],
                }
                report["type_mismatches"].append(mismatch)
                folder_diff["type_mismatches"].append(mismatch)
                continue

            if left_child["type"] == "dir":
                report["matched_dirs"] += 1
                compare_dirs(left_child, right_child, (rel_path + "/" + left_child["name"]).strip("/"))
            else:
                report["matched_files"] += 1

        if any(
            [
                folder_diff["left_only_dirs"],
                folder_diff["right_only_dirs"],
                folder_diff["left_only_files"],
                folder_diff["right_only_files"],
                folder_diff["type_mismatches"],
                folder_diff["left_collisions"],
                folder_diff["right_collisions"],
            ]
        ):
            report["folder_diffs"].append(folder_diff)

    compare_dirs(left_root, right_root, "")
    report["folder_diffs"].sort(key=lambda item: (-item["mtime"], item["folder"]))
    report["partial_file_diffs"].sort(key=lambda item: (-item["mtime"], item["relative_path"]))
    report["whole_dir_diffs"].sort(key=lambda item: (-item["mtime"], item["relative_path"]))
    return report


def render_report(report: dict, limit: int | None = None) -> str:
    lines = [
        "差异对账报告",
        "=" * 60,
        f"左侧: {report['left_label']}",
        f"右侧: {report['right_label']}",
        f"忽略扩展名: {'是' if report['ignore_extension'] else '否'}",
        f"大小写不敏感: {'是' if report['case_insensitive'] else '否'}",
        f"匹配目录: {report['matched_dirs']}",
        f"匹配文件: {report['matched_files']}",
        f"左侧独有目录: {len(report['left_only_dirs'])}",
        f"右侧独有目录: {len(report['right_only_dirs'])}",
        f"左侧独有文件: {len(report['left_only_files'])}",
        f"右侧独有文件: {len(report['right_only_files'])}",
        f"类型不一致: {len(report['type_mismatches'])}",
        f"部分文件差异: {len(report['partial_file_diffs'])}",
    ]

    def trim(items: list[dict]) -> list[dict]:
        return items if limit is None else items[:limit]

    if report["folder_diffs"]:
        lines.extend(["", "[差异文件夹]"])
        for item in trim(report["folder_diffs"]):
            lines.append(
                f"- {item['folder']} ({format_mtime(item['mtime'])}) "
                f"L_dirs={len(item['left_only_dirs'])} R_dirs={len(item['right_only_dirs'])} "
                f"L_files={len(item['left_only_files'])} R_files={len(item['right_only_files'])}"
            )
        if limit is not None and len(report["folder_diffs"]) > limit:
            lines.append(f"... 其余 {len(report['folder_diffs']) - limit} 个文件夹未显示")

    if report["whole_dir_diffs"]:
        lines.extend(["", "[整目录差异]"])
        for item in trim(report["whole_dir_diffs"]):
            lines.append(f"- {item['side']}: {item['path']} ({format_mtime(item['mtime'])})")
        if limit is not None and len(report["whole_dir_diffs"]) > limit:
            lines.append(f"... 其余 {len(report['whole_dir_diffs']) - limit} 条目录差异未显示")

    if report["partial_file_diffs"]:
        lines.extend(["", "[部分文件差异]"])
        for item in trim(report["partial_file_diffs"]):
            lines.append(f"- {item['side']}: {item['path']} ({format_size(item['size'])}, {format_mtime(item['mtime'])})")
        if limit is not None and len(report["partial_file_diffs"]) > limit:
            lines.append(f"... 其余 {len(report['partial_file_diffs']) - limit} 条文件差异未显示")

    if report["type_mismatches"]:
        lines.extend(["", "[类型不一致]"])
        for item in trim(report["type_mismatches"]):
            lines.append(f"- {item['relative_path']} (left={item['left_type']}, right={item['right_type']})")
        if limit is not None and len(report["type_mismatches"]) > limit:
            lines.append(f"... 其余 {len(report['type_mismatches']) - limit} 条类型差异未显示")

    return "\n".join(lines)


def render_folder_summary(report: dict, limit: int | None = None) -> str:
    folder_diffs = report.get("folder_diffs", [])
    lines = [
        "差异文件夹摘要",
        "=" * 60,
        f"左侧: {report.get('left_label')}",
        f"右侧: {report.get('right_label')}",
        f"忽略扩展名: {'是' if report.get('ignore_extension') else '否'}",
        f"文件夹数: {len(folder_diffs)}",
        "",
        "[folders]",
    ]

    visible = folder_diffs if limit is None else folder_diffs[:limit]
    for item in visible:
        lines.append(
            f"- {item['folder']} ({format_mtime(item['mtime'])}) "
            f"L_dirs={len(item['left_only_dirs'])} "
            f"R_dirs={len(item['right_only_dirs'])} "
            f"L_files={len(item['left_only_files'])} "
            f"R_files={len(item['right_only_files'])} "
            f"mismatch={len(item['type_mismatches'])}"
        )
    if limit is not None and len(folder_diffs) > limit:
        lines.append(f"... 其余 {len(folder_diffs) - limit} 个文件夹未显示")
    return "\n".join(lines)


def render_partial_files(report: dict, limit: int | None = None) -> str:
    partial_diffs = report.get("partial_file_diffs", [])
    lines = [
        "部分文件差异清单",
        "=" * 60,
        f"左侧: {report.get('left_label')}",
        f"右侧: {report.get('right_label')}",
        f"忽略扩展名: {'是' if report.get('ignore_extension') else '否'}",
        f"文件数: {len(partial_diffs)}",
        "",
        "[files]",
    ]

    visible = partial_diffs if limit is None else partial_diffs[:limit]
    for item in visible:
        lines.append(
            f"- {item['side']}: {item['path']} "
            f"(folder={item['folder']}, {format_size(item['size'])}, {format_mtime(item['mtime'])})"
        )
    if limit is not None and len(partial_diffs) > limit:
        lines.append(f"... 其余 {len(partial_diffs) - limit} 条文件差异未显示")
    return "\n".join(lines)


def emit_text_and_optional_json(rendered: str, payload: dict, output: str | None, json_output: str | None, success_label: str) -> None:
    print(rendered)
    if output:
        output_path = Path(output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"✅ {success_label}文本已保存到: {output_path}")
    if json_output:
        json_path = Path(json_output).expanduser().resolve()
        write_json(json_path, payload)
        print(f"✅ {success_label}JSON 已保存到: {json_path}")


def compare_local(args: argparse.Namespace) -> int:
    token = load_token()
    client = BaiduPanInventoryClient(token)
    local_root = Path(args.local_root).expanduser().resolve()
    remote_root = normalize_remote_path(args.remote_root)
    report = compare_trees(
        build_local_tree(local_root),
        client.build_remote_tree(remote_root),
        left_kind="local",
        right_kind="remote",
        left_label=str(local_root),
        right_label=remote_root,
        ignore_extension=args.ignore_extension,
        case_insensitive=args.case_insensitive,
    )
    output_report(report, args)
    return 0


def compare_remote(args: argparse.Namespace) -> int:
    token = load_token()
    client = BaiduPanInventoryClient(token)
    left_remote = normalize_remote_path(args.left_remote)
    right_remote = normalize_remote_path(args.right_remote)
    report = compare_trees(
        client.build_remote_tree(left_remote),
        client.build_remote_tree(right_remote),
        left_kind="remote",
        right_kind="remote",
        left_label=left_remote,
        right_label=right_remote,
        ignore_extension=args.ignore_extension,
        case_insensitive=args.case_insensitive,
    )
    output_report(report, args)
    return 0


def output_report(report: dict, args: argparse.Namespace) -> None:
    rendered = render_report(report, limit=args.limit)
    emit_text_and_optional_json(rendered, report, args.output, args.json_output, "报告")


def command_folder_summary(args: argparse.Namespace) -> int:
    report = read_json(Path(args.report_file).expanduser().resolve())
    summary_payload = {
        "tool": "baidupan-reconcile-folder-summary",
        "generated_at": now_iso(),
        "source_report": str(Path(args.report_file).expanduser().resolve()),
        "left_label": report.get("left_label"),
        "right_label": report.get("right_label"),
        "ignore_extension": report.get("ignore_extension"),
        "folder_diffs": report.get("folder_diffs", []),
    }
    rendered = render_folder_summary(report, limit=args.limit)
    emit_text_and_optional_json(rendered, summary_payload, args.output, args.json_output, "摘要")
    return 0


def command_partial_files(args: argparse.Namespace) -> int:
    report = read_json(Path(args.report_file).expanduser().resolve())
    payload = {
        "tool": "baidupan-reconcile-partial-files",
        "generated_at": now_iso(),
        "source_report": str(Path(args.report_file).expanduser().resolve()),
        "left_label": report.get("left_label"),
        "right_label": report.get("right_label"),
        "ignore_extension": report.get("ignore_extension"),
        "partial_file_diffs": report.get("partial_file_diffs", []),
    }
    rendered = render_partial_files(report, limit=args.limit)
    emit_text_and_optional_json(rendered, payload, args.output, args.json_output, "清单")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="百度网盘差异对账工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare_local_parser = subparsers.add_parser("compare-local", help="比较本地目录和网盘目录")
    compare_local_parser.add_argument("local_root")
    compare_local_parser.add_argument("remote_root")

    compare_remote_parser = subparsers.add_parser("compare-remote", help="比较两个网盘目录")
    compare_remote_parser.add_argument("left_remote")
    compare_remote_parser.add_argument("right_remote")

    folder_summary_parser = subparsers.add_parser("folder-summary", help="从 JSON 报告提取差异文件夹摘要")
    folder_summary_parser.add_argument("report_file")

    partial_files_parser = subparsers.add_parser("partial-files", help="从 JSON 报告提取部分文件差异清单")
    partial_files_parser.add_argument("report_file")

    for subparser in [compare_local_parser, compare_remote_parser]:
        subparser.add_argument("--ignore-extension", action="store_true", help="忽略文件扩展名")
        subparser.add_argument("--case-insensitive", action="store_true", help="按大小写不敏感比较")
        subparser.add_argument("--limit", type=int, default=80, help="每个报告分段最多显示多少条")
        subparser.add_argument("--output", help="保存文本报告到文件")
        subparser.add_argument("--json-output", help="保存 JSON 报告到文件")

    for subparser in [folder_summary_parser, partial_files_parser]:
        subparser.add_argument("--limit", type=int, default=80, help="最多显示多少条")
        subparser.add_argument("--output", help="保存文本结果到文件")
        subparser.add_argument("--json-output", help="保存 JSON 结果到文件")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "compare-local":
        return compare_local(args)
    if args.command == "compare-remote":
        return compare_remote(args)
    if args.command == "folder-summary":
        return command_folder_summary(args)
    if args.command == "partial-files":
        return command_partial_files(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
