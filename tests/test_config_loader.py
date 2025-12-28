#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试配置加载器
"""

import os
import pytest
import tempfile
import shutil
import yaml

from src.utils.config.config_loader import (
    merge_configs,
    file_has_changed,
    load_yaml_file,
    load_config_directory,
    load_all_yaml_files,
    get_config,
    _expand_env_vars,
    _file_mtimes,
    _file_hashes
)


@pytest.fixture
def temp_config_dir():
    """创建临时配置目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def reset_config_cache():
    """每个测试前重置配置缓存"""
    import src.utils.config.config_loader as loader
    loader._file_mtimes.clear()
    loader._file_hashes.clear()
    loader._first_load = True
    yield


class TestMergeConfigs:
    """测试配置合并函数"""
    
    def test_simple_merge(self):
        """测试简单合并"""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = merge_configs(base, override)
        
        assert result == {"a": 1, "b": 3, "c": 4}
    
    def test_deep_merge(self):
        """测试深度合并"""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 20, "z": 30}}
        result = merge_configs(base, override)
        
        assert result == {"a": {"x": 1, "y": 20, "z": 30}, "b": 3}
    
    def test_override_non_dict_with_dict(self):
        """测试用字典覆盖非字典值"""
        base = {"a": 1}
        override = {"a": {"x": 2}}
        result = merge_configs(base, override)
        
        assert result == {"a": {"x": 2}}
    
    def test_empty_base(self):
        """测试空基础配置"""
        result = merge_configs({}, {"a": 1})
        assert result == {"a": 1}
    
    def test_empty_override(self):
        """测试空覆盖配置"""
        base = {"a": 1}
        result = merge_configs(base, {})
        assert result == {"a": 1}


class TestExpandEnvVars:
    """测试环境变量替换"""
    
    def test_expand_string(self):
        """测试字符串中的环境变量"""
        os.environ["TEST_VAR"] = "hello"
        result = _expand_env_vars("Value: ${TEST_VAR}")
        assert result == "Value: hello"
        del os.environ["TEST_VAR"]
    
    def test_expand_dict(self):
        """测试字典中的环境变量"""
        os.environ["TEST_KEY"] = "value123"
        result = _expand_env_vars({"key": "${TEST_KEY}"})
        assert result == {"key": "value123"}
        del os.environ["TEST_KEY"]
    
    def test_expand_list(self):
        """测试列表中的环境变量"""
        os.environ["TEST_ITEM"] = "item1"
        result = _expand_env_vars(["${TEST_ITEM}", "item2"])
        assert result == ["item1", "item2"]
        del os.environ["TEST_ITEM"]
    
    def test_missing_env_var(self):
        """测试不存在的环境变量保持原值"""
        result = _expand_env_vars("${NONEXISTENT_VAR}")
        assert result == "${NONEXISTENT_VAR}"
    
    def test_non_string_passthrough(self):
        """测试非字符串类型直接返回"""
        assert _expand_env_vars(123) == 123
        assert _expand_env_vars(True) is True
        assert _expand_env_vars(None) is None


class TestFileHasChanged:
    """测试文件变更检测"""
    
    def test_nonexistent_file(self):
        """测试不存在的文件"""
        assert file_has_changed("/nonexistent/file.yaml") is False
    
    def test_first_load(self, temp_config_dir):
        """测试首次加载"""
        config_file = os.path.join(temp_config_dir, "test.yaml")
        with open(config_file, 'w') as f:
            f.write("key: value")
        
        assert file_has_changed(config_file) is True
    
    def test_unchanged_file(self, temp_config_dir):
        """测试未修改的文件"""
        config_file = os.path.join(temp_config_dir, "test.yaml")
        with open(config_file, 'w') as f:
            f.write("key: value")
        
        # 首次加载
        file_has_changed(config_file)
        # 第二次检查（未修改）
        import src.utils.config.config_loader as loader
        loader._first_load = False
        
        assert file_has_changed(config_file) is False


class TestLoadYamlFile:
    """测试 YAML 文件加载"""
    
    def test_load_valid_yaml(self, temp_config_dir):
        """测试加载有效 YAML"""
        config_file = os.path.join(temp_config_dir, "test.yaml")
        with open(config_file, 'w') as f:
            yaml.dump({"key": "value", "nested": {"x": 1}}, f)
        
        result = load_yaml_file(config_file)
        assert result == {"key": "value", "nested": {"x": 1}}
    
    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        result = load_yaml_file("/nonexistent/file.yaml")
        assert result == {}
    
    def test_load_empty_yaml(self, temp_config_dir):
        """测试加载空 YAML"""
        config_file = os.path.join(temp_config_dir, "empty.yaml")
        with open(config_file, 'w') as f:
            f.write("")
        
        result = load_yaml_file(config_file)
        assert result == {}


class TestLoadConfigDirectory:
    """测试配置目录加载"""
    
    def test_load_with_main_yaml(self, temp_config_dir):
        """测试有 main.yaml 的目录"""
        # 创建 main.yaml
        main_config = {"imports": ["other.yaml"], "main_key": "main_value"}
        with open(os.path.join(temp_config_dir, "main.yaml"), 'w') as f:
            yaml.dump(main_config, f)
        
        # 创建 other.yaml
        with open(os.path.join(temp_config_dir, "other.yaml"), 'w') as f:
            yaml.dump({"other_key": "other_value"}, f)
        
        result = load_config_directory(temp_config_dir)
        
        assert "main_key" in result
        assert "other_key" in result
        assert "imports" not in result  # imports 应被移除
    
    def test_load_without_main_yaml(self, temp_config_dir):
        """测试没有 main.yaml 的目录"""
        # 创建多个 yaml 文件
        with open(os.path.join(temp_config_dir, "a.yaml"), 'w') as f:
            yaml.dump({"a": 1}, f)
        with open(os.path.join(temp_config_dir, "b.yaml"), 'w') as f:
            yaml.dump({"b": 2}, f)
        
        result = load_config_directory(temp_config_dir)
        
        assert result.get("a") == 1
        assert result.get("b") == 2
    
    def test_main_yaml_without_imports(self, temp_config_dir):
        """测试 main.yaml 没有 imports 字段"""
        with open(os.path.join(temp_config_dir, "main.yaml"), 'w') as f:
            yaml.dump({"only_main": True}, f)
        
        result = load_config_directory(temp_config_dir)
        assert result == {"only_main": True}


class TestLoadAllYamlFiles:
    """测试加载所有 YAML 文件"""
    
    def test_alphabetical_order(self, temp_config_dir):
        """测试按字母顺序加载"""
        # 创建多个文件
        with open(os.path.join(temp_config_dir, "z.yaml"), 'w') as f:
            yaml.dump({"key": "z_value"}, f)
        with open(os.path.join(temp_config_dir, "a.yaml"), 'w') as f:
            yaml.dump({"key": "a_value"}, f)
        
        # a.yaml 先加载，z.yaml 后加载并覆盖
        result = load_all_yaml_files(temp_config_dir)
        assert result["key"] == "z_value"
    
    def test_both_yaml_extensions(self, temp_config_dir):
        """测试 .yaml 和 .yml 扩展名"""
        with open(os.path.join(temp_config_dir, "config.yaml"), 'w') as f:
            yaml.dump({"yaml_key": 1}, f)
        with open(os.path.join(temp_config_dir, "settings.yml"), 'w') as f:
            yaml.dump({"yml_key": 2}, f)
        
        result = load_all_yaml_files(temp_config_dir)
        assert "yaml_key" in result
        assert "yml_key" in result


class TestGetConfig:
    """测试 get_config 函数"""
    
    def test_get_config_by_name(self, temp_config_dir):
        """测试按名称获取配置"""
        # 这个测试需要项目的 config 目录存在
        # 我们测试默认配置功能
        result = get_config(default_config={"default": "value"})
        assert "default" in result
    
    def test_get_config_with_default(self):
        """测试带默认配置"""
        result = get_config(
            config_path="/nonexistent/path",
            default_config={"fallback": True}
        )
        assert result.get("fallback") is True
    
    def test_get_config_from_path(self, temp_config_dir):
        """测试从指定路径获取配置"""
        config_file = os.path.join(temp_config_dir, "custom.yaml")
        with open(config_file, 'w') as f:
            yaml.dump({"custom": "config"}, f)
        
        result = get_config(config_path=config_file)
        assert result.get("custom") == "config"
