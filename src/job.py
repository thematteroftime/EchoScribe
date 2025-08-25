import os
import re
import shutil
import logging
import gc
from typing import Tuple, Any, Optional

try:
    import torch
except Exception:
    torch = None

logger = logging.getLogger("TranscribeJob")  # 单文件转写作业日志


def extract_seq_from_filename(path: str) -> int:
    base = os.path.splitext(os.path.basename(path))[0]
    m = re.search(r'(\d+)$', base)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d+)', base)
    return int(m.group(1)) if m else -1


def parse_generate_output(res: Any) -> str:
    # 兼容不同模型返回结构，尽力提取文本
    try:
        if isinstance(res, (list, tuple)) and res:
            first = res[0]
            if isinstance(first, dict) and "text" in first:
                return first["text"] or ""
            return str(first)
        if isinstance(res, dict) and "text" in res:
            return res["text"] or ""
        return str(res)
    except Exception:
        return ""


class TranscriptionJob:
    def __init__(self, audio_path: str, model: Any, failed_dir: str):
        self.audio_path = audio_path  # 输入音频路径
        self.failed_dir = failed_dir  # 失败文件移动目录
        self.model = model  # ASR 模型实例（需实现 generate(input=...)）
        self.sequence_number = extract_seq_from_filename(audio_path)  # 序号用于排序/合并

    def run(self) -> Tuple[int, str]:
        try:
            # 检查文件是否存在
            if not os.path.exists(self.audio_path):
                logger.error("音频文件不存在: %s", self.audio_path)
                return self.sequence_number, ""
            
            # 检查文件大小
            file_size = os.path.getsize(self.audio_path)
            if file_size == 0:
                logger.error("音频文件为空: %s", self.audio_path)
                return self.sequence_number, ""
            
            # 执行转写
            logger.info("开始转写文件: %s (大小: %.2f MB)", 
                       os.path.basename(self.audio_path), file_size / (1024 * 1024))
            
            res = self.model.generate(input=self.audio_path)  # 模型推理
            text = parse_generate_output(res)
            
            # 清理GPU内存
            if torch and torch.cuda.is_available():
                torch.cuda.empty_cache()
                gc.collect()
            
            logger.info("转写完成: %s, 文本长度: %d", 
                       os.path.basename(self.audio_path), len(text))
            
            return self.sequence_number, text
            
        except torch.cuda.OutOfMemoryError as e:
            logger.error("GPU内存不足: %s", str(e))
            # 清理GPU内存
            if torch and torch.cuda.is_available():
                torch.cuda.empty_cache()
                gc.collect()
            self._move_to_failed("GPU内存不足")
            return self.sequence_number, ""
            
        except RuntimeError as e:
            if "CUDA" in str(e) or "cublas" in str(e).lower():
                logger.error("CUDA错误: %s", str(e))
                if torch and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    gc.collect()
                self._move_to_failed("CUDA错误")
            else:
                logger.error("运行时错误: %s", str(e))
                self._move_to_failed("运行时错误")
            return self.sequence_number, ""
            
        except Exception as e:
            logger.exception("转写异常: %s", str(e))
            self._move_to_failed("转写异常")
            return self.sequence_number, ""

    def _move_to_failed(self, reason: str):
        """将失败的文件移动到失败目录"""
        try:
            os.makedirs(self.failed_dir, exist_ok=True)
            failed_path = os.path.join(self.failed_dir, os.path.basename(self.audio_path))
            
            # 如果目标文件已存在，添加后缀
            if os.path.exists(failed_path):
                base, ext = os.path.splitext(failed_path)
                failed_path = f"{base}_failed{ext}"
            
            shutil.move(self.audio_path, failed_path)
            logger.info("文件已移动到失败目录: %s (原因: %s)", failed_path, reason)
            
        except Exception as e:
            logger.exception("移动失败文件失败: %s", str(e))
