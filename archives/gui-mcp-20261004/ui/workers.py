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
    progress = Signal(object)        # 中途进度（如分批 done/total），跨线程经 Qt 排队连接到 UI

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


def run_async(owner, fn, *args, done=None, failed=None, on_progress=None,
              emit_sink=None) -> FuncWorker:
    """后台跑 fn(*args, **kwargs)：接好 done/失败回调，把线程挂到 owner._workers
    持引用防回收，结束后自动 remove + deleteLater。

    owner 没有 _workers 属性时就地建一个；主窗关闭时会 wait 各页的 _workers 收尾。
    fn 如需带关键字参数，调用方包一层闭包（run_async 的 **kwargs 只接收 done/failed）。

    on_progress：可选回调，接到 worker.progress 信号——AI 复筛分批进度用它显「批 3/8」。
    emit_sink：可选单元素 list；传入时 worker.start() **前**把 worker.progress.emit 塞进去
        （emit_sink[0] = emit），让 fn 闭包线程安全地把进度发射器传给被调函数（如
        deepseek.classify(progress=...)）。start 前绑定 = 结构性消竞态，不靠时序侥幸。
    """
    if not hasattr(owner, "_workers"):
        owner._workers = []
    w = FuncWorker(fn, *args)
    if done:
        w.done.connect(done)
    if failed:
        w.failed.connect(failed)
    if on_progress:
        w.progress.connect(on_progress)
    w.finished.connect(lambda: (owner._workers.remove(w), w.deleteLater()))
    owner._workers.append(w)
    if emit_sink is not None:
        emit_sink.append(w.progress.emit)
    w.start()
    return w
