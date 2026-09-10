#!/usr/bin/env python3
"""MCP stdio-обёртка над CLI wsearch (agent-kreal/agent-web-search).

3 инструмента: wsearch_search, wsearch_fetch, wsearch_status.
Путь к CLI — АБСОЛЮТНЫЙ хардкод (в профильной сессии ~ резолвится не туда).
Восстановлено 10.09.2026 после потери файла при чистке профильного home.
"""
import json
import subprocess
import sys

CLI = "/home/hermes/.hermes/profiles/telegram/home/projects/wsearch/web-search"
CLI_CWD = "/home/hermes/.hermes/profiles/telegram/home/projects/wsearch"
TIMEOUT = 180

TOOLS = [
    {
        "name": "wsearch_search",
        "description": "Веб-поиск через wsearch: 9 провайдеров с квотным фолбеком (фолбек ДО 429) и intent-роутингом. Возвращает результаты с текстом сниппетов.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Поисковый запрос"},
                "n": {"type": "integer", "description": "Максимум результатов (по умолчанию 8)"},
                "intent": {
                    "type": "string",
                    "enum": ["auto", "docs", "research", "fact", "news", "ru", "debug"],
                    "description": "Интент запроса (auto = автоопределение)",
                },
                "freshness": {"type": "string", "enum": ["day", "week", "month"], "description": "Свежесть результатов"},
                "provider": {"type": "string", "description": "Форсировать провайдера (exa, brave, tavily, youcom, ddg, jina, linkup, parallel, zai)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "wsearch_fetch",
        "description": "Извлечение URL в markdown через wsearch: бесплатный локальный каскад (trafilatura/curl/браузер) → firecrawl для анти-бота → jina для PDF.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL страницы или PDF"},
                "max_chars": {"type": "integer", "description": "Ограничение длины вывода"},
                "provider": {"type": "string", "description": "Форсировать провайдера: firecrawl, jina, local, local-http, local-curl, local-browser"},
                "no_cache": {"type": "boolean", "description": "Игнорировать кэш (30 мин)"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "wsearch_status",
        "description": "Статус wsearch: таблица провайдеров, квоты и здоровье.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def run_cli(args):
    proc = subprocess.run(
        ["python3", CLI] + args,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        cwd=CLI_CWD,
    )
    out = proc.stdout or ""
    if proc.returncode != 0 and proc.stderr:
        out = (out + "\n[stderr]\n" + proc.stderr).strip()
    return {"output": out}


def handle_call(name, args):
    if name == "wsearch_search":
        args_list = ["search", str(args.get("query", ""))]
        if args.get("n"):
            args_list += ["-n", str(args["n"])]
        intent = args.get("intent")
        if intent and intent != "auto":
            args_list += ["--intent", intent]
        if args.get("freshness"):
            args_list += ["--freshness", args["freshness"]]
        if args.get("provider"):
            args_list += ["--provider", args["provider"]]
        return run_cli(args_list)

    if name == "wsearch_fetch":
        args_list = ["fetch", str(args.get("url", ""))]
        if args.get("max_chars"):
            args_list += ["--max-chars", str(args["max_chars"])]
        if args.get("provider"):
            args_list += ["--provider", args["provider"]]
        if args.get("no_cache"):
            args_list += ["--no-cache"]
        return run_cli(args_list)

    if name == "wsearch_status":
        return run_cli(["status"])

    return {"error": f"unknown tool {name}"}


def handle(msg):
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": msg.get("params", {}).get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "wsearch", "version": "1.1.0"},
        }}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        try:
            out = handle_call(params.get("name"), params.get("arguments", {}) or {})
            text = json.dumps(out, ensure_ascii=False)
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": text}],
            }}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": mid, "result": {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)}, ensure_ascii=False)}],
                "isError": True,
            }}
    if mid is None:
        return None
    return {"jsonrpc": "2.0", "id": mid, "result": {}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            resp = handle(msg)
        except Exception as e:
            resp = {"jsonrpc": "2.0", "id": msg.get("id"), "result": {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)}, ensure_ascii=False)}],
                "isError": True,
            }}
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
