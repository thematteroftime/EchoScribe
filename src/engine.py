import os
import time
import logging
import threading
import shutil
import torch
from typing import Dict, Any, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
from config_loader import load_system_config, load_model_config
from buffer import MemoryBuffer
from job import TranscriptionJob
from merge import MergeManager
from model_manager import ModelManager

# 创建引擎模块的日志记录器
logger = logging.getLogger("Engine")  # 引擎（系统管理器）模块日志


class SystemManager:
    """
    系统管理器类
    
    这是整个音频转写系统的核心控制器，负责：
    1. 监控输入目录中的音频文件
    2. 调度转写任务到工作线程
    3. 管理模型实例和缓冲区
    4. 协调各个组件的工作
    """
    
    def __init__(self, sys_cfg: Dict[str, Any],
                       model_cfg: Dict[str, Any],
                       model_instances: List[Tuple[Dict[str, Any], Any]] = None):
        """
        初始化系统管理器
        
        Args:
            sys_cfg: 系统配置字典，包含各种系统参数
            model_cfg: 模型配置字典，包含模型相关参数
            model_instances: 预加载的模型实例列表，每个元素为(配置, 模型实例)的元组
        """
        self.cfg = sys_cfg  # 系统运行配置
        self.model_cfg = model_cfg  # 模型配置
        self.models = model_instances or []  # 预加载模型（可空）
        self.save_file = self.cfg["transcription"]["save_file"]  # 是否归档原始音频

        # 初始化目录结构和日志系统
        self._init_dirs()
        self._init_logger()

        # 创建内存缓冲区，用于存储转写结果
        self.buffer = MemoryBuffer(max_fragments=int(self.cfg["transcription"]["buffer_max_fragments"]))
        
        # 创建合并管理器，负责定期将缓冲区数据合并成文件
        self.merge_manager = MergeManager(
            self.buffer, 
            self.cfg["archive_dir"], 
            int(self.cfg["transcription"]["merge_interval"]), 
            float(self.cfg.get("disk_threshold_gb", 1.0))
        )
        
        # 创建任务队列，用于存储待处理的音频文件路径
        # 兼容性处理：某些Python版本可能没有threading.Queue
        self.task_queue = threading.Queue() if hasattr(threading, "Queue") else __import__("queue").Queue()
        
        # 创建线程池执行器，用于并发处理转写任务
        # 根据GPU内存限制并发数量，避免内存溢出
        concurrency = int(self.cfg["transcription"]["concurrency"])  # 目标并发
        if torch and torch.cuda.is_available():
            vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            if vram_gb < 6:  # 如果GPU内存小于6GB，减少并发数
                concurrency = min(concurrency, 2)
                logger.info("GPU内存较小(%.1fGB)，调整并发数为: %d", vram_gb, concurrency)
        
        self.executor = ThreadPoolExecutor(max_workers=concurrency)  # 工作线程池

        # 用于跟踪已处理的文件，避免重复处理
        self._seen = {}  # 文件名 -> 最近 mtime，避免重复处理
        
        # 运行状态控制事件
        self._running = threading.Event()  # 运行状态标志
        
        # 文件监控线程
        self._watcher_thread = threading.Thread(target=self._watcher, daemon=True, name="WatcherThread")
        
        # 工作线程列表
        self._worker_threads: List[threading.Thread] = []

    def _init_dirs(self):
        """
        初始化必要的目录结构
        
        创建系统运行所需的各种目录，包括输入目录、归档目录、失败目录等
        """
        # 需要创建的目录列表
        dirs_to_create = [
            self.cfg["input_dir"],      # 输入音频文件目录
            self.cfg["archive_dir"],    # 归档目录
            self.cfg["failed_dir"],     # 失败文件目录
            #self.cfg.get("polished_dir", "polished_results")  # 润色结果目录
        ]
        
        # 创建所有必要的目录
        for d in dirs_to_create:
            os.makedirs(d, exist_ok=True)
        
        # 创建日志目录
        os.makedirs("logs", exist_ok=True)

    def _init_logger(self):
        """
        初始化日志系统
        
        注意：实际的日志配置在main.py中完成，这里只是占位符
        """
        # logger configured in main; keep here for completeness
        pass  # 实际日志在 main.py 配置

    def start(self):
        """
        启动系统管理器
        
        启动文件监控线程和工作线程，开始处理音频转写任务
        """
        # 设置运行标志
        self._running.set()
        
        # 启动文件监控线程
        self._watcher_thread.start()
        
        # 创建并启动工作线程
        concurrency = self.executor._max_workers
        for i in range(concurrency):
            t = threading.Thread(target=self._worker, daemon=True, name=f"WorkerThread-{i}")
            t.start()
            self._worker_threads.append(t)
        
        logger.info("SystemManager started")

    def stop(self):
        """
        停止系统管理器
        
        停止所有线程，关闭线程池，并停止合并管理器
        """
        # 清除运行标志，通知所有线程停止
        self._running.clear()
        
        # 等待文件监控线程结束，最多等待2秒
        self._watcher_thread.join(timeout=2)
        
        # 关闭线程池执行器，等待所有任务完成
        self.executor.shutdown(wait=True)
        
        # 停止合并管理器
        self.merge_manager.stop()
        
        logger.info("SystemManager stopped")

    def _watcher(self):
        """
        文件监控线程方法
        
        持续监控输入目录，发现新的音频文件时将其添加到任务队列
        """
        input_dir = self.cfg["input_dir"]
        
        while self._running.is_set():
            try:
                # 遍历输入目录中的所有文件
                for fname in os.listdir(input_dir):
                    # 只处理.wav文件
                    if not fname.lower().endswith(".wav"):
                        continue
                    
                    fpath = os.path.join(input_dir, fname)
                    
                    # 获取文件的修改时间，用于检测文件是否被修改
                    try:
                        mtime = os.path.getmtime(fpath)
                    except Exception:
                        mtime = None
                    
                    # 检查文件是否已经处理过，或者是否被修改过
                    seen_m = self._seen.get(fname)
                    if seen_m is None or seen_m != mtime:
                        # 更新文件的修改时间记录
                        self._seen[fname] = mtime
                        # 将文件路径添加到任务队列
                        self.task_queue.put(fpath)
                
                # 短暂休眠，避免过度占用CPU
                time.sleep(0.5)  # 降低轮询频率以减轻 IO 压力
                
            except Exception:
                # 记录监控过程中的异常，但不中断监控
                logger.exception("Watcher error")
                time.sleep(1)

    def _select_model(self):
        """
        选择要使用的模型实例
        
        Returns:
            Tuple[Dict[str, Any], Any]: 返回(模型配置, 模型实例)的元组
        
        Raises:
            RuntimeError: 当没有可用模型时抛出异常
        """
        # 如果有预加载的模型实例，使用第一个
        if self.models:
            return self.models[0]
        
        # 如果没有预加载的模型，尝试动态加载默认模型
        mm = ModelManager(self.model_cfg)
        try:
            inst = mm.load_model_instance()
            return (self.model_cfg["models"][self.model_cfg.get("default_model")], inst)
        except Exception:
            raise RuntimeError("no model available")

    def _worker(self):
        """
        工作线程方法
        
        从任务队列中获取音频文件路径，执行转写任务，并将结果添加到缓冲区
        """
        while self._running.is_set():
            try:
                # 从任务队列中获取文件路径，最多等待1秒
                fpath = self.task_queue.get(timeout=1)
            except Exception:
                # 如果超时或出现异常，短暂休眠后继续
                time.sleep(0.1)
                continue
            
            # 选择要使用的模型
            entry, model = self._select_model()
            
            # 创建转写任务并执行
            job = TranscriptionJob(fpath, model, self.cfg["failed_dir"])  # 构建并执行作业
            seq, text = job.run()
            
            # 如果转写成功且有文本内容
            if text and text.strip():  # 丢弃空白转写
                try:
                    # 将转写结果添加到缓冲区
                    self.buffer.add(seq, text)
                except Exception:
                    # 如果缓冲区添加失败，触发合并操作
                    logger.exception("buffer add failed; triggering merge")
                    self.merge_manager.perform_merge(trigger="buffer_full")
                    
                    # 再次尝试添加到缓冲区
                    try:
                        self.buffer.add(seq, text)
                    except Exception:
                        # 如果再次失败，记录错误并丢弃数据
                        logger.error("double add failed; dropping")
                
                # 将原始音频文件移动到归档目录
                if(self.save_file):  # 可选：归档原始 wav
                    try:
                        dest_dir = os.path.join(self.cfg["archive_dir"], "originals")
                        os.makedirs(dest_dir, exist_ok=True)
                        shutil.move(fpath, os.path.join(dest_dir, os.path.basename(fpath)))
                    except Exception:
                        logger.exception("move original failed")
                
                # 记录转写完成的日志
                logger.info("transcribed seq=%s len=%d", seq, len(text))
            else:
                # 如果转写结果为空，记录警告
                # 注意：失败文件的处理已经在TranscriptionJob中完成
                logger.warning("empty transcript, moved to failed handled in job")
