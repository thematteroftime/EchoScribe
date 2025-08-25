#!/usr/bin/env python3
"""
润色处理器管理脚本

可以独立运行润色处理，不依赖主转写系统
"""

import sys
import os
import time
import argparse
from pathlib import Path

# 添加src目录到Python路径
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
sys.path.insert(0, str(src_dir))

from config_loader import load_system_config
from polish_processor import create_polish_processor_from_config

def main():
    parser = argparse.ArgumentParser(description="润色处理器管理工具")
    parser.add_argument("--config", default="config/system_config.json", 
                       help="系统配置文件路径")
    parser.add_argument("--status", action="store_true", 
                       help="显示处理器状态")
    parser.add_argument("--process-all", action="store_true", 
                       help="处理所有未处理的文件")
    parser.add_argument("--daemon", action="store_true", 
                       help="以守护进程模式运行")
    
    args = parser.parse_args()
    
    # 加载配置
    try:
        system_config = load_system_config(args.config)
        print(f"✓ 配置文件加载成功: {args.config}")
    except Exception as e:
        print(f"✗ 配置文件加载失败: {e}")
        return 1
    
    # 创建润色处理器
    processor = create_polish_processor_from_config(system_config)
    if not processor:
        print("✗ 润色功能未启用或配置无效")
        return 1
    
    print("✓ 润色处理器创建成功")
    
    if args.status:
        # 显示状态
        status = processor.get_status()
        print("\n=== 润色处理器状态 ===")
        print(f"运行状态: {'运行中' if status['running'] else '已停止'}")
        print(f"已处理文件数: {status['processed_count']}")
        print(f"待处理文件数: {status['pending_count']}")
        print(f"归档目录: {status['archive_dir']}")
        print(f"润色结果目录: {status['polished_dir']}")
        
        if status['pending_files']:
            print(f"待处理文件: {', '.join(status['pending_files'])}")
        
        return 0
    
    if args.process_all:
        # 处理所有未处理文件
        print("开始处理所有未处理文件...")
        processor.start()
        
        # 等待处理完成
        while True:
            status = processor.get_status()
            if status['pending_count'] == 0:
                print("✓ 所有文件处理完成")
                break
            
            print(f"待处理文件数: {status['pending_count']}")
            time.sleep(5)
        
        processor.stop()
        return 0
    
    if args.daemon:
        # 守护进程模式
        print("启动润色处理器守护进程...")
        processor.start()
        
        try:
            while True:
                time.sleep(10)
                status = processor.get_status()
                if status['pending_count'] > 0:
                    print(f"监控中... 待处理文件数: {status['pending_count']}")
        except KeyboardInterrupt:
            print("\n收到停止信号...")
        finally:
            processor.stop()
            print("润色处理器已停止")
        
        return 0
    
    # 默认交互模式
    print("\n=== 润色处理器交互模式 ===")
    print("命令:")
    print("  status  - 显示状态")
    print("  start   - 启动处理器")
    print("  stop    - 停止处理器")
    print("  process - 处理一次")
    print("  quit    - 退出")
    
    while True:
        try:
            cmd = input("\n> ").strip().lower()
            
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "status":
                status = processor.get_status()
                print(f"运行状态: {'运行中' if status['running'] else '已停止'}")
                print(f"已处理文件数: {status['processed_count']}")
                print(f"待处理文件数: {status['pending_count']}")
            elif cmd == "start":
                processor.start()
                print("✓ 处理器已启动")
            elif cmd == "stop":
                processor.stop()
                print("✓ 处理器已停止")
            elif cmd == "process":
                # 手动处理一次
                status = processor.get_status()
                if status['pending_count'] > 0:
                    print(f"处理 {status['pending_count']} 个文件...")
                    processor.start()
                    time.sleep(5)
                    processor.stop()
                    print("✓ 处理完成")
                else:
                    print("没有待处理的文件")
            else:
                print("未知命令，请使用: status, start, stop, process, quit")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"错误: {e}")
    
    # 确保处理器停止
    processor.stop()
    print("✓ 润色处理器已安全退出")
    return 0

if __name__ == "__main__":
    sys.exit(main())
