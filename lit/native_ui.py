"""Windows UI Automation 原生界面桥；只认唯一 Zotero 进程和唯一题录。"""
import json
from pathlib import Path
import re
import sys
import time
import subprocess


def window():
    import psutil
    from pywinauto import Desktop
    matches = []
    for candidate in Desktop(backend='uia').windows():
        try:
            executable = Path(psutil.Process(candidate.process_id()).exe())
            if (executable == Path('E:/Software/zotero_APP/zotero.exe')
                    and candidate.element_info.class_name == 'MozillaWindowClass'
                    and len([c for c in candidate.descendants(control_type='Tree')
                             if c.element_info.automation_id == 'item-tree-main-default']) == 1):
                matches.append(candidate)
        except (psutil.Error, OSError):
            continue
    if len(matches) != 1:
        raise RuntimeError('未找到唯一 Zotero 主窗口')
    return matches[0]


def one(elements, label):
    values = list(elements)
    if len(values) != 1:
        raise RuntimeError(label + '无法唯一确认')
    return values[0]


def foreground(main):
    """鼠标输入落在前台窗口；UIA 找到后台控件并不等于可安全点击。"""
    import ctypes
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    if user32.GetForegroundWindow() != main.handle:
        raise RuntimeError('Zotero 不在前台，停止原生输入')


def focus_target(main, title, doi, pmid):
    main.set_focus()
    foreground(main)
    row = selected(main, title, doi, pmid)
    foreground(main)
    return row


def find_menu(main, title, doi, pmid, timeout=3):
    deadline = time.monotonic() + timeout
    while True:
        foreground(main)
        selected(main, title, doi, pmid)
        matches = [x for x in main.descendants(control_type='MenuItem')
                   if x.is_visible() and x.is_enabled()
                   and x.window_text() in ('查找全文', 'Find Full Text', 'Find Available PDF')]
        if len(matches) == 1:
            foreground(main)
            return matches[0]
        if len(matches) > 1 or time.monotonic() >= deadline:
            raise RuntimeError('查找全文菜单无法唯一确认：匹配数=' + str(len(matches)) + '，前台主窗已核对')
        time.sleep(.15)


def dialog_belongs(main, candidate):
    """Zotero 公共文件框可能由子进程承载，以原生 owner 和可执行文件确权。"""
    import ctypes
    import psutil
    user32 = ctypes.windll.user32
    user32.GetWindow.restype = ctypes.c_void_p
    user32.GetWindow.argtypes = (ctypes.c_void_p, ctypes.c_uint)
    return (candidate.element_info.class_name == '#32770'
            and user32.GetWindow(candidate.handle, 4) == main.handle
            and Path(psutil.Process(candidate.process_id()).exe())
            == Path(psutil.Process(main.process_id()).exe()))


def file_dialog(main, windows):
    """只认主窗拥有的文件框，兼容 UIA 把模态框嵌于主窗树下。"""
    matches = []
    candidates = list(windows) + main.descendants(control_type='Window')
    seen = set()
    for candidate in candidates:
        if candidate.handle in seen:
            continue
        seen.add(candidate.handle)
        if candidate.handle == main.handle or not dialog_belongs(main, candidate):
            continue
        edits = [x for x in candidate.descendants(control_type='Edit')
                 if x.element_info.automation_id == '1148' and x.is_visible()]
        # Windows 公共文件框既有直接 Edit，也有 ComboBox 1148 内嵌 Edit。
        for combo in candidate.descendants(control_type='ComboBox'):
            if combo.element_info.automation_id == '1148' and combo.is_visible():
                for edit in combo.descendants(control_type='Edit'):
                    if edit.is_visible() and edit not in edits:
                        edits.append(edit)
        buttons = [x for x in candidate.descendants(control_type='Button')
                   if x.element_info.automation_id == '1' and x.is_visible()]
        if len(edits) == 1 and len(buttons) == 1:
            matches.append((candidate, edits[0], buttons[0]))
    return one(matches, '文件选择框')


def selected(main, title, doi=None, pmid=None):
    tree = one((c for c in main.descendants(control_type='Tree') if c.element_info.automation_id == 'item-tree-main-default'), '题录列表')
    rows = []
    for row in tree.descendants(control_type='TreeItem'):
        try:
            if row.is_selected():
                rows.append(row)
        except Exception:
            continue
    row = one(rows, '已选题录')
    texts = [c.window_text() for c in row.descendants()]
    if title not in texts:
        raise RuntimeError('当前选中题录标题不符')
    if doi is not None:
        values = {x.window_text(): x.get_value() for x in main.descendants(control_type='Edit') if x.window_text() in ('DOI', 'PMID', '其他', 'Extra')}
        if values.get('DOI', '').lower() != doi.lower():
            raise RuntimeError('当前题录 DOI 不符')
        extra = values.get('其他', values.get('Extra', ''))
        if values.get('PMID') != pmid and re.findall(r'(?im)^PMID:\s*(\d+)\s*$', extra) != [pmid]:
            raise RuntimeError('当前题录 PMID 不符')
    return row


def select(parent, title, doi=None, pmid=None):
    main = window()
    handle, pid = main.handle, main.process_id()
    import psutil
    executable = psutil.Process(pid).exe()
    subprocess.run([executable, '-url', 'zotero://select/library/items/' + parent], timeout=15)
    time.sleep(1.5)
    main = window()
    if (main.handle, main.process_id()) != (handle, pid):
        raise RuntimeError('Zotero 窗口归属变化')
    row = selected(main, title, doi, pmid)
    return main, row


def run(payload):
    parent, title = payload['parent_key'], payload['title']
    if not re.fullmatch(r'[A-Z0-9]{8}', parent) or not isinstance(title, str) or not title:
        raise ValueError('目标题录参数无效')
    main, row = select(parent, title, payload['doi'], payload['pmid'])
    selected(main, title, payload['doi'], payload['pmid'])
    if payload['action'] == 'find':
        # click_input 最终注入屏幕鼠标，必须先前置并核验窗口，不能只信 UIA 定位。
        row = focus_target(main, title, payload['doi'], payload['pmid'])
        foreground(main)
        row.click_input(button='right')
        menu = find_menu(main, title, payload['doi'], payload['pmid'])
        menu.invoke()
    elif payload['action'] == 'attach':
        path = Path(payload['path']).resolve(strict=True)
        if path.suffix.lower() != '.pdf':
            raise ValueError('只允许已验证 PDF')
        button = one((c for c in main.descendants(control_type='Button') if c.element_info.automation_id == 'zotero-tb-attachment-add'), '附件按钮')
        button.invoke()
        time.sleep(.3)
        main = window()
        selected(main, title, payload['doi'], payload['pmid'])
        menu = one((x for x in main.descendants(control_type='MenuItem') if x.is_visible() and x.window_text() in ('附加文件...', '附加文件…', 'Attach Stored Copy of File…', 'Attach Stored Copy of File...')), '存储副本菜单')
        menu.invoke()
        time.sleep(.5)
        from pywinauto import Desktop
        dialog, edit, open_button = file_dialog(main, Desktop(backend='uia').windows(process=main.process_id()))
        edit.set_edit_text(str(path))
        if edit.get_value() != str(path):
            raise RuntimeError('文件名控件读回不符')
        current = window()
        if (current.handle, current.process_id()) != (main.handle, main.process_id()):
            raise RuntimeError('Zotero 主窗口归属变化，停止附加')
        selected(current, title, payload['doi'], payload['pmid'])
        open_button.invoke()
    else:
        raise ValueError('不支持的原生动作')
    return {'ok': True, 'action': payload['action'], 'parent_key': parent, 'status': 'triggered_unverified'}


if __name__ == '__main__':
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        print(json.dumps(run(json.load(sys.stdin)), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({'ok': False, 'reason': str(error) if isinstance(error, (ValueError, RuntimeError)) else '原生控件操作失败，停止待核'}, ensure_ascii=False))
        raise SystemExit(2)
