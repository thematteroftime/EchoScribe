import os
import time
import threading
import logging
from typing import Dict, Optional
from buffer import MemoryBuffer

# 创建日志记录器，用于记录合并管理器的操作日志
logger = logging.getLogger("MergeManager")  # 合并相关日志输出


def has_enough_disk(path: str, min_free_gb: float) -> bool:
    """
    检查指定路径的磁盘是否有足够的可用空间
    
    Args:
        path: 要检查的磁盘路径
        min_free_gb: 所需的最小可用空间（GB）
    
    Returns:
        bool: 如果可用空间足够返回True，否则返回False
    """
    try:
        import shutil
        # 获取磁盘使用情况
        usage = shutil.disk_usage(path)
        # 计算可用空间（GB）并与阈值比较
        return (usage.free / (1024 ** 3)) >= min_free_gb
    except Exception:
        # 无法获取磁盘信息时，为不中断流程，默认允许写入
        # 注意：生产环境可改为更保守策略
        return True


class MergeManager:
    """
    合并管理器类
    
    负责将内存缓冲区中的多个转写片段合并成完整的文本文件，
    并定期将合并结果保存到归档目录中。
    """
    
    def __init__(self, buffer: MemoryBuffer, archive_dir: str, interval: int, disk_threshold_gb: float = 1.0):
        """
        初始化合并管理器
        
        Args:
            buffer: 内存缓冲区实例，存储待合并的转写片段
            archive_dir: 归档目录路径，用于保存合并后的文本文件
            interval: 定时合并的间隔时间（秒）
            disk_threshold_gb: 磁盘空间阈值（GB），低于此值时拒绝写入
        """
        self.buffer = buffer  # 待合并的分片来源
        self.archive_dir = archive_dir  # 合并文件存放目录
        self.interval = interval  # 定时合并间隔（秒）
        self.disk_threshold_gb = disk_threshold_gb  # 最低剩余磁盘阈值
        
        # 确保必要的目录存在
        os_dirs = [self.archive_dir]
        for d in os_dirs:
            os.makedirs(d, exist_ok=True)
        
        # 创建停止事件，用于控制后台线程
        self._stop = threading.Event()  # 线程停止信号
        
        # 创建并启动后台合并线程
        self._thread = threading.Thread(target=self._loop, daemon=True, name="MergeThread")
        self._thread.start()

    def _loop(self):
        """
        后台循环方法
        
        在独立线程中运行，定期检查缓冲区并执行合并操作。
        使用Event的wait方法实现定时检查，避免频繁的sleep调用。
        """
        while not self._stop.wait(self.interval):
            try:
                # 如果缓冲区中有数据，执行合并操作
                if self.buffer.size() > 0:
                    self.perform_merge(trigger="timed")
            except Exception:
                # 记录合并过程中的异常，但不中断循环
                logger.exception("定时合并异常")

    def stop(self):
        """
        停止合并管理器
        
        设置停止标志，等待后台线程结束，并执行最后一次合并操作。
        """
        # 设置停止标志
        self._stop.set()  # 发出停止信号
        # 等待后台线程结束，最多等待5秒
        self._thread.join(timeout=5)
        
        # 执行最后一次合并操作
        try:
            self.perform_merge(trigger="stop")  # 停止前进行最后一次落盘
        except Exception:
            logger.exception("stop merge failed")

    def perform_merge(self, trigger: str = "manual") -> Optional[str]:
        """
        执行合并操作
        
        从缓冲区获取所有转写片段，按序列号排序后合并成完整文本，
        并保存到归档目录中。
        
        Args:
            trigger: 触发合并的原因（"manual", "timed", "stop", "final"等）
        
        Returns:
            Optional[str]: 合并后文件的路径，如果没有数据则返回None
        """
        # 从缓冲区获取所有数据并清空缓冲区
        items: Dict[int, str] = self.buffer.consume_all()
        
        # 如果没有数据，直接返回
        if not items:
            return None
        
        # 按序列号排序，确保文本的正确顺序
        sorted_items = sorted(items.items(), key=lambda x: x[0])  # 按序列号升序
        
        # 合并所有非空文本片段，用换行符分隔
        merged_text = "\n".join(t for _, t in sorted_items if t.strip())  # 过滤空白文本
        
        # 获取序列号范围，用于生成文件名
        start = sorted_items[0][0]  # 起始序列号
        end = sorted_items[-1][0]   # 结束序列号
        
        # 根据触发原因生成不同的文件名
        fname = f"{'final' if trigger=='final' else 'full'}_{start:03d}_to_{end:03d}.txt"
        out_path = os.path.join(self.archive_dir, fname)
        
        # 检查磁盘空间是否足够
        if not has_enough_disk(self.archive_dir, self.disk_threshold_gb):
            logger.error("磁盘空间不足，回写失败并重新入队")
            # 如果磁盘空间不足，将数据重新放回缓冲区
            self.buffer.requeue(items)
            return None
        
        # 将合并后的文本写入文件
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(merged_text)
        
        # 记录合并完成的日志
        logger.info("合并完成: %s", out_path)
        return out_path
