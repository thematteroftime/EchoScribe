import queue
import threading
from typing import Dict


class MemoryBuffer:
    # 内存缓冲区：用于暂存转写分片，支持并发安全读写
    def __init__(self, max_fragments: int):
        # 最大可暂存的片段数量（用于限制内存占用）
        self.max_fragments = max_fragments
        # 用于按序列号保存文本的字典（供快速合并与读取）
        self._map: Dict[int, str] = {}
        # 互斥锁，确保多线程环境下的字典访问安全
        self._lock = threading.Lock()
        # 有界队列，用于背压控制与快速清空
        self._q = queue.Queue(maxsize=max_fragments)

    def add(self, seq: int, text: str) -> None:
        # 新增一个分片（序列号+文本）
        if seq is None:
            # 无序列号则忽略（保持上游稳健性）
            return
        try:
            # 先写入队列（可能阻塞至超时）以提供背压
            self._q.put((seq, text), timeout=2)
            # 再写入字典，使用锁保护
            with self._lock:
                self._map[seq] = text
        except queue.Full:
            # 队列已满，交由上游触发合并或重试
            raise

    def consume_all(self) -> Dict[int, str]:
        # 取出当前所有分片并清空内部存储
        with self._lock:
            items = dict(self._map)  # 拷贝以避免引用问题
            self._map.clear()
        # 清空队列（非阻塞）
        try:
            while True:
                self._q.get_nowait()
        except Exception:
            # 队列已空或异常，忽略
            pass
        return items

    def requeue(self, items: Dict[int, str]) -> None:
        # 将此前取出的分片重新放回（例如磁盘不足写回失败时）
        with self._lock:
            for k, v in items.items():
                try:
                    self._q.put_nowait((k, v))
                    self._map[k] = v
                except queue.Full:
                    # 队列满即停止回填，避免阻塞
                    break

    def size(self) -> int:
        # 当前已缓存的分片数量
        with self._lock:
            return len(self._map)
