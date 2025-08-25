#!/usr/bin/env python3
"""
润色服务性能测试脚本

测试优化后的润色服务响应速度和稳定性
"""

import sys
import os
import time
import json
from pathlib import Path

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from polish_service import PolishManager

def test_performance():
    """性能测试主函数"""
    
    # 测试配置
    test_config = {
        "enabled": True,
        "service": "deepseek",
        "api_key": "sk-a98df4e27f5f4fe08c32cddc799db555",
        "model": "deepseek-chat",
        "prompt_template": "你是一位专业文本编辑，要求：\\n1. 保留所有技术术语\\n2. 优化句子流畅度\\n3. 不得添加原文没有的信息\\n\\n需要润色的文本：{text}",
        "performance": {
            "timeout": 15,
            "max_retries": 2,
            "chunk_size": 800,
            "processing_interval": 1,
            "temperature": 0.3
        }
    }
    
    # 测试文本（不同长度）
    test_texts = [
        {
            "name": "短文本",
            "text": "今天天气很好，我去了公园散步。",
            "expected_time": 5
        },
        {
            "name": "中等文本", 
            "text": "今天天气很好，我去了公园散步。公园里有很多人在锻炼身体，有的在跑步，有的在打太极，还有的在遛狗。空气很新鲜，阳光也很温暖，让人感觉很舒服。这是一个非常适合户外活动的好天气。",
            "expected_time": 8
        },
        {
            "name": "长文本",
            "text": "今天天气很好，我去了公园散步。公园里有很多人在锻炼身体，有的在跑步，有的在打太极，还有的在遛狗。空气很新鲜，阳光也很温暖，让人感觉很舒服。这是一个非常适合户外活动的好天气。我在公园里走了一个小时，看到了很多美丽的风景，也遇到了几个朋友。我们一起聊天，分享各自的生活经历。这种轻松愉快的时光让人感到非常放松和满足。",
            "expected_time": 12
        }
    ]
    
    print("=== 润色服务性能测试 ===")
    print(f"配置: {test_config['service']} API")
    print(f"超时设置: {test_config['performance']['timeout']}秒")
    print(f"重试次数: {test_config['performance']['max_retries']}")
    print(f"分段大小: {test_config['performance']['chunk_size']}字符")
    print("=" * 50)
    
    # 创建润色管理器
    polish_manager = PolishManager(test_config, "test_polished")
    
    if not polish_manager.enabled:
        print("❌ 润色功能未启用")
        return
    
    print("✅ 润色服务初始化成功")
    print()
    
    # 执行性能测试
    results = []
    
    for test_case in test_texts:
        print(f"🔍 测试 {test_case['name']}...")
        print(f"文本长度: {len(test_case['text'])} 字符")
        print(f"预期时间: < {test_case['expected_time']} 秒")
        
        # 执行润色
        start_time = time.time()
        try:
            polished_text = polish_manager.polish_text(test_case['text'])
            end_time = time.time()
            
            processing_time = end_time - start_time
            
            if polished_text and polished_text != test_case['text']:
                status = "✅ 成功"
                if processing_time <= test_case['expected_time']:
                    performance = "✅ 优秀"
                elif processing_time <= test_case['expected_time'] * 1.5:
                    performance = "⚠️ 良好"
                else:
                    performance = "❌ 较慢"
            else:
                status = "❌ 失败"
                performance = "❌ 失败"
            
            print(f"处理时间: {processing_time:.2f} 秒")
            print(f"状态: {status}")
            print(f"性能: {performance}")
            
            results.append({
                "name": test_case['name'],
                "text_length": len(test_case['text']),
                "processing_time": processing_time,
                "expected_time": test_case['expected_time'],
                "status": status,
                "performance": performance
            })
            
        except Exception as e:
            end_time = time.time()
            processing_time = end_time - start_time
            print(f"❌ 异常: {str(e)}")
            print(f"处理时间: {processing_time:.2f} 秒")
            
            results.append({
                "name": test_case['name'],
                "text_length": len(test_case['text']),
                "processing_time": processing_time,
                "expected_time": test_case['expected_time'],
                "status": "❌ 异常",
                "performance": "❌ 异常",
                "error": str(e)
            })
        
        print("-" * 30)
    
    # 输出测试总结
    print("\n=== 性能测试总结 ===")
    successful_tests = [r for r in results if "成功" in r['status']]
    failed_tests = [r for r in results if "失败" in r['status'] or "异常" in r['status']]
    
    print(f"总测试数: {len(results)}")
    print(f"成功: {len(successful_tests)}")
    print(f"失败: {len(failed_tests)}")
    
    if successful_tests:
        avg_time = sum(r['processing_time'] for r in successful_tests) / len(successful_tests)
        print(f"平均处理时间: {avg_time:.2f} 秒")
    
    print("\n详细结果:")
    for result in results:
        print(f"  {result['name']}: {result['processing_time']:.2f}s ({result['performance']})")
    
    # 保存测试结果
    test_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "config": test_config,
        "results": results
    }
    
    results_file = Path("test_performance_results.json")
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n测试结果已保存到: {results_file}")

if __name__ == "__main__":
    test_performance()
