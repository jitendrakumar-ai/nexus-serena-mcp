#!/usr/bin/env python3
import sys, os, json, ast, re, argparse

VERSION = "1.2.0"
SERVER_NAME = "nexus-serena-mcp"

TOOLS = [
    {"name": "find_symbol_definition", "description": "Locate symbol definitions in AST", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "path": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "find_symbol_references", "description": "Find symbol usage references", "inputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}, "path": {"type": "string"}}, "required": ["symbol"]}},
    {"name": "surgical_replace_symbol", "description": "Surgically refactor symbol", "inputSchema": {"type": "object", "properties": {"old_symbol": {"type": "string"}, "new_symbol": {"type": "string"}, "file_path": {"type": "string"}}, "required": ["old_symbol", "new_symbol", "file_path"]}},
    {"name": "resolve_library_docs", "description": "Resolve docstrings for modules", "inputSchema": {"type": "object", "properties": {"library_name": {"type": "string"}, "symbol_name": {"type": "string"}}, "required": ["library_name"]}},
    {"name": "project_onboarding_memory", "description": "Analyze repository structural memory", "inputSchema": {"type": "object", "properties": {"root_path": {"type": "string"}}}}
]

class SerenaMCPEngine:
    @staticmethod
    def find_symbol_definition(symbol, path=None):
        target = path or "."
        matches = []
        files = [target] if os.path.isfile(target) else [os.path.join(r, f) for r, _, fs in os.walk(target) for f in fs if f.endswith('.py')]
        for fpath in files:
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    tree = ast.parse(f.read(), filename=fpath)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == symbol:
                        matches.append({"file": fpath, "line": node.lineno, "col": node.col_offset, "type": type(node).__name__, "name": symbol})
                    elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == symbol:
                        matches.append({"file": fpath, "line": node.lineno, "col": node.col_offset, "type": "VariableAssignment", "name": symbol})
            except Exception: pass
        return {"symbol": symbol, "found_count": len(matches), "definitions": matches}

    @staticmethod
    def find_symbol_references(symbol, path=None):
        target = path or "."
        refs = []
        files = [target] if os.path.isfile(target) else [os.path.join(r, f) for r, _, fs in os.walk(target) for f in fs if f.endswith('.py')]
        pat = re.compile(r'\b' + re.escape(symbol) + r'\b')
        for fpath in files:
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f, 1):
                        if pat.search(line):
                            refs.append({"file": fpath, "line": i, "content": line.strip()})
            except Exception: pass
        return {"symbol": symbol, "reference_count": len(refs), "references": refs}

    @staticmethod
    def surgical_replace_symbol(old_symbol, new_symbol, file_path):
        if not os.path.isfile(file_path): return {"success": False, "error": "File not found"}
        try:
            with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            new_c, count = re.subn(r'\b' + re.escape(old_symbol) + r'\b', new_symbol, content)
            if count > 0:
                with open(file_path, 'w', encoding='utf-8') as f: f.write(new_c)
            return {"success": True, "file": file_path, "replacements_made": count}
        except Exception as e: return {"success": False, "error": str(e)}

    @staticmethod
    def resolve_library_docs(library_name, symbol_name=None):
        try:
            mod = __import__(library_name)
            target = mod
            if symbol_name:
                for part in symbol_name.split('.'): target = getattr(target, part)
            doc = getattr(target, "__doc__", "") or "No docstring found."
            return {"library": library_name, "symbol": symbol_name, "docstring": doc.strip(), "type": str(type(target))}
        except Exception as e: return {"library": library_name, "symbol": symbol_name, "error": str(e)}

    @staticmethod
    def project_onboarding_memory(root_path=None):
        target = root_path or "."
        py_files, other_files = [], []
        for r, _, fs in os.walk(target):
            if ".git" in r or "__pycache__" in r: continue
            for f in fs:
                rel = os.path.relpath(os.path.join(r, f), target)
                (py_files if f.endswith('.py') else other_files).append(rel)
        return {"root_path": os.path.abspath(target), "python_files_count": len(py_files), "other_files_count": len(other_files), "key_files": py_files[:10] + other_files[:10]}

def run_self_test():
    print(f"[{SERVER_NAME}] Running Self-Test v{VERSION}...")
    res1 = SerenaMCPEngine.find_symbol_definition("run_self_test", __file__)
    assert res1["found_count"] >= 1, "Failed find_symbol_definition"
    res2 = SerenaMCPEngine.find_symbol_references("SerenaMCPEngine", __file__)
    assert res2["reference_count"] > 0, "Failed find_symbol_references"
    res3 = SerenaMCPEngine.resolve_library_docs("json", "dumps")
    assert "docstring" in res3, "Failed resolve_library_docs"
    res4 = SerenaMCPEngine.project_onboarding_memory(".")
    assert "python_files_count" in res4, "Failed project_onboarding_memory"
    res5 = SerenaMCPEngine.surgical_replace_symbol("nonexistent_sym_99", "new_sym", __file__)
    assert res5["success"] is True, "Failed surgical_replace_symbol"
    print(f"[{SERVER_NAME}] ALL SELF-TESTS PASSED (v{VERSION})")
    return 0

def main():
    parser = argparse.ArgumentParser(description="Nexus Serena MCP Server v1.2.0")
    parser.add_argument("--self-test", action="store_true", help="Run self-test suite and exit")
    args = parser.parse_args()
    if args.self_test: sys.exit(run_self_test())
    while True:
        try:
            line = sys.stdin.readline()
            if not line: break
            req = json.loads(line)
            mid, method = req.get("id"), req.get("method")
            if method == "initialize":
                res = {"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": SERVER_NAME, "version": VERSION}}}
            elif method == "tools/list":
                res = {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
            elif method == "tools/call":
                p = req.get("params", {})
                name, args_dict = p.get("name"), p.get("arguments", {})
                handler = getattr(SerenaMCPEngine, name, None)
                out = handler(**args_dict) if handler else {"error": f"Unknown tool {name}"}
                res = {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(out, indent=2)}]}}
            else:
                res = {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "Method not found"}}
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()
        except Exception: pass

if __name__ == "__main__":
    main()
