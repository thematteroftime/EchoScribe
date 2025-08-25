import os
import time
import logging
import threading
from typing import Dict, Any, Optional, List, Tuple

try:
    import torch
except Exception:
    torch = None

try:
    from funasr import AutoModel
except Exception:
    AutoModel = None

logger = logging.getLogger("ModelManager")  # 模型加载与缓存管理


class ModelManager:
    """
    模型管理器类 - 支持模型实例缓存和线程安全
    """
    
    # 类级别的模型实例缓存
    _model_cache = {}  # 进程级模型缓存：避免重复下载/初始化
    _cache_lock = threading.Lock()  # 保护缓存的互斥锁
    
    def __init__(self, model_config: Dict[str, Any], models_dir: str = "models"):
        self.model_config = model_config
        self.models_dir = models_dir
        os.makedirs(self.models_dir, exist_ok=True)

    def detect_vram_gb(self) -> float:
        if torch is None or not getattr(torch, "cuda", None):
            return 0.0
        try:
            if not torch.cuda.is_available():
                return 0.0
            props = torch.cuda.get_device_properties(0)
            return props.total_memory / (1024 ** 3)
        except Exception:
            return 0.0

    def get_default_model_cfg(self) -> Dict[str, Any]:
        name = self.model_config.get("default_model")
        return self.model_config["models"].get(name, {})

    def load_model_instance(self, name: Optional[str] = None) -> Any:
        """
        加载模型实例，支持缓存机制避免重复加载
        """
        cfg = self.get_default_model_cfg() if name is None else self.model_config["models"].get(name)
        if not cfg:
            raise RuntimeError("模型配置缺失")
        
        device = cfg.get("device", "auto")
        if device == "auto":
            device = "cuda" if (torch and torch.cuda.is_available()) else "cpu"
        
        model_id = cfg.get("model_id")
        if AutoModel is None:
            raise RuntimeError("AutoModel not available")
        
        # 生成缓存键
        cache_key = f"{model_id}_{device}"
        
        # 检查缓存中是否已有模型实例
        with self._cache_lock:
            if cache_key in self._model_cache:
                logger.info("使用缓存的模型实例: %s", cache_key)
                return self._model_cache[cache_key]
        
        # 如果缓存中没有，则创建新实例
        try:
            logger.info("创建新的模型实例: %s", cache_key)
            
            # 设置环境变量减少日志输出
            os.environ['TOKENIZERS_PARALLELISM'] = 'false'
            
            # 创建模型实例
            model_instance = AutoModel(
                model=model_id, 
                device=device, 
                disable_update=cfg.get("disable_update", True)
            )
            
            # 将实例添加到缓存
            with self._cache_lock:
                self._model_cache[cache_key] = model_instance
            
            logger.info("模型实例创建成功: %s", cache_key)
            return model_instance
            
        except Exception as e:
            logger.error("模型实例创建失败: %s", str(e))
            raise

    def clear_cache(self):
        """清空模型缓存"""
        with self._cache_lock:
            self._model_cache.clear()
            logger.info("模型缓存已清空")

    def get_cache_info(self) -> Dict[str, int]:
        """获取缓存信息"""
        with self._cache_lock:
            return {
                "cached_models": len(self._model_cache),
                "cache_keys": list(self._model_cache.keys())
            }

    def select_models_by_vram(self, ranking_cfg: Dict[str, Any], max_models: int = 3) -> List[Dict[str, Any]]:
        vram = self.detect_vram_gb()
        candidates = [m for m in ranking_cfg.get("models", []) if vram >= float(m.get("min_vram_gb", 0)) or vram == 0.0]
        selected = sorted(candidates, key=lambda x: x["precision_rank"])[:max_models]
        logger.info("Selected models by vram: %s", [m.get("id") for m in selected])
        return selected
