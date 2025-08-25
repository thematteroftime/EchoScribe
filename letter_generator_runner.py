#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信件生成器启动脚本
"""

import sys
import os
import time
import signal
import argparse
import logging

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.letter_generator import LetterGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LetterGeneratorRunner:
    def __init__(self):
        self.generator = None
        self.running = False

    def setup_signal_handlers(self):
        """设置信号处理器"""

        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，正在停止...")
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def start(self, run_once: bool = False):
        """启动信件生成器"""
        try:
            self.generator = LetterGenerator()

            if run_once:
                logger.info("运行单次生成...")
                success = self.generator.generate_and_save_letter()
                if success:
                    logger.info("单次生成完成")
                else:
                    logger.info("单次生成完成（条件不满足或生成失败）")
                return

            # 启动后台线程
            logger.info("启动信件生成后台线程")
            self.generator.start_background_thread()
            self.running = True

            # 设置信号处理器
            self.setup_signal_handlers()

            # 保持主线程运行
            try:
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("收到中断信号，正在停止...")
                self.stop()

        except Exception as e:
            logger.error(f"启动失败: {e}")
            self.stop()

    def stop(self):
        """停止信件生成器"""
        if self.generator:
            self.generator.stop_background_thread()
        self.running = False
        logger.info("信件生成器已停止")


def main():
    parser = argparse.ArgumentParser(description='信件生成器启动脚本')
    parser.add_argument(
        '--once',
        action='store_true',
        help='只运行一次，不启动后台线程'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='强制生成，忽略事件数量阈值'
    )

    args = parser.parse_args()

    # 创建运行器
    runner = LetterGeneratorRunner()

    try:
        # 启动生成器
        runner.start(run_once=args.once)
    except Exception as e:
        logger.error(f"运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
