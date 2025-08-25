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
        logging.FileHandler('src/logs/letter_generator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LetterGenerator:
    def __init__(self):
        """初始化信件生成器"""
        # 获取当前脚本所在目录的上级目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(current_dir)

        self.dataset_dir = os.path.join(parent_dir, "dataset")  # 事件数据目录
        self.letter_examples_dir = os.path.join(parent_dir, "letter_examples")  # 示例信件目录
        self.user_profile_path = os.path.join(parent_dir, "user_profile.json")  # 用户档案

        # 加载配置
        self.system_cfg = load_system_config()
        self.letter_output_dir = self.system_cfg["letter_generation"]["output_dir"]
        self.letter_config = self.system_cfg.get('letter_generation', {})
        self.client = self._init_llm_client()

        # 线程控制
        self.running = False
        self.thread = None
        self.interval = self.letter_config.get('processing_interval', 7200)
        self.event_threshold = self.letter_config.get('event_threshold', 5)

        # 生成状态跟踪
        self.last_generation_time = None
        self.generated_letters = set()
        self._load_generation_history()

    def _init_llm_client(self) -> Optional[OpenAI]:
        """初始化LLM客户端"""
        try:
            llm_config = self.letter_config.get('llm_config', {})
            api_key = llm_config.get('api_key')
            base_url = llm_config.get('base_url')

            if not api_key:
                logger.warning("未找到API密钥")
                return None

            # 注意：公开仓库请使用占位/环境变量注入
            return OpenAI(api_key=api_key, base_url=base_url)
        except Exception as e:
            logger.error(f"初始化LLM客户端失败: {e}")
            return None

    def _load_generation_history(self):
        """加载生成历史记录"""
        try:
            history_file = "src/logs/letter_generation_history.json"
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.last_generation_time = data.get('last_generation_time')
                    self.generated_letters = set(data.get('generated_letters', []))
        except Exception as e:
            logger.error(f"加载生成历史记录失败: {e}")
            self.last_generation_time = None
            self.generated_letters = set()

    def _save_generation_history(self):
        """保存生成历史记录"""
        try:
            history_file = "src/logs/letter_generation_history.json"
            os.makedirs(os.path.dirname(history_file), exist_ok=True)
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'last_generation_time': self.last_generation_time,
                    'generated_letters': list(self.generated_letters)
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存生成历史记录失败: {e}")

    def get_dataset_files(self) -> List[str]:
        """获取dataset目录下的所有JSON文件"""
        try:
            pattern = os.path.join(self.dataset_dir, "*.json")
            files = glob.glob(pattern)
            return sorted(files)
        except Exception as e:
            logger.error(f"获取dataset文件失败: {e}")
            return []

    def count_events(self) -> int:
        """统计事件数量"""
        files = self.get_dataset_files()
        return len(files)

    def read_letter_example(self) -> str:
        """读取信件示例"""
        try:
            # 直接使用正确的路径
            example_path = os.path.join(os.path.dirname(self.letter_examples_dir), "letter_examples", "letter_ex1.txt")
            with open(example_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取信件示例失败: {e}")
            return ""

    def read_user_profile(self) -> Dict[str, Any]:
        """读取用户档案"""
        try:
            with open(self.user_profile_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取用户档案失败: {e}")
            return {}

    def read_event_data(self) -> List[Dict[str, Any]]:
        """读取事件数据"""
        events = []
        files = self.get_dataset_files()

        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    event_data = json.load(f)
                    events.append(event_data)
            except Exception as e:
                logger.error(f"读取事件文件失败 {file_path}: {e}")

        return events

    def generate_letter(self) -> Optional[str]:
        """生成信件"""
        if not self.client:
            logger.error("LLM客户端未初始化")
            return None

        try:
            # 读取所有输入数据
            letter_example = self.read_letter_example()
            user_profile = self.read_user_profile()
            events = self.read_event_data()

            if not letter_example or not user_profile or not events:
                logger.error("输入数据不完整")
                return None

            # 构建prompt
            prompt = f"""
我希望你学习以下这封范例信件的风格、语气、结构和底层逻辑，然后为我创作一封新的信。

##示例信件
{letter_example}

## 用户信息：
{json.dumps(user_profile, ensure_ascii=False, indent=2)}

## 事件数据：
{json.dumps(events, ensure_ascii=False, indent=2)}

**[分析与指令]**
在学习范例后，请在创作新信件时，严格遵循以下提炼出的核心原则：
1.  **共情式开场：** 复述对方的具体困境和话语，表明你在认真倾听。
2.  **看见感受与需求：** 从痛苦的表象深入到其背后的普世需求（如被理解、被接纳、实现价值）。
3.  **成长型视角：** 使用隐喻将痛苦重构成一次成长的旅程。
4.  **正念式建议：** 提出一个温和的、关注当下的具体行动建议，强调“体验而非解决”。
5.  **无条件的陪伴：** 以坚定的支持姿态结尾。
6.  **整体语气：** 保持极度的温柔、真诚和耐心，避免任何形式的说教和催促。

**[任务]**
现在，请你运用从范例和指令中学到的一切，为以下情境写一封信：
**新情境：**我的朋友因为重要的面试失败而感到非常沮丧和自我怀疑，他觉得自己一无是处。

**[禁止事项]**：
- 不要直接复制示例中的句子或段落
- 不要使用示例中的特定比喻或典故
- 不要保持与示例完全相同的结构

请直接返回完整的信件内容，不要包含其他说明文字。
"""
            #print(prompt)
            llm_config = self.letter_config.get('llm_config', {})
            response = self.client.chat.completions.create(
                model=llm_config.get('model', 'deepseek-chat'),
                messages=[
                    {"role": "system",
                     "content": "你是一个专业的信件写作助手，能够基于用户信息和事件数据生成温暖、个性化的信件。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=llm_config.get('temperature', 0.9),
                max_tokens=llm_config.get('max_tokens', 5000)
            )

            result = response.choices[0].message.content.strip()
            return result

        except Exception as e:
            logger.error(f"生成信件失败: {e}")
            return None

    def save_letter(self, letter_content: str) -> str:
        """保存信件"""
        try:
            # 确保输出目录存在
            os.makedirs(self.letter_output_dir, exist_ok=True)

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"letter_{timestamp}.txt"
            file_path = os.path.join(self.letter_output_dir, filename)

            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(letter_content)

            logger.info(f"信件已保存: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"保存信件失败: {e}")
            return ""

    def should_generate_letter(self) -> bool:
        """判断是否应该生成信件"""
        # 检查事件数量是否达到阈值
        event_count = self.count_events()
        if event_count < self.event_threshold:
            logger.info(f"事件数量不足，当前: {event_count}, 需要: {self.event_threshold}")
            return False

        # 检查是否已经生成过信件
        if self.last_generation_time:
            # 可以添加时间间隔检查，避免频繁生成
            pass

        return True

    def generate_and_save_letter(self) -> bool:
        """生成并保存信件"""
        try:
            logger.info("开始生成信件...")

            # 生成信件
            letter_content = self.generate_letter()
            if not letter_content:
                return False

            # 保存信件
            file_path = self.save_letter(letter_content)
            if not file_path:
                return False

            # 更新状态
            self.last_generation_time = datetime.now().isoformat()
            self.generated_letters.add(os.path.basename(file_path))
            self._save_generation_history()

            logger.info("信件生成完成")
            return True

        except Exception as e:
            logger.error(f"生成并保存信件失败: {e}")
            return False

    def start_background_thread(self):
        """启动后台生成线程"""
        if self.running:
            logger.warning("后台线程已在运行")
            return

        self.running = True

        def background_worker():
            logger.info(f"信件生成线程已启动，间隔: {self.interval}秒")
            logger.info(f"事件阈值: {self.event_threshold}")

            while self.running:
                try:
                    # 检查是否应该生成信件
                    if self.should_generate_letter():
                        success = self.generate_and_save_letter()
                        if success:
                            logger.info("信件生成成功")
                        else:
                            logger.error("信件生成失败")
                    else:
                        logger.info("等待事件数量达到阈值...")

                except Exception as e:
                    logger.error(f"后台处理出错: {e}")

                # 等待下次检查
                time.sleep(self.interval)

        self.thread = threading.Thread(target=background_worker, daemon=True)
        self.thread.start()
        logger.info("信件生成线程已启动")

    def stop_background_thread(self):
        """停止后台生成线程"""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("信件生成线程已停止")

    def get_status(self) -> Dict[str, Any]:
        """获取生成状态"""
        event_count = self.count_events()

        return {
            'event_count': event_count,
            'event_threshold': self.event_threshold,
            'can_generate': event_count >= self.event_threshold,
            'interval': self.interval,
            'last_generation_time': self.last_generation_time,
            'generated_letters_count': len(self.generated_letters),
            'running': self.running
        }

    def force_generate(self) -> bool:
        """强制生成信件（忽略阈值）"""
        logger.info("强制生成信件...")
        return self.generate_and_save_letter()


def main():
    """主函数，用于测试"""
    generator = LetterGenerator()

    # 显示状态
    status = generator.get_status()
    print(f"事件数量: {status['event_count']}")
    print(f"事件阈值: {status['event_threshold']}")
    print(f"可以生成: {status['can_generate']}")
    print(f"生成间隔: {status['interval']}秒")
    print(f"已生成信件数: {status['generated_letters_count']}")

    # 尝试生成信件
    if status['can_generate']:
        success = generator.generate_and_save_letter()
        if success:
            print("信件生成成功！")
        else:
            print("信件生成失败！")
    else:
        print("事件数量不足，无法生成信件")


if __name__ == "__main__":
    main()
