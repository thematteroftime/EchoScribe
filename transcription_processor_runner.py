#!/usr/bin/env python3
"""
启动脚本 - 设置环境变量和内存管理
"""

import os
import sys
import subprocess

def setup_environment():
    """设置环境变量"""
    
    # 减少第三方库的日志输出
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
    
    # CUDA相关设置
    os.environ['CUDA_LAUNCH_BLOCKING'] = '1'  # 同步CUDA操作，便于调试
    os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:128'  # 限制内存分配大小
    
    # 设置Python路径（将 src 加入 PATH 以便模块导入）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(current_dir, 'src')
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

def check_gpu_memory():
    """检查GPU内存状态"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            print(f"检测到 {gpu_count} 个GPU设备:")
            
            for i in range(gpu_count):
                props = torch.cuda.get_device_properties(i)
                total_memory = props.total_memory / (1024 ** 3)
                allocated = torch.cuda.memory_allocated(i) / (1024 ** 3)
                cached = torch.cuda.memory_reserved(i) / (1024 ** 3)
                
                print(f"  GPU {i}: {props.name}")
                print(f"    总内存: {total_memory:.1f} GB")
                print(f"    已分配: {allocated:.1f} GB")
                print(f"    已缓存: {cached:.1f} GB")
                print(f"    可用: {total_memory - allocated:.1f} GB")
                
                # 清理GPU内存
                torch.cuda.empty_cache()
                print(f"    清理后可用: {total_memory - torch.cuda.memory_allocated(i) / (1024 ** 3):.1f} GB")
        else:
            print("未检测到可用的GPU设备")
    except ImportError:
        print("PyTorch未安装，无法检查GPU状态")
    except Exception as e:
        print(f"检查GPU状态时出错: {e}")

def main():
    """主函数"""
    print("=== 语音转写系统启动器 ===")
    
    # 设置环境
    setup_environment()
    print("✓ 环境变量设置完成")
    
    # 检查GPU状态（可选）
    check_gpu_memory()
    
    # 切换到src目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.join(current_dir, 'src')
    
    print(f"✓ 切换到工作目录: {src_dir}")
    os.chdir(src_dir)
    
    # 启动主程序
    print("✓ 启动主程序...")
    try:
        subprocess.run([sys.executable, "main.py"], check=True)
    except KeyboardInterrupt:
        print("\n✓ 程序被用户中断")
    except subprocess.CalledProcessError as e:
        print(f"✗ 程序运行出错: {e}")
    except Exception as e:
        print(f"✗ 启动失败: {e}")

if __name__ == "__main__":
    main()
