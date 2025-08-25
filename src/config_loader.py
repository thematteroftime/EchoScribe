import json
import os
from typing import Dict, Any


def load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_system_config(path: str = None) -> Dict[str, Any]:
    if path is None:
        # 获取当前脚本所在目录的上级目录中的config文件夹
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(os.path.dirname(current_dir), "config", "system_config.json")
    else:
        config_path = path
    return load_json(config_path)


def load_model_config(path: str = None) -> Dict[str, Any]:
    if path is None:
        # 获取当前脚本所在目录的上级目录中的config文件夹
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(os.path.dirname(current_dir), "config", "model_config.json")
    else:
        config_path = path
    return load_json(config_path)
