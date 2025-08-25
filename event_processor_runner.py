#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件处理器启动脚本
用于启动和管理后台事件处理线程
"""

import sys
import time
import signal
import argparse
from src.event_processor import EventProcessor
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EventProcessorRunner:
    def __init__(self):
        self.processor = None
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
        """
        启动事件处理器
        
        Args:
            interval: 运行间隔（秒）
            run_once: 是否只运行一次
        """
        try:
            self.processor = EventProcessor()
            interval = self.processor.interval

            if run_once:
                logger.info("运行单次处理...")
                success = self.processor.run_once()
                if success:
                    logger.info("单次处理完成")
                else:
                    logger.error("单次处理失败")
                return

            # 启动后台线程
            logger.info(f"启动后台事件处理线程，间隔: {interval}秒")
            self.processor.start_background_thread(interval)
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
        """停止事件处理器"""
        if self.processor:
            self.processor.stop_background_thread()
        self.running = False
        logger.info("事件处理器已停止")


def main():
    """"""
    parser = argparse.ArgumentParser(description='事件处理器启动脚本')
    parser.add_argument(
        '--interval',
        type=int,
        default=60,
        help='运行间隔（秒），默认3600秒（1小时）'
    )
    parser.add_argument(
        '--run-once',
        action='store_true',
        help='只运行一次，不启动后台线程'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='LLM_detect10/config/model_config.json',
        help='配置文件路径'
    )

    args = parser.parse_args()
    """"""

    # 创建运行器
    runner = EventProcessorRunner()

    try:
        # 启动处理器
        runner.start()
    except Exception as e:
        logger.error(f"运行出错: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
