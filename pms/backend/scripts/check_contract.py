#!/usr/bin/env python3
"""
前后端契约校验脚本

扫描后端 API 路由中的 Pydantic Schema/ResponseModel，与前端 TypeScript 中的 interface 和 api 调用进行对比，
输出字段名差异报告。本脚本不依赖外部 TypeScript 解析器，仅使用 Python 标准库。

用法：
    cd pms/backend
    python scripts/check_contract.py

退出码：
    0 - 未发现契约差异
    1 - 发现差异（配合 CI 使用）
"""

from __future__ import annotations

import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------- 数据结构 ----------


@dataclass
class SchemaField:
    name: str
    type_str: str
    required: bool


@dataclass
class Schema:
    name: str
    file: str
    fields: dict[str, SchemaField] = field(default_factory=dict)


@dataclass
class Endpoint:
    method: str
    path: str  # 标准化后的全路径，例如 /v1/cycles/{cycle_id}
    file: str
    line: int
    request_schemas: list[str] = field(default_factory=list)
    response_model: str | None = None


@dataclass
class FrontendInterface:
    name: str
    file: str
    line: int
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class FrontendCall:
    method: str
    path: str  # 标准化后的路径
    file: str
    line: int
    response_type: str | None = None
    payload_keys: set[str] = field(default_factory=set)


@dataclass
class Issue:
    kind: str  # "response_field_missing" | "response_extra_field" | "request_field_missing" | "request_extra_field"
    endpoint: str
    detail: str
    file: str
    line: int


# ---------- 后端扫描 ----------


class BackendScanner(ast.NodeVisitor):
    def __init__(self) -> None:
        self.schemas: dict[str, Schema] = {}
        self.endpoints: list[Endpoint] = []
        self._current_file = ""
        self._router_prefix = ""

    def scan_file(self, path: Path) -> None:
        self._current_file = str(path.relative_to(Path.cwd()))
        self._router_prefix = ""
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            print(f"[WARN] 无法解析 {self._current_file}: {e}", file=sys.stderr)
            return
        self.visit(tree)

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        # 识别 APIRouter(prefix="...")
        if (
            len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
        ):
            call = node.value
            if isinstance(call.func, ast.Name) and call.func.id == "APIRouter":
                for kw in call.keywords:
                    if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                        self._router_prefix = kw.value.value or ""
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        if not self._is_basemodel_subclass(node):
            self.generic_visit(node)
            return

        schema = Schema(name=node.name, file=self._current_file)
        for item in node.body:
            if not isinstance(item, ast.AnnAssign) or item.target is None:
                continue
            if not isinstance(item.target, ast.Name):
                continue
            field_name = item.target.id
            type_str = self._annotation_to_str(item.annotation)
            required = item.value is None
            # 有默认值 Field(...) 仍视为必填
            if item.value is not None and isinstance(item.value, ast.Call):
                func = item.value.func
                if isinstance(func, ast.Name) and func.id == "Field":
                    required = True
            schema.fields[field_name] = SchemaField(
                name=field_name,
                type_str=type_str,
                required=required,
            )
        self.schemas[node.name] = schema
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        for decorator in node.decorator_list:
            endpoint = self._parse_route_decorator(decorator, node)
            if endpoint:
                self.endpoints.append(endpoint)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def _is_basemodel_subclass(self, node: ast.ClassDef) -> bool:
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "BaseModel":
                return True
            if isinstance(base, ast.Attribute) and base.attr == "BaseModel":
                return True
            # 处理 list[X] 等嵌套，但基类通常就是 BaseModel
        return False

    def _annotation_to_str(self, node: ast.AST | None) -> str:
        if node is None:
            return "Any"
        try:
            return ast.unparse(node)
        except Exception:  # pragma: no cover
            return "<unknown>"

    def _parse_route_decorator(
        self, decorator: ast.expr, func: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> Endpoint | None:
        if not isinstance(decorator, ast.Call):
            return None
        if not isinstance(decorator.func, ast.Attribute):
            return None
        router_var = decorator.func.value
        if not isinstance(router_var, ast.Name):
            return None
        if router_var.id != "router":
            return None

        method = decorator.func.attr.lower()
        if method not in {"get", "post", "put", "patch", "delete"}:
            return None

        path = ""
        response_model: str | None = None
        if decorator.args and isinstance(decorator.args[0], ast.Constant):
            path = decorator.args[0].value or ""

        for kw in decorator.keywords:
            if kw.arg == "response_model" and kw.value is not None:
                response_model = self._annotation_to_str(kw.value)

        # 请求体 schema：函数参数中类型为已知 BaseModel 的参数
        request_schemas: list[str] = []
        for arg in func.args.args:
            if arg.annotation is None:
                continue
            ann_str = self._annotation_to_str(arg.annotation)
            if ann_str in self.schemas:
                request_schemas.append(ann_str)

        full_path = normalize_path(f"/v1{self._router_prefix}{path}")
        return Endpoint(
            method=method,
            path=full_path,
            file=self._current_file,
            line=getattr(decorator, "lineno", 0),
            request_schemas=request_schemas,
            response_model=response_model,
        )


# ---------- 前端扫描 ----------


INTERFACE_RE = re.compile(
    r"interface\s+(\w+)\s*\{([^}]*)\}",
    re.MULTILINE | re.DOTALL,
)

API_CALL_RE = re.compile(
    r"api\.(get|post|put|patch|delete)\s*(?:<([^>]+)>)?\s*\(\s*(?:\"([^\"]+)\"|'([^']+)'|`([^`]+)`)",
    re.IGNORECASE,
)

FIELD_LINE_RE = re.compile(r"(\w+)(\??)\s*:")


def extract_payload_keys(source: str, call_start: int) -> set[str]:
    """
    从 api.xxx(path, payload) 调用中提取 payload 顶层字段名。
    使用大括号计数处理嵌套对象和数组，避免误把内层字段当顶层字段。
    """
    # 从调用开始处向后找到 path 后的逗号
    i = call_start
    paren_depth = 0
    comma_pos = -1
    while i < len(source):
        ch = source[i]
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1
            if paren_depth == 0:
                break
        elif ch == "," and paren_depth == 1 and comma_pos == -1:
            j = i + 1
            while j < len(source) and source[j] in " \t\n":
                j += 1
            if j < len(source) and source[j : j + 2] != "//":
                comma_pos = j
        i += 1

    if comma_pos == -1 or comma_pos >= len(source):
        return set()

    start = comma_pos
    ch = source[start]

    if ch == "{":
        end = _find_matching_brace(source, start, "{", "}")
        if end == -1:
            return set()
        body = source[start + 1 : end]
        return _top_level_object_keys(body)

    if ch == "[":
        end = _find_matching_brace(source, start, "[", "]")
        if end == -1:
            return set()
        body = source[start + 1 : end].strip()
        if body and body[0] == "{":
            first_obj_end = _find_matching_brace(body, 0, "{", "}")
            if first_obj_end != -1:
                return _top_level_object_keys(body[1:first_obj_end])
        return set()

    return set()


def _find_matching_brace(source: str, start: int, open_ch: str, close_ch: str) -> int:
    depth = 0
    in_string: str | None = None
    i = start
    while i < len(source):
        ch = source[i]
        if in_string:
            if ch == "\\" and i + 1 < len(source):
                i += 2
                continue
            if ch == in_string:
                in_string = None
        else:
            if ch in ('"', "'", "`"):
                in_string = ch
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return -1


def _top_level_object_keys(body: str) -> set[str]:
    """从对象体中提取顶层字段名（不进入嵌套对象/数组，忽略成员访问）。"""
    keys: set[str] = set()
    depth = 0
    in_string: str | None = None
    i = 0
    n = len(body)
    current_key: str | None = None
    last_non_space: str = ","

    def _peek_key(start: int) -> tuple[str | None, int]:
        m = re.match(r"[a-zA-Z_][a-zA-Z0-9_]*", body[start:])
        if not m:
            return None, start
        return m.group(0), start + len(m.group(0))

    while i < n:
        ch = body[i]
        if in_string:
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue

        if ch in ('"', "'"):
            if depth == 0 and current_key is None and last_non_space in ",{":
                end_quote = body.find(ch, i + 1)
                if end_quote != -1:
                    after = body[end_quote + 1 : end_quote + 2].strip()
                    if after in (":", "?"):
                        current_key = body[i + 1 : end_quote]
            in_string = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "[" and depth == 0:
            end = _find_matching_brace(body, i, "[", "]")
            if end != -1:
                i = end
                last_non_space = "]"
        elif ch == ":" and depth == 0 and current_key is not None:
            keys.add(current_key)
            current_key = None
            last_non_space = ":"
        elif ch.isidentifier() and depth == 0 and current_key is None and last_non_space in ",{":
            key, next_i = _peek_key(i)
            if key:
                rest = body[next_i:].lstrip()
                if rest.startswith(":") or rest.startswith("?"):
                    current_key = key
                    i = next_i - 1
                elif rest.startswith(",") or rest.startswith("}"):
                    keys.add(key)
                    i = next_i - 1
        elif ch == ".":
            last_non_space = "."
        elif not ch.isspace():
            last_non_space = ch
        i += 1
    return keys


def scan_frontend(web_src: Path) -> tuple[dict[str, FrontendInterface], list[FrontendCall]]:
    interfaces: dict[str, FrontendInterface] = {}
    calls: list[FrontendCall] = []

    for path in web_src.rglob("*.ts*"):
        if "/node_modules/" in str(path):
            continue
        source = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(web_src))

        # 解析 interface
        for match in INTERFACE_RE.finditer(source):
            name = match.group(1)
            body = match.group(2)
            fields: dict[str, str] = {}
            for fm in FIELD_LINE_RE.finditer(body):
                fields[fm.group(1)] = body[fm.end() :].split("\n")[0].split(";")[0].strip()
            interfaces[name] = FrontendInterface(
                name=name,
                file=rel,
                line=source[: match.start()].count("\n") + 1,
                fields=fields,
            )

        # 解析 api 调用
        for match in API_CALL_RE.finditer(source):
            method = match.group(1).lower()
            response_type = match.group(2)
            # 三个引号分组中只有一个非空
            call_path = match.group(3) or match.group(4) or match.group(5) or ""
            line = source[: match.start()].count("\n") + 1

            # 模板字面量中的 ${var} 替换为 {}，便于与后端 {param} 路径做模式匹配
            call_path = re.sub(r"\$\{[^}]+\}", "{}", call_path)

            # 尝试在同一次调用后面提取 payload 对象字面量
            payload_keys = extract_payload_keys(source, match.start())

            calls.append(
                FrontendCall(
                    method=method,
                    path=normalize_path(call_path),
                    file=rel,
                    line=line,
                    response_type=response_type.strip() if response_type else None,
                    payload_keys=payload_keys,
                )
            )

    return interfaces, calls


# ---------- 工具函数 ----------


def normalize_path(path: str) -> str:
    """统一 /api/v1 与 /v1，去除末尾斜杠，并去掉查询字符串。"""
    if path.startswith("/api/v1"):
        path = "/v1" + path[len("/api/v1") :]
    path = path.split("?")[0]
    path = path.rstrip("/") or "/"
    return path


def path_to_pattern(path: str) -> str:
    """将 /v1/cycles/{cycle_id} 转换为 /v1/cycles/{} 用于模糊匹配。"""
    return re.sub(r"\{[^}]+\}", "{}", path)


def match_frontend_call_to_endpoint(call: FrontendCall, endpoints: list[Endpoint]) -> Endpoint | None:
    call_pattern = path_to_pattern(call.path)
    for ep in endpoints:
        if ep.method != call.method:
            continue
        if path_to_pattern(ep.path) == call_pattern:
            return ep
        # 允许 /v1/cycles/123 与 /v1/cycles/{cycle_id} 匹配
        if dynamic_path_match(ep.path, call.path):
            return ep
    return None


def dynamic_path_match(backend_path: str, frontend_path: str) -> bool:
    backend_parts = backend_path.split("/")
    frontend_parts = frontend_path.split("/")
    if len(backend_parts) != len(frontend_parts):
        return False
    for bp, fp in zip(backend_parts, frontend_parts):
        if bp.startswith("{") and bp.endswith("}"):
            continue
        if bp != fp:
            return False
    return True


def unwrap_array(type_str: str | None) -> str | None:
    if type_str is None:
        return None
    type_str = type_str.strip()
    if type_str.endswith("[]"):
        return type_str[:-2].strip()
    if type_str.startswith("Array<") and type_str.endswith(">"):
        return type_str[6:-1].strip()
    return type_str


def compare_fields(
    backend_schema: Schema,
    frontend_iface: FrontendInterface,
    context: str,
) -> list[Issue]:
    issues: list[Issue] = []
    backend_names = set(backend_schema.fields.keys())
    frontend_names = set(frontend_iface.fields.keys())

    for missing in backend_names - frontend_names:
        field = backend_schema.fields[missing]
        issues.append(
            Issue(
                kind=f"{context}_field_missing",
                endpoint=backend_schema.name,
                detail=f"后端 {context} schema '{backend_schema.name}' 的字段 '{missing}' ({field.type_str}) 未在前端 interface '{frontend_iface.name}' 中定义",
                file=frontend_iface.file,
                line=frontend_iface.line,
            )
        )

    for extra in frontend_names - backend_names:
        issues.append(
            Issue(
                kind=f"{context}_extra_field",
                endpoint=backend_schema.name,
                detail=f"前端 interface '{frontend_iface.name}' 的字段 '{extra}' 在后端 {context} schema '{backend_schema.name}' 中不存在",
                file=frontend_iface.file,
                line=frontend_iface.line,
            )
        )

    return issues


# ---------- 主流程 ----------


def main() -> int:
    backend_root = Path.cwd()
    web_root = (backend_root / ".." / "web").resolve()
    api_dir = backend_root / "src" / "pms" / "api" / "v1"

    if not api_dir.exists():
        print(f"[ERROR] 未找到后端 API 目录: {api_dir}", file=sys.stderr)
        return 1

    if not web_root.exists():
        print(f"[ERROR] 未找到前端目录: {web_root}", file=sys.stderr)
        return 1

    backend_scanner = BackendScanner()
    for py_file in sorted(api_dir.glob("*.py")):
        backend_scanner.scan_file(py_file)

    interfaces, calls = scan_frontend(web_root / "src")

    issues: list[Issue] = []
    unmatched_calls: list[FrontendCall] = []

    for call in calls:
        ep = match_frontend_call_to_endpoint(call, backend_scanner.endpoints)
        if ep is None:
            unmatched_calls.append(call)
            continue

        # 响应字段对比
        if call.response_type and ep.response_model:
            inner = unwrap_array(call.response_type)
            if inner and inner in interfaces:
                # 尝试从 response_model 中解析 schema 名（支持 list[X] 和 X）
                response_schema_name = unwrap_array(ep.response_model)
                if response_schema_name and response_schema_name in backend_scanner.schemas:
                    issues.extend(
                        compare_fields(
                            backend_scanner.schemas[response_schema_name],
                            interfaces[inner],
                            "response",
                        )
                    )

        # 请求字段对比（仅处理有 inline payload 的情况）
        if call.payload_keys and ep.request_schemas:
            for schema_name in ep.request_schemas:
                schema = backend_scanner.schemas.get(schema_name)
                if schema is None:
                    continue
                backend_names = set(schema.fields.keys())
                for key in call.payload_keys - backend_names:
                    issues.append(
                        Issue(
                            kind="request_extra_field",
                            endpoint=f"{call.method.upper()} {call.path}",
                            detail=f"前端请求 payload 含字段 '{key}'，但后端请求 schema '{schema.name}' 不存在该字段",
                            file=call.file,
                            line=call.line,
                        )
                    )
                for key in backend_names - call.payload_keys:
                    field_info = schema.fields[key]
                    if field_info.required:
                        issues.append(
                            Issue(
                                kind="request_field_missing",
                                endpoint=f"{call.method.upper()} {call.path}",
                                detail=f"后端请求 schema '{schema.name}' 的必填字段 '{key}' 未在前端 payload 中出现",
                                file=call.file,
                                line=call.line,
                            )
                        )

    # 输出报告
    print("=" * 70)
    print("PMS 前后端契约校验报告")
    print("=" * 70)
    print(f"后端 schema 数量: {len(backend_scanner.schemas)}")
    print(f"后端 endpoint 数量: {len(backend_scanner.endpoints)}")
    print(f"前端 interface 数量: {len(interfaces)}")
    print(f"前端 api 调用数量: {len(calls)}")
    print()

    if issues:
        print(f"发现 {len(issues)} 处契约差异：")
        print("-" * 70)
        for idx, issue in enumerate(issues, 1):
            print(f"{idx}. [{issue.kind}] {issue.endpoint}")
            print(f"   {issue.detail}")
            print(f"   位置: {issue.file}:{issue.line}")
            print()
    else:
        print("未发现字段名级别的前后段契约差异。")

    if unmatched_calls:
        print("-" * 70)
        print(f"以下 {len(unmatched_calls)} 个前端调用未匹配到后端 endpoint（可能因路径拼接或动态路由导致）：")
        for call in unmatched_calls:
            print(f"   {call.method.upper()} {call.path}  @ {call.file}:{call.line}")
        print()

    # 同时输出一份简洁 JSON 方便 CI 解析
    summary = {
        "schema_count": len(backend_scanner.schemas),
        "endpoint_count": len(backend_scanner.endpoints),
        "interface_count": len(interfaces),
        "call_count": len(calls),
        "issue_count": len(issues),
        "unmatched_call_count": len(unmatched_calls),
        "issues": [
            {
                "kind": i.kind,
                "endpoint": i.endpoint,
                "detail": i.detail,
                "file": i.file,
                "line": i.line,
            }
            for i in issues
        ],
        "unmatched_calls": [
            {"method": c.method.upper(), "path": c.path, "file": c.file, "line": c.line}
            for c in unmatched_calls
        ],
    }

    import json

    summary_path = backend_root / "scripts" / "contract_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"详细 JSON 报告已写入: {summary_path}")

    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
