#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
事件处理器测试脚本
"""

import os
import sys
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from event_processor import EventProcessor

class TestEventProcessor:
    def setup_method(self):
        """测试前的设置"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        
        # 创建测试用的目录结构
        self.archive_dir = os.path.join(self.temp_dir, "archive")
        self.polished_dir = os.path.join(self.temp_dir, "polished_results")
        self.dataset_dir = os.path.join(self.temp_dir, "dataset")
        self.template_dir = os.path.join(self.temp_dir, "json_template")
        
        os.makedirs(self.archive_dir, exist_ok=True)
        os.makedirs(self.polished_dir, exist_ok=True)
        os.makedirs(self.dataset_dir, exist_ok=True)
        os.makedirs(self.template_dir, exist_ok=True)
        
        # 创建测试文件
        self._create_test_files()
        
        # 创建测试配置
        self.config_path = os.path.join(self.temp_dir, "test_config.json")
        self._create_test_config()
        
        # 创建用户档案
        self.user_profile_path = os.path.join(self.temp_dir, "user_profile.json")
        self._create_user_profile()
    
    def teardown_method(self):
        """测试后的清理"""
        shutil.rmtree(self.temp_dir)
    
    def _create_test_files(self):
        """创建测试文件"""
        # 创建archive文件
        archive_content = "这是一个测试会议，讨论项目进度和下一步计划。"
        with open(os.path.join(self.archive_dir, "full_000_to_006.txt"), 'w', encoding='utf-8') as f:
            f.write(archive_content)
        
        # 创建polished文件
        polished_content = "这是一个关于项目进度讨论的会议，主要讨论了当前的项目状态和下一步的计划安排。"
        with open(os.path.join(self.polished_dir, "polished_full_000_to_006.txt"), 'w', encoding='utf-8') as f:
            f.write(polished_content)
        
        # 创建事件模板
        template = {
            "id": "唯一事件标识符（格式：YYYYMMDD-NNN，如20240520-001）",
            "datetime": "事件发生时间（ISO 8601格式，精确到分钟）",
            "location": "事件发生地点（简短描述）",
            "title": "事件核心标题（20字内）",
            "summary": "事件关键内容概述（50字内）",
            "theme": "事件所属主题类别（如工作/生活/学习）",
            "tag": "事件核心标签（5字内，用于快速检索）"
        }
        with open(os.path.join(self.template_dir, "event_template.json"), 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
    
    def _create_test_config(self):
        """创建测试配置"""
        config = {
            "llm_config": {
                "api_key": "test_key",
                "base_url": "https://api.test.com/v1",
                "model": "test-model",
                "temperature": 0.3,
                "max_tokens": 1000
            }
        }
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    
    def _create_user_profile(self):
        """创建用户档案"""
        profile = {
            "name": "测试用户",
            "event_index": []
        }
        with open(self.user_profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
    
    def test_init(self):
        """测试初始化"""
        with patch('event_processor.EventProcessor._init_llm_client') as mock_init:
            mock_init.return_value = None
            processor = EventProcessor(self.config_path)
            
            assert processor.config_path == self.config_path
            assert processor.archive_dir == "LLM_detect10/src/archive"
            assert processor.polished_dir == "LLM_detect10/src/polished_results"
    
    def test_get_available_files(self):
        """测试获取可用文件"""
        with patch('event_processor.EventProcessor._init_llm_client') as mock_init:
            mock_init.return_value = None
            processor = EventProcessor(self.config_path)
            
            # 修改目录路径为测试目录
            processor.archive_dir = self.archive_dir
            processor.polished_dir = self.polished_dir
            
            files = processor.get_available_files()
            
            # 应该优先返回polished文件
            assert len(files) == 1
            assert "polished_full_000_to_006.txt" in files[0]
    
    def test_read_file_content(self):
        """测试读取文件内容"""
        with patch('event_processor.EventProcessor._init_llm_client') as mock_init:
            mock_init.return_value = None
            processor = EventProcessor(self.config_path)
            
            test_file = os.path.join(self.archive_dir, "full_000_to_006.txt")
            content = processor.read_file_content(test_file)
            
            assert "测试会议" in content
    
    def test_save_event_json(self):
        """测试保存事件JSON"""
        with patch('event_processor.EventProcessor._init_llm_client') as mock_init:
            mock_init.return_value = None
            processor = EventProcessor(self.config_path)
            
            processor.dataset_dir = self.dataset_dir
            
            event_data = {
                "id": "20250101-001",
                "datetime": "2025-01-01T10:00:00",
                "location": "会议室",
                "title": "测试会议",
                "summary": "这是一个测试会议",
                "theme": "工作",
                "tag": "会议"
            }
            
            file_path = processor.save_event_json(event_data)
            
            assert os.path.exists(file_path)
            
            # 验证保存的内容
            with open(file_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            
            assert saved_data["id"] == "20250101-001"
            assert saved_data["title"] == "测试会议"
    
    def test_update_user_profile(self):
        """测试更新用户档案"""
        with patch('event_processor.EventProcessor._init_llm_client') as mock_init:
            mock_init.return_value = None
            processor = EventProcessor(self.config_path)
            
            processor.user_profile_path = self.user_profile_path
            
            event_data = {
                "id": "20250101-001",
                "title": "测试会议",
                "tag": "会议"
            }
            
            success = processor.update_user_profile(event_data)
            
            assert success
            
            # 验证用户档案是否被更新
            with open(self.user_profile_path, 'r', encoding='utf-8') as f:
                profile = json.load(f)
            
            assert len(profile["event_index"]) == 1
            assert profile["event_index"][0]["id"] == "20250101-001"
    
    @patch('event_processor.OpenAI')
    def test_generate_event_json(self, mock_openai):
        """测试生成事件JSON"""
        # 模拟LLM响应
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "id": "20250101-001",
            "datetime": "2025-01-01T10:00:00",
            "location": "会议室",
            "title": "项目讨论会议",
            "summary": "讨论项目进度和计划",
            "theme": "工作",
            "tag": "会议"
        }, ensure_ascii=False)
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        with patch('event_processor.EventProcessor._init_llm_client') as mock_init:
            mock_init.return_value = mock_client
            processor = EventProcessor(self.config_path)
            
            processor.template_dir = self.template_dir
            
            content = "这是一个关于项目进度的会议讨论"
            event_data = processor.generate_event_json(content)
            
            assert event_data is not None
            assert event_data["id"] == "20250101-001"
            assert event_data["title"] == "项目讨论会议"

def main():
    """运行测试"""
    import pytest
    
    # 运行测试
    pytest.main([__file__, "-v"])

if __name__ == "__main__":
    main()
