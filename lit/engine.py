# -*- coding: utf-8 -*-
"""后端桥：spawn zotero-import.ps1，从 stdout 取 `TRACKEEP_JSON ` 前缀行并 json.loads。

两个入口同构、共用 `_run_engine`：
  - `run_search`（dry-run）：只读 PubMed + 遍历 Zotero 去重预览，**绝不加 -Execute**，
    不写 Zotero、不动台账。约 30–60 秒。
  - `run_import`（Slice 3）：追加 `-Execute`，引擎自己重新完整跑一遍
    （esearch+efetch+去重+POST 导入），**不复用预览 items** → 天然满足「导入前必是
    最新检索+去重、无过期清单」（护栏⑤⑥），崩溃后重跑也自动补齐（护栏⑩）。
"""
import json
import subprocess

from lit import config

_PREFIX = "TRACKEEP_JSON "

# GUI（pythonw 无控制台）spawn 子进程时，Windows 会给子进程新建一个控制台窗——
# 就是点「检索」弹出的 PowerShell 窗。CREATE_NO_WINDOW 抑制它，引擎静默后台运行。
# getattr 兜底：非 Windows 无此 flag 时取 0（不影响开发跨平台跑测）。
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def run_search(journal, *, reldate_days=None, month=None, year=None,
               include_editorial=False, include_letter=False,
               topic_filter=None, timeout=180) -> dict:
    """spawn 引擎 dry-run，返回 TRACKEEP_JSON 解析出的 dict。

    检索窗三选一：reldate_days(int) / month("YYYY-MM") / year(int)。引擎自身会校验
    「须且只须指定一个」；这里先在 Python 侧挡一道，给出更清晰的错误。

    dry-run：末尾固定加 `-EmitJson`，**绝不加 `-Execute`**（不写 Zotero、不动台账）。
    """
    return _run_engine(journal, reldate_days=reldate_days, month=month, year=year,
                       include_editorial=include_editorial,
                       include_letter=include_letter,
                       topic_filter=topic_filter, execute=False, timeout=timeout)


def run_import(journal, *, reldate_days=None, month=None, year=None,
               include_editorial=False, include_letter=False,
               topic_filter=None, timeout=300) -> dict:
    """spawn 引擎真实导入（-Execute），返回 TRACKEEP_JSON 解析出的 dict。

    与 run_search 同构参数，但 argv **追加 `-Execute`**（真写 Zotero + 台账），
    timeout=300（比 dry-run 多 POST 每条，给更宽）。

    关键设计：导入 = 引擎自己重新完整跑一遍（esearch+efetch+去重+POST 导入），
    **不复用 dry-run 预览的 items**——天然满足「导入前必是最新检索 + 去重、无过期清单」
    （护栏⑤⑥），也让崩溃后重跑能自动补齐（台账只记成功 + 去重跳过已导入，护栏⑩）。

    返回同 schema：executed=true、counts.imported / counts.failed 有值、
    items[].status 含 imported / failed。
    """
    return _run_engine(journal, reldate_days=reldate_days, month=month, year=year,
                       include_editorial=include_editorial,
                       include_letter=include_letter,
                       topic_filter=topic_filter, execute=True, timeout=timeout)


def _run_engine(journal, *, reldate_days=None, month=None, year=None,
                include_editorial=False, include_letter=False,
                topic_filter=None, execute=False, timeout=180) -> dict:
    """run_search / run_import 的共用实现：组 argv + spawn + 解析 TRACKEEP_JSON。

    execute=False（默认）= dry-run；execute=True = 末尾追加 `-Execute` 真写。
    """
    # 护栏：spawn 前预检引擎脚本在不在——缺就给人话，别让 powershell 抛天书「找不到文件」
    if not config.ENGINE_PATH.exists():
        raise RuntimeError(
            "引擎脚本未找到：%s\n（检查 Mecha-Core 是否就位、路径是否正确）"
            % config.ENGINE_PATH)

    argv = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(config.ENGINE_PATH), "-Journal", str(journal)]

    modes = [reldate_days is not None, bool(month), year is not None]
    if sum(modes) != 1:
        raise ValueError("检索窗须且只须指定 reldate_days / month / year 之一")
    if reldate_days is not None:
        argv += ["-ReldateDays", str(int(reldate_days))]
    elif month:
        argv += ["-Month", str(month)]
    else:
        argv += ["-Year", str(int(year))]

    if include_editorial:
        argv.append("-IncludeEditorial")
    if include_letter:
        argv.append("-IncludeLetter")
    if topic_filter:
        argv += ["-TopicFilter", str(topic_filter)]
    argv.append("-EmitJson")
    if execute:
        argv.append("-Execute")   # 真写 Zotero + 台账（仅 run_import）

    # 护栏：spawn 静默运行（无弹窗）+ 超时/找不到 PowerShell 转人话，别抛原始异常串
    try:
        cp = subprocess.run(argv, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout,
                            creationflags=_NO_WINDOW)
    except FileNotFoundError:
        raise RuntimeError("未找到 PowerShell，无法运行引擎（检查系统 PATH）。")
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "引擎超时（>%d 秒）——可能 PubMed 或网络较慢，请稍后重试。" % timeout)
    if cp.returncode != 0:
        raise RuntimeError(
            f"引擎退出码 {cp.returncode}\n--- stderr ---\n{cp.stderr.strip()[-2000:]}")

    # 解析：取以 `TRACKEEP_JSON ` 开头的那行（PowerShell stdout 可能有 BOM / 混合换行，
    # 逐行 strip + 去 BOM 再判前缀）。
    line = None
    for ln in cp.stdout.splitlines():
        s = ln.strip().lstrip("﻿")
        if s.startswith(_PREFIX):
            line = s
            break
    if line is None:
        tail = cp.stdout.strip()[-500:]
        raise RuntimeError(f"stdout 未找到 TRACKEEP_JSON 行。\n--- stdout 末尾 ---\n{tail}")
    return json.loads(line[len(_PREFIX):])
