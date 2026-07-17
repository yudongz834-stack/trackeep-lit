# -*- coding: utf-8 -*-
"""后台线程：耗时操作（spawn 引擎检索，约 30–60 秒）放线程里跑，界面不卡死。

从 mecha-quant 复制后裁剪：本项目无 quant 包，删掉 UpdateWorker/EventOpWorker/
ScanWorker/BatchWorker 四个 quant 专用 worker，只留通用 FuncWorker + run_async。
"""
from PySide6.QtCore import QThread, Signal


class FuncWorker(QThread):
    """通用后台执行器：跑任意函数，结束回传结果。"""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self._fn, self._args, self._kwargs = fn, args, kwargs

    def run(self) -> None:
        try:
            self.done.emit(self._fn(*self._args, **self._kwargs))
        except BaseException as e:
            # 兜 BaseException（KeyboardInterrupt/SystemExit 不被 except Exception 捕获）：
            # 仍发 failed 信号让 UI 复位 _running，否则线程收尾但界面永卡；不 re-raise。
            self.failed.emit(f"{type(e).__name__}: {e}")


def run_async(owner, fn, *args, done=None, failed=None) -> FuncWorker:
    """后台跑 fn(*args, **kwargs)：接好 done/失败回调，把线程挂到 owner._workers
    持引用防回收，结束后自动 remove + deleteLater。

    owner 没有 _workers 属性时就地建一个；主窗关闭时会 wait 各页的 _workers 收尾。
    fn 如需带关键字参数，调用方包一层闭包（run_async 的 **kwargs 只接收 done/failed）。
    """
    if not hasattr(owner, "_workers"):
        owner._workers = []
    w = FuncWorker(fn, *args)
    if done:
        w.done.connect(done)
    if failed:
        w.failed.connect(failed)
    w.finished.connect(lambda: (owner._workers.remove(w), w.deleteLater()))
    owner._workers.append(w)
    w.start()
    return w
