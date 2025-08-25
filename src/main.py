import logging
import time
import os
from logging.handlers import TimedRotatingFileHandler
from config_loader import load_system_config, load_model_config
from engine import SystemManager
from model_manager import ModelManager
from polish_processor import create_polish_processor_from_config

def setup_logger():
    # 设置环境变量减少第三方库的日志输出
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # 降低第三方库日志噪音
    logging.getLogger('funasr').setLevel(logging.WARNING)
    logging.getLogger('modelscope').setLevel(logging.WARNING)
    logging.getLogger('transformers').setLevel(logging.WARNING)
    logging.getLogger('torch').setLevel(logging.WARNING)
    logging.getLogger('huggingface_hub').setLevel(logging.WARNING)
    logging.getLogger('tqdm').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # 文件处理器：每天轮转
    handler = TimedRotatingFileHandler("logs/system.log", when="midnight", encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(threadName)s - %(message)s")
    handler.setFormatter(fmt)
    
    # 控制台处理器
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    
    logger.addHandler(handler)
    logger.addHandler(console)
    
    return logger

def main():
    logger = setup_logger()
    
    # 加载系统与模型配置
    system_cfg = load_system_config()
    model_cfg = load_model_config()
    
    # 预加载模型管理器（可按需使用缓存与检测 VRAM）
    mm = ModelManager(model_cfg)
    
    # 创建系统管理器（监视输入、分发转写、缓冲合并）
    manager = SystemManager(system_cfg, model_cfg, model_instances=[])
    
    # 创建独立的润色处理器（可选，由配置决定）
    polish_processor = create_polish_processor_from_config(system_cfg)
    
    try:
        logger.info("启动语音转写系统...")
        manager.start()
        
        # 启动润色处理器（如果启用）
        if polish_processor:
            logger.info("启动独立的润色处理器...")
            polish_processor.start()
        
        # 主循环：保持进程常驻
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭系统...")
        
        # 停止润色处理器
        if polish_processor:
            polish_processor.stop()
        
        # 停止系统管理器
        manager.stop()
        
        logger.info("系统已安全关闭")

if __name__ == "__main__":
    main()
