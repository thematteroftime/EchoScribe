import os
import json
import time
import threading
import glob
from datetime import datetime
from typing import Optional, List, Dict, Any
import openai
from openai import OpenAI
import logging
from .config_loader import load_system_config, load_model_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('src/logs/event_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EventProcessor:
    def __init__(self):
        """
        初始化事件处理器
        
        Args:
            config_path: 模型配置文件路径
        """
        self.archive_dir = "src/archive"  # 合并后的全文目录
        self.polished_dir = "src/polished_results"  # 润色后优先读取
        self.dataset_dir = "dataset"  # 事件 JSON 输出位置
        self.template_dir = "json_template"  # 事件模板所在目录
        self.user_profile_path = "user_profile.json"  # 用户档案索引文件
        self.flag = 0  # 内部游标（选择文件用）
        self.old_flag = 0

        # 加载配置
        self.model_cfg = load_model_config()
        self.system_cfg = load_system_config()
        self.client = self._init_llm_client()

        # 线程控制
        self.running = False
        self.thread = None
        self.interval = self.system_cfg["event_processing"]["processing_interval"]  # 运行间隔（秒）

    def _init_llm_client(self) -> Optional[OpenAI]:
        """初始化LLM客户端"""
        try:
            llm_config = self.model_cfg.get('llm_config', {})
            api_key = llm_config.get('api_key')
            base_url = llm_config.get('base_url')

            if not api_key:
                logger.warning("未找到API密钥，将使用本地模型")
                return None

            # 注意：公开仓库中请使用占位或环境变量注入
            return OpenAI(
                api_key=api_key,
                base_url=base_url
            )
        except Exception as e:
            logger.error(f"初始化LLM客户端失败: {e}")
            return None

    def get_available_files(self) -> List[str]:
        """
        获取可用的文件列表，优先返回polished文件
        
        Returns:
            文件路径列表
        """
        files = []  # 汇总候选文件路径

        # 首先检查polished_results目录
        polished_pattern = os.path.join(self.polished_dir, "polished_full_*.txt")
        polished_files = glob.glob(polished_pattern)
        files.extend(polished_files)

        # 然后检查archive目录
        archive_pattern = os.path.join(self.archive_dir, "full_*.txt")
        archive_files = glob.glob(archive_pattern)

        # 过滤掉已经有polished版本的文件
        for archive_file in archive_files:
            filename = os.path.basename(archive_file)
            polished_filename = f"polished_{filename}"
            polished_path = os.path.join(self.polished_dir, polished_filename)

            if not os.path.exists(polished_path):
                files.append(archive_file)

        return sorted(files)

    def generate_event_id(self, event_date=None):
        """生成唯一事件ID (格式: YYYYMMDD-NNN)"""
        # 使用当前日期或传入日期
        dt = event_date or datetime.now()
        date_str = dt.strftime("%Y%m%d")
        next_seq = self.flag  # 序列号从001开始

        return f"{date_str}-{next_seq:03d}"  # :03d 确保3位数字

    def select_file(self, files: List[str]) -> Optional[str]:
        """
        选择要处理的文件
        
        Args:
            files: 可用文件列表
            
        Returns:
            选中的文件路径
        """
        if not files or len(files) == self.flag:
            logger.info("没有找到可处理的文件")
            return None
        """
        print("\n可用的文件:")
        for i, file_path in enumerate(files, 1):
            filename = os.path.basename(file_path)
            print(f"{i}. {filename}")
        """
        try:
            if self.system_cfg["event_processing"]["delete_source_files"]:
                index = 0
                self.flag += 1
            else:
                index = self.flag
                self.flag += 1

            if self.old_flag <= index < (len(files)-self.old_flag) + self.flag:
                return files[index]
            else:
                logger.error("无效的选择")
                return None
        except ValueError:
            logger.error("请输入有效的数字")
            return None

    def read_file_content(self, file_path: str) -> str:
        """读取文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            return ""

    def generate_event_json(self, content: str) -> Optional[Dict[str, Any]]:
        """
        使用LLM将文本内容转换为JSON事件
        
        Args:
            content: 文本内容
            
        Returns:
            JSON事件数据
        """
        if not self.client:
            logger.error("LLM客户端未初始化")
            return None

        try:
            # 读取事件模板
            template_path = os.path.join(self.template_dir, "event_template.json")
            with open(template_path, 'r', encoding='utf-8') as f:
                template = json.load(f)

            # 构建prompt
            prompt = f"""
请分析以下文本内容，并按照提供的JSON模板格式生成一个事件记录。

文本内容：
{content}

JSON模板：
{json.dumps(template, ensure_ascii=False, indent=2)}

要求：
1. 根据文本内容提取关键信息
2. 生成唯一的事件ID（格式：YYYYMMDD-NNN）
3. 推断事件发生的时间和地点
4. 生成简洁的标题和摘要
5. 确定事件主题和标签
6. 返回完整的JSON格式数据

请直接返回JSON数据，不要包含其他说明文字。
"""

            llm_config = self.model_cfg.get('llm_config', {})
            response = self.client.chat.completions.create(
                model=llm_config.get('model', 'deepseek-chat'),
                messages=[
                    {"role": "system",
                     "content": "你是一个专业的事件分析助手，能够从文本中提取关键信息并生成结构化的事件记录。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=llm_config.get('temperature', 0.3),
                max_tokens=llm_config.get('max_tokens', 1000)
            )

            result = response.choices[0].message.content.strip()

            # 尝试解析JSON
            try:
                event_data = json.loads(result)
                event_data["id"] = self.generate_event_id()
                event_data["datetime"] = datetime.now().strftime("%Y-%m-%dT%H:%M:00")
                return event_data
            except json.JSONDecodeError:
                logger.error(f"LLM返回的不是有效JSON: {result}")
                return None

        except Exception as e:
            logger.error(f"生成事件JSON失败: {e}")
            return None

    def save_event_json(self, event_data: Dict[str, Any]) -> str:
        """
        保存事件JSON文件
        
        Args:
            event_data: 事件数据
            
        Returns:
            保存的文件路径
        """
        try:
            # 确保dataset目录存在
            os.makedirs(self.dataset_dir, exist_ok=True)

            # 生成文件名
            event_id = event_data.get('id', 'unknown')
            filename = f"{event_id}.json"
            file_path = os.path.join(self.dataset_dir, filename)

            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(event_data, f, ensure_ascii=False, indent=2)

            logger.info(f"事件JSON已保存: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"保存事件JSON失败: {e}")
            return ""

    def update_user_profile(self, event_data: Dict[str, Any]) -> bool:
        """
        更新用户档案中的事件索引
        
        Args:
            event_data: 事件数据
            
        Returns:
            是否更新成功
        """
        try:
            # 读取用户档案
            with open(self.user_profile_path, 'r', encoding='utf-8') as f:
                user_profile = json.load(f)

            # 添加新事件到索引
            new_event = {
                "id": event_data.get('id'),
                "name": event_data.get('title'),
                "tag": event_data.get('tag')
            }

            if 'event_index' not in user_profile:
                user_profile['event_index'] = []

            user_profile['event_index'].append(new_event)

            # 保存更新后的用户档案
            with open(self.user_profile_path, 'w', encoding='utf-8') as f:
                json.dump(user_profile, f, ensure_ascii=False, indent=2)

            logger.info("用户档案已更新")
            return True

        except Exception as e:
            logger.error(f"更新用户档案失败: {e}")
            return False

    def delete_source_files(self, file_paths: List[str]) -> bool:
        """
        删除源文件
        
        Args:
            file_paths: 要删除的文件路径列表
            
        Returns:
            是否删除成功
        """
        try:
            for file_path in file_paths:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"已删除文件: {file_path}")
            return True
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False

    def process_single_file(self, file_path: str, delete_after: bool = False) -> bool:
        """
        处理单个文件
        
        Args:
            file_path: 文件路径
            delete_after: 处理后是否删除
            
        Returns:
            是否处理成功
        """
        logger.info(f"开始处理文件: {file_path}")

        # 读取文件内容
        content = self.read_file_content(file_path)
        if not content:
            return False

        # 生成事件JSON
        event_data = self.generate_event_json(content)
        if not event_data:
            return False

        # 保存事件JSON
        json_path = self.save_event_json(event_data)
        if not json_path:
            return False

        # 更新用户档案
        if not self.update_user_profile(event_data):
            return False

        # 删除源文件（如果需要）
        if delete_after:
            self.delete_source_files([file_path])

        logger.info(f"文件处理完成: {file_path}")
        return True

    def run_once(self) -> bool:
        """
        运行一次处理流程
        
        Returns:
            是否成功处理了文件
        """
        try:
            # 获取可用文件
            files = self.get_available_files()
            if not files:
                logger.info("没有找到可处理的文件")
                return False

            # 选择文件
            selected_file = self.select_file(files)
            if not selected_file:
                return False

            # 询问是否删除文件
            delete_after = self.system_cfg["event_processing"]["delete_source_files"]

            # 处理文件
            success = self.process_single_file(selected_file, delete_after)

            return success

        except Exception as e:
            logger.error(f"处理流程出错: {e}")
            return False

    def start_background_thread(self, interval: int = 3600):
        """
        启动后台处理线程
        
        Args:
            interval: 运行间隔（秒）
        """
        if self.running:
            logger.warning("后台线程已在运行")
            return

        self.running = True

        def background_worker():
            logger.info(f"后台处理线程已启动，间隔: {interval}秒")
            while self.running:
                try:
                    self.run_once()
                except Exception as e:
                    logger.error(f"后台处理出错: {e}")

                # 等待下次运行
                time.sleep(self.interval)

        self.thread = threading.Thread(target=background_worker, daemon=True)
        self.thread.start()
        logger.info("后台处理线程已启动")

    def stop_background_thread(self):
        """停止后台处理线程"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("后台处理线程已停止")

    def set_interval(self, interval: int):
        """
        设置运行间隔
        
        Args:
            interval: 间隔时间（秒）
        """
        self.interval = interval
        logger.info(f"运行间隔已设置为: {interval}秒")


def main():
    """主函数，用于测试"""
    processor = EventProcessor()

    # 运行一次处理
    success = processor.run_once()

    if success:
        print("文件处理成功！")
    else:
        print("文件处理失败！")


if __name__ == "__main__":
    main()

