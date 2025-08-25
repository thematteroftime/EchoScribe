"""
独立的润色处理器

专门处理archive目录中的文本文件，与主转写流程解耦
"""

import os
import time
import logging
import threading
from typing import List, Dict, Any, Optional
from pathlib import Path
from polish_service import PolishManager

logger = logging.getLogger("PolishProcessor")


class PolishProcessor:
    """
    独立的润色处理器
    
    监控archive目录，对新的文本文件进行润色处理
    """
    
    def __init__(self, archive_dir: str, polished_dir: str, polishing_config: Dict[str, Any]):
        """
        初始化润色处理器
        
        Args:
            archive_dir: 归档目录路径
            polished_dir: 润色结果目录
            polishing_config: 润色配置
        """
        self.archive_dir = Path(archive_dir)
        self.polished_dir = Path(polished_dir)
        self.polishing_config = polishing_config
        
        # 确保目录存在
        self.polished_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化润色管理器
        self.polish_manager = PolishManager(polishing_config, str(self.polished_dir))
        
        # 记录已处理的文件
        self.processed_files = set()
        self.processed_log = self.polished_dir / "processed_files.txt"
        self._load_processed_files()
        
        # 控制标志
        self.running = False
        self.thread = None
        
        # 从配置中获取性能参数
        performance_config = polishing_config.get("performance", {})
        self.check_interval = performance_config.get("processing_interval", 5)  # 检查间隔（秒）
        self.chunk_size = performance_config.get("chunk_size", 800)  # 分段大小
        
        logger.info("润色处理器初始化完成")
    
    def _load_processed_files(self):
        """加载已处理文件列表"""
        if self.processed_log.exists():
            try:
                with open(self.processed_log, 'r', encoding='utf-8') as f:
                    self.processed_files = set(line.strip() for line in f if line.strip())
                logger.info("加载已处理文件列表: %d 个文件", len(self.processed_files))
            except Exception as e:
                logger.error("加载已处理文件列表失败: %s", str(e))
    
    def _save_processed_files(self):
        """保存已处理文件列表"""
        try:
            with open(self.processed_log, 'w', encoding='utf-8') as f:
                for filename in sorted(self.processed_files):
                    f.write(f"{filename}\n")
        except Exception as e:
            logger.error("保存已处理文件列表失败: %s", str(e))
    
    def _get_pending_files(self) -> List[Path]:
        """获取待处理的文件列表"""
        if not self.archive_dir.exists():
            return []
        
        pending_files = []
        for file_path in self.archive_dir.glob("*.txt"):
            if file_path.name not in self.processed_files:
                pending_files.append(file_path)
        
        return sorted(pending_files)
    
    def _process_file(self, file_path: Path) -> bool:
        """
        处理单个文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 处理是否成功
        """
        try:
            logger.info("开始处理文件: %s", file_path.name)
            
            # 读取文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if not content:
                logger.warning("文件内容为空: %s", file_path.name)
                return True
            
            # 执行润色
            start_time = time.time()
            
            # 根据文本长度选择处理策略
            if len(content) < 800:  # 短文本快速处理
                polished_content = self.polish_manager.polish_text(content)
            else:  # 长文本分段处理
                logger.info("检测到长文本 (%d 字符)，启用分段处理", len(content))
                polished_content = self._polish_long_text(content)

            end_time = time.time()

            if polished_content and polished_content != content:
                # 保存润色结果
                polished_filename = f"polished_{file_path.stem}.txt"
                polished_path = self.polished_dir / polished_filename

                with open(polished_path, 'w', encoding='utf-8') as f:
                    f.write(polished_content)

                logger.info("润色完成: %s -> %s (耗时: %.2f秒)",
                           file_path.name, polished_filename, end_time - start_time)
            else:
                logger.info("润色无变化或失败: %s", file_path.name)

            # 标记为已处理
            self.processed_files.add(file_path.name)
            self._save_processed_files()

            return True

        except Exception as e:
            logger.exception("处理文件失败: %s, 错误: %s", file_path.name, str(e))
            return False

    def _polish_long_text(self, text: str) -> str:
        """
        分段处理长文本，提高响应速度

        Args:
            text: 长文本内容

        Returns:
            润色后的文本
        """
        # 降低分段阈值，更早开始分段
        if len(text) <= 600:
            return self.polish_manager.polish_text(text)

        # 根据文本长度动态调整分段大小
        if len(text) > 3000:
            # 超长文本使用更小的分段
            dynamic_chunk_size = 300
            logger.info("超长文本检测，使用小分段 (%d 字符)", dynamic_chunk_size)
        elif len(text) > 1500:
            # 长文本使用中等分段
            dynamic_chunk_size = 400
            logger.info("长文本检测，使用中等分段 (%d 字符)", dynamic_chunk_size)
        else:
            # 普通文本使用配置的分段大小
            dynamic_chunk_size = self.chunk_size

        # 按句子分段
        sentences = text.split('。')
        polished_parts = []
        total_sentences = len([s for s in sentences if s.strip()])
        processed_sentences = 0

        current_chunk = ""
        chunk_count = 0

        for sentence in sentences:
            if not sentence.strip():
                continue

            current_chunk += sentence + "。"
            processed_sentences += 1

            # 当累积的文本达到动态分段长度时，进行润色
            if len(current_chunk) >= dynamic_chunk_size:
                chunk_count += 1
                logger.info("处理第 %d 个分段 (%d 字符, %d/%d 句子)",
                           chunk_count, len(current_chunk), processed_sentences, total_sentences)

                polished_part = self.polish_manager.polish_text(current_chunk)
                if polished_part:
                    polished_parts.append(polished_part)
                    logger.info("第 %d 个分段润色成功", chunk_count)
                else:
                    polished_parts.append(current_chunk)
                    logger.warning("第 %d 个分段润色失败，使用原文", chunk_count)
                current_chunk = ""

        # 处理剩余的文本
        if current_chunk.strip():
            chunk_count += 1
            logger.info("处理最后分段 (%d 字符)", len(current_chunk))

            polished_part = self.polish_manager.polish_text(current_chunk)
            if polished_part:
                polished_parts.append(polished_part)
                logger.info("最后分段润色成功")
            else:
                polished_parts.append(current_chunk)
                logger.warning("最后分段润色失败，使用原文")

        logger.info("长文本分段处理完成，共 %d 个分段", chunk_count)
        return "".join(polished_parts)
    
    def _process_loop(self):
        """处理循环"""
        logger.info("润色处理器启动，监控目录: %s", self.archive_dir)
        
        while self.running:
            try:
                # 获取待处理文件
                pending_files = self._get_pending_files()
                
                if pending_files:
                    logger.info("发现 %d 个待处理文件", len(pending_files))
                    
                    # 处理文件
                    for file_path in pending_files:
                        if not self.running:
                            break
                        
                        success = self._process_file(file_path)
                        if not success:
                            logger.warning("文件处理失败，稍后重试: %s", file_path.name)
                        
                        # 处理间隔，避免过于频繁的API调用
                        time.sleep(1)  # 减少间隔时间
                else:
                    # 没有待处理文件，等待更长时间
                    time.sleep(self.check_interval)
                    
            except Exception as e:
                logger.exception("处理循环异常: %s", str(e))
                time.sleep(self.check_interval)
    
    def start(self):
        """启动润色处理器"""
        if self.running:
            logger.warning("润色处理器已在运行")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True, name="PolishProcessor")
        self.thread.start()
        logger.info("润色处理器已启动")
    
    def stop(self):
        """停止润色处理器"""
        if not self.running:
            return
        
        logger.info("正在停止润色处理器...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        logger.info("润色处理器已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取处理器状态"""
        pending_files = self._get_pending_files()
        return {
            "running": self.running,
            "processed_count": len(self.processed_files),
            "pending_count": len(pending_files),
            "pending_files": [f.name for f in pending_files[:5]],  # 只显示前5个
            "archive_dir": str(self.archive_dir),
            "polished_dir": str(self.polished_dir)
        }


def create_polish_processor_from_config(system_config: Dict[str, Any]) -> Optional[PolishProcessor]:
    """
    从系统配置创建润色处理器
    
    Args:
        system_config: 系统配置字典
        
    Returns:
        Optional[PolishProcessor]: 润色处理器实例，如果配置无效则返回None
    """
    polishing_config = system_config.get("polishing")
    
    if not polishing_config or not polishing_config.get("enabled", False):
        logger.info("润色功能未启用")
        return None
    
    try:
        archive_dir = system_config.get("archive_dir", "archive")
        polished_dir = system_config.get("polished_dir", "polished_results")
        
        processor = PolishProcessor(archive_dir, polished_dir, polishing_config)
        return processor
        
    except Exception as e:
        logger.error("创建润色处理器失败: %s", str(e))
        return None
