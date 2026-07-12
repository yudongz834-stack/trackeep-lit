# -*- coding: utf-8 -*-
"""Zotero 写 API 薄封装（仅受控建 collection 用）—— 标准库 urllib，不加新依赖。

Slice 3 只用它干一件事（护栏⑯）：检索发现该刊 collection 不存在、PI 在受控建框里
确认后，POST 创建子 collection。**现实 74 刊 collection 都已存在，此路极少触发——
建好代码即可，绝不真建。**

凭证读 `~/.config/mecha/secrets/zotero.env`（`ZOTERO_USER_ID` / `ZOTERO_API_KEY`），
**只用于请求头；token 值绝不进 print / log / 异常文本**（红线：凭证不外传）。
"""
import json
import urllib.error
import urllib.request
from pathlib import Path

ENV_PATH = Path.home() / ".config" / "mecha" / "secrets" / "zotero.env"
API_BASE = "https://api.zotero.org"
_TIMEOUT = 30


def _load_env() -> tuple[str, str]:
    """读 zotero.env → (user_id, api_key)。缺文件 / 缺字段 → ValueError / FileNotFoundError。"""
    if not ENV_PATH.exists():
        raise FileNotFoundError("凭证文件不存在：%s" % ENV_PATH)
    uid = key = None
    for ln in ENV_PATH.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, _, v = ln.partition("=")
        k, v = k.strip(), v.strip()
        if k == "ZOTERO_USER_ID":
            uid = v
        elif k == "ZOTERO_API_KEY":
            key = v
    if not uid or not key:
        raise ValueError("zotero.env 缺 ZOTERO_USER_ID 或 ZOTERO_API_KEY")
    return uid, key


def _request(method: str, path: str, body=None):
    """发 Zotero API 请求 → 解析 json。token 只进请求头，绝不进异常文本。

    path 形如 `/collections`；最终 URL = API_BASE/users/<uid><path>（uid 不进异常）。
    """
    uid, key = _load_env()
    url = "%s/users/%s%s" % (API_BASE, uid, path)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Zotero-API-Key", key)
    req.add_header("Zotero-API-Version", "3")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise RuntimeError("Zotero API HTTP %d（建 collection 失败）" % e.code) from None
    except urllib.error.URLError as e:
        raise RuntimeError("Zotero API 网络错误：%s" % e.reason) from None
    return json.loads(text) if text else {}


def list_collections() -> list[dict]:
    """GET /collections → [{key, name, parentCollection, ...}, ...]。"""
    data = _request("GET", "/collections")
    return data if isinstance(data, list) else []


def find_top_key(name: str) -> str | None:
    """按名匹配顶层 collection（parentCollection 为 falsy）→ 返回其 key。无 → None。

    受控建 collection 用：用分类名（如「胸部肿瘤与胸外科」）定位父 collection。
    """
    name = (name or "").strip()
    if not name:
        return None
    for c in list_collections():
        if c.get("parentCollection"):
            continue              # 非顶层，跳过
        if (c.get("name") or "").strip() == name:
            return c.get("key")
    return None


def create_collection(name: str, parent_key: str | None) -> str:
    """POST /collections 创建子 collection，返回新建的 key。

    body `[{"name": name, "parentCollection": parent_key}]`（parent_key 为 None/False
    → 顶层 collection）；Zotero 返回 `{"success": {"0": "<newKey>"}, ...}`。
    """
    body = [{"name": str(name), "parentCollection": parent_key or False}]
    resp = _request("POST", "/collections", body=body)
    success = resp.get("success") if isinstance(resp, dict) else None
    if isinstance(success, dict) and success:
        return str(next(iter(success.values())))
    failed = resp.get("failed") if isinstance(resp, dict) else None
    n = len(failed) if isinstance(failed, dict) else 0
    raise RuntimeError("创建 collection 失败（Zotero 拒绝 %d 项）" % n)
