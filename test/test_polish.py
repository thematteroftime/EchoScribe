#!/usr/bin/env python3
"""
润色功能测试脚本

用于测试多种润色服务是否正常工作
支持OpenAI、DeepSeek、Qwen等服务
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from ..src.polish_service import PolishManager

def test_polish_service():
    """测试润色服务"""
    
    # 测试配置 - 可以根据需要修改
    test_configs = [
        {
            "name": "DeepSeek",
            "config": {
                "enabled": True,
                "service": "deepseek",
                "api_key": "sk-a98df4e27f5f4fe08c32cddc799db555",
                "prompt_template": "你是一位专业文本编辑，要求：\\n1. 保留所有技术术语\\n2. 优化句子流畅度\\n3. 不得添加原文没有的信息\\n\\n需要润色的文本：{text}"
            }
        },
        {
            "name": "Qwen",
            "config": {
                "enabled": True,
                "service": "qwen",
                "api_key": "sk-2cec85a63c004708bd9ea453ab37e276",
                "prompt_template": "你是一位专业文本编辑，要求：\\n1. 保留所有技术术语\\n2. 优化句子流畅度\\n3. 不得添加原文没有的信息\\n\\n需要润色的文本：{text}"
            }
        },
        {
            "name": "OpenAI",
            "config": {
                "enabled": True,
                "service": "openai",
                "api_key": "your-openai-api-key",  # 请替换为您的OpenAI API密钥
                "model": "gpt-3.5-turbo",
                "prompt_template": "你是一位专业文本编辑，要求：\\n1. 保留所有技术术语\\n2. 优化句子流畅度\\n3. 不得添加原文没有的信息\\n\\n需要润色的文本：{text}"
            }
        }
    ]
    
    # 测试文本
    test_text = """
    今天天气很好，我去了公园散步。公园里有很多人在锻炼身体，
    有的在跑步，有的在打太极，还有的在遛狗。空气很新鲜，
    阳光也很温暖，让人感觉很舒服。
    """
    
    print("=== 润色功能测试 ===")
    print(f"原始文本: {test_text.strip()}")
    print("=" * 60)
    
    for test_config in test_configs:
        service_name = test_config["name"]
        config = test_config["config"]
        
        print(f"\n🔍 测试 {service_name} 服务...")
        
        # 跳过没有API密钥的配置
        if "your-openai-api-key" in config.get("api_key", ""):
            print(f"⚠️ 跳过 {service_name}：缺少API密钥")
            continue
        
        try:
            # 创建润色管理器
            polish_manager = PolishManager(config, "polished_results")
            
            if not polish_manager.enabled:
                print(f"❌ {service_name} 润色功能未启用")
                continue
            
            print(f"✅ {service_name} 润色服务初始化成功")
            
            # 执行润色
            print(f"🔄 正在使用 {service_name} 润色文本...")
            start_time = time.time()
            polished_text = polish_manager.polish_text(test_text)
            end_time = time.time()
            
            if polished_text and polished_text != test_text:
                print(f"✅ {service_name} 润色成功! (耗时: {end_time - start_time:.2f}秒)")
                print(f"润色后文本: {polished_text.strip()}")
                
                # 保存润色结果
                polished_path = polish_manager.save_polished_text(f"test_{service_name.lower()}.txt", polished_text)
                if polished_path:
                    print(f"✅ {service_name} 润色结果已保存到: {polished_path}")
                else:
                    print(f"❌ {service_name} 润色结果保存失败")
            else:
                print(f"⚠️ {service_name} 润色失败或无变化")
                
        except Exception as e:
            print(f"❌ {service_name} 测试失败: {str(e)}")
            import traceback
            traceback.print_exc()

def test_single_service():
    """测试单个服务（用于调试）"""
    
    # 选择要测试的服务
    service_config = {
        "enabled": True,
        "service": "deepseek",  # 可选: "deepseek", "qwen", "openai"
        "api_key": "sk-a98df4e27f5f4fe08c32cddc799db555",
        "prompt_template": "你是一位专业文本编辑，要求：\\n1. 保留所有技术术语\\n2. 优化句子流畅度\\n3. 不得添加原文没有的信息\\n\\n需要润色的文本：{text}"
    }
    
    test_text = "这是一个测试文本，用于验证润色功能是否正常工作。"
    
    print("=== 单服务测试 ===")
    print(f"服务类型: {service_config['service']}")
    print(f"原始文本: {test_text}")
    print("-" * 50)
    
    try:
        polish_manager = PolishManager(service_config, "polished_results")
        
        if not polish_manager.enabled:
            print("❌ 润色功能未启用")
            return
        
        print("✅ 润色服务初始化成功")
        
        import time
        start_time = time.time()
        polished_text = polish_manager.polish_text(test_text)
        end_time = time.time()
        
        if polished_text and polished_text != test_text:
            print("✅ 润色成功!")
            print(f"润色后文本: {polished_text}")
            print(f"耗时: {end_time - start_time:.2f}秒")
        else:
            print("⚠️ 润色失败或无变化")
            
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import time
    
    # 选择测试模式
    test_mode = "single"  # 可选: "all", "single"
    
    if test_mode == "all":
        test_polish_service()
    else:
        test_single_service()
