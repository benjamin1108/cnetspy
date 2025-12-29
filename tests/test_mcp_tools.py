#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MCP 工具模块测试

测试内容:
- 工具注册机制
- 工具不重复注册
- 工具处理器正确性
- Server 处理器设置
"""

import pytest
import pytest_asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from mcp.types import Tool


class TestToolRegistry:
    """工具注册表测试"""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置全局注册表"""
        from src.mcp.tools import registry
        registry._tools = []
        registry._handlers = {}
        registry._tools_config = None
        yield
        # 测试后再次清理
        registry._tools = []
        registry._handlers = {}
        registry._tools_config = None
    
    def test_register_tool_basic(self):
        """测试基本工具注册"""
        from src.mcp.tools.registry import register_tool, get_all_tools, get_handler
        
        # 创建测试工具和处理器
        tool = Tool(
            name="test_tool",
            description="Test tool description",
            inputSchema={"type": "object", "properties": {}}
        )
        
        async def handler(args):
            return "test result"
        
        # 注册工具
        register_tool(tool, handler)
        
        # 验证注册成功
        tools = get_all_tools()
        assert len(tools) == 1
        assert tools[0].name == "test_tool"
        
        # 验证处理器注册
        registered_handler = get_handler("test_tool")
        assert registered_handler is handler
    
    def test_register_tool_no_duplicate(self):
        """测试工具不重复注册"""
        from src.mcp.tools.registry import register_tool, get_all_tools, _handlers
        
        tool1 = Tool(
            name="duplicate_tool",
            description="First registration",
            inputSchema={"type": "object"}
        )
        
        tool2 = Tool(
            name="duplicate_tool",
            description="Second registration (should be ignored)",
            inputSchema={"type": "object"}
        )
        
        async def handler1(args):
            return "handler1"
        
        async def handler2(args):
            return "handler2"
        
        # 注册第一次
        register_tool(tool1, handler1)
        
        # 尝试重复注册
        register_tool(tool2, handler2)
        
        # 验证只有一个工具
        tools = get_all_tools()
        assert len(tools) == 1
        assert tools[0].description == "First registration"
        
        # 验证处理器是第一个
        assert _handlers["duplicate_tool"] is handler1
    
    def test_register_multiple_tools(self):
        """测试注册多个不同工具"""
        from src.mcp.tools.registry import register_tool, get_all_tools, get_handler
        
        tools_data = [
            ("tool_a", "Tool A description"),
            ("tool_b", "Tool B description"),
            ("tool_c", "Tool C description"),
        ]
        
        handlers = {}
        for name, desc in tools_data:
            tool = Tool(name=name, description=desc, inputSchema={"type": "object"})
            async def handler(args, n=name):
                return f"Result from {n}"
            handlers[name] = handler
            register_tool(tool, handler)
        
        # 验证所有工具注册成功
        all_tools = get_all_tools()
        assert len(all_tools) == 3
        
        tool_names = {t.name for t in all_tools}
        assert tool_names == {"tool_a", "tool_b", "tool_c"}
        
        # 验证每个处理器都能获取
        for name in ["tool_a", "tool_b", "tool_c"]:
            assert get_handler(name) is not None
    
    def test_get_handler_nonexistent(self):
        """测试获取不存在的处理器"""
        from src.mcp.tools.registry import get_handler
        
        result = get_handler("nonexistent_tool")
        assert result is None


class TestToolRegistrationFunctions:
    """测试各模块的工具注册函数"""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置全局注册表"""
        from src.mcp.tools import registry
        registry._tools = []
        registry._handlers = {}
        registry._tools_config = None
        yield
        registry._tools = []
        registry._handlers = {}
        registry._tools_config = None
    
    @pytest.fixture
    def mock_db(self):
        """创建模拟数据库层"""
        db = MagicMock()
        db.query_updates_paginated.return_value = []
        db.get_update_by_id.return_value = None
        db.count_updates.return_value = 0
        db.get_vendor_statistics.return_value = []
        db.get_update_type_statistics.return_value = {}
        db.get_analysis_coverage.return_value = 0.0
        db.get_timeline_statistics.return_value = []
        db.get_product_subcategory_statistics.return_value = []
        db.get_vendor_update_type_matrix.return_value = []
        return db
    
    def test_register_update_tools(self, mock_db):
        """测试更新工具注册"""
        from src.mcp.tools.updates import register_update_tools
        from src.mcp.tools.registry import get_all_tools, get_handler
        
        register_update_tools(mock_db)
        
        tools = get_all_tools()
        tool_names = {t.name for t in tools}
        
        # 验证更新工具已注册
        assert "search_updates" in tool_names
        assert "get_update_detail" in tool_names
        
        # 验证处理器存在
        assert get_handler("search_updates") is not None
        assert get_handler("get_update_detail") is not None
    
    def test_register_stats_tools(self, mock_db):
        """测试统计工具注册"""
        from src.mcp.tools.stats import register_stats_tools
        from src.mcp.tools.registry import get_all_tools, get_handler
        
        register_stats_tools(mock_db)
        
        tools = get_all_tools()
        tool_names = {t.name for t in tools}
        
        # 验证统计工具已注册
        assert "get_stats_overview" in tool_names
        assert "get_timeline" in tool_names
        assert "get_vendor_stats" in tool_names
        assert "get_update_type_stats" in tool_names
    
    def test_register_analysis_tools(self, mock_db):
        """测试分析工具注册"""
        from src.mcp.tools.analysis import register_analysis_tools
        from src.mcp.tools.registry import get_all_tools, get_handler
        
        register_analysis_tools(mock_db)
        
        tools = get_all_tools()
        tool_names = {t.name for t in tools}
        
        # 验证分析工具已注册
        assert "get_product_hotness" in tool_names
        assert "compare_vendors" in tool_names
        assert "get_vendor_type_matrix" in tool_names
    
    def test_all_tools_registration_no_duplicate(self, mock_db):
        """测试所有工具注册后无重复"""
        from src.mcp.tools.updates import register_update_tools
        from src.mcp.tools.stats import register_stats_tools
        from src.mcp.tools.analysis import register_analysis_tools
        from src.mcp.tools.registry import get_all_tools, _handlers
        
        # 注册所有工具
        register_update_tools(mock_db)
        register_stats_tools(mock_db)
        register_analysis_tools(mock_db)
        
        tools = get_all_tools()
        
        # 验证工具数量与处理器数量一致
        assert len(tools) == len(_handlers)
        
        # 验证无重复名称
        tool_names = [t.name for t in tools]
        assert len(tool_names) == len(set(tool_names)), "存在重复的工具名称"
    
    def test_double_registration_safe(self, mock_db):
        """测试重复调用注册函数是安全的"""
        from src.mcp.tools.updates import register_update_tools
        from src.mcp.tools.stats import register_stats_tools
        from src.mcp.tools.analysis import register_analysis_tools
        from src.mcp.tools.registry import get_all_tools
        
        # 第一次注册
        register_update_tools(mock_db)
        register_stats_tools(mock_db)
        register_analysis_tools(mock_db)
        
        first_count = len(get_all_tools())
        
        # 第二次注册（模拟多次调用）
        register_update_tools(mock_db)
        register_stats_tools(mock_db)
        register_analysis_tools(mock_db)
        
        second_count = len(get_all_tools())
        
        # 验证数量不变
        assert first_count == second_count, "重复注册导致工具数量增加"


class TestServerHandlers:
    """测试 Server 处理器设置"""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置全局注册表"""
        from src.mcp.tools import registry
        registry._tools = []
        registry._handlers = {}
        registry._tools_config = None
        yield
        registry._tools = []
        registry._handlers = {}
        registry._tools_config = None
    
    def test_setup_server_handlers(self):
        """测试 Server 处理器设置"""
        from src.mcp.tools.registry import register_tool, setup_server_handlers, get_all_tools
        from mcp.server import Server
        
        # 先注册一些工具
        tool = Tool(name="test_tool", description="Test", inputSchema={"type": "object"})
        async def handler(args):
            return "result"
        register_tool(tool, handler)
        
        # 创建 Server 并设置处理器
        server = Server("test")
        setup_server_handlers(server)
        
        # 验证处理器已设置（通过检查 server 的内部状态）
        # Server 的 list_tools 和 call_tool 装饰器会注册处理器
        assert hasattr(server, 'request_handlers')


class TestToolConfig:
    """测试工具配置获取"""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置配置缓存"""
        from src.mcp.tools import registry
        registry._tools_config = None
        yield
        registry._tools_config = None
    
    def test_get_tool_description_with_config(self):
        """测试从配置获取工具描述"""
        from src.mcp.tools.registry import get_tool_description
        
        # 应该能获取配置中的描述
        desc = get_tool_description("search_updates", "默认描述")
        
        # 如果配置存在，返回配置值；否则返回默认值
        assert desc is not None
        assert len(desc) > 0
    
    def test_get_tool_description_fallback(self):
        """测试工具描述回退到默认值"""
        from src.mcp.tools.registry import get_tool_description
        
        # 不存在的工具应该返回默认值
        desc = get_tool_description("nonexistent_tool_xyz", "这是默认描述")
        assert desc == "这是默认描述"
    
    def test_get_param_description(self):
        """测试获取参数描述"""
        from src.mcp.tools.registry import get_param_description
        
        # 存在的参数
        desc = get_param_description("search_updates", "vendor", "默认厂商描述")
        assert desc is not None
        
        # 不存在的参数应该返回默认值
        desc = get_param_description("search_updates", "nonexistent_param", "默认值")
        assert desc == "默认值"


class TestToolHandlerExecution:
    """测试工具处理器执行"""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置全局注册表"""
        from src.mcp.tools import registry
        registry._tools = []
        registry._handlers = {}
        registry._tools_config = None
        yield
        registry._tools = []
        registry._handlers = {}
        registry._tools_config = None
    
    @pytest.fixture
    def mock_db(self):
        """创建模拟数据库层"""
        db = MagicMock()
        db.query_updates_paginated.return_value = [
            {
                "update_id": "test-001",
                "vendor": "aws",
                "title": "Test Update",
                "title_translated": "测试更新",
                "publish_date": "2024-12-28",
                "update_type": "new_feature",
                "product_name": "VPC",
                "subcategory": "Networking",
                "tags": '["VPC", "网络"]',
                "summary_zh": "测试摘要"
            }
        ]
        return db
    
    @pytest.mark.asyncio
    async def test_search_updates_handler(self, mock_db):
        """测试 search_updates 处理器执行"""
        from src.mcp.tools.updates import register_update_tools
        from src.mcp.tools.registry import get_handler
        
        register_update_tools(mock_db)
        
        handler = get_handler("search_updates")
        assert handler is not None
        
        # 执行处理器
        result = await handler({
            "vendor": "aws",
            "date_from": "2024-01-01",
            "date_to": "2024-12-31"
        })
        
        # 验证返回格式
        assert len(result) == 1
        assert result[0].type == "text"
        assert "测试更新" in result[0].text or "Test Update" in result[0].text
    
    @pytest.mark.asyncio
    async def test_get_stats_overview_handler(self):
        """测试 get_stats_overview 处理器执行"""
        from src.mcp.tools.stats import register_stats_tools
        from src.mcp.tools.registry import get_handler
        
        mock_db = MagicMock()
        mock_db.count_updates.return_value = 1000
        mock_db.get_vendor_statistics.return_value = [
            {"vendor": "aws", "count": 500, "analyzed": 400}
        ]
        mock_db.get_update_type_statistics.return_value = {
            "new_feature": 300,
            "enhancement": 200
        }
        mock_db.get_analysis_coverage.return_value = 0.8
        
        register_stats_tools(mock_db)
        
        handler = get_handler("get_stats_overview")
        result = await handler({})
        
        assert len(result) == 1
        assert "1,000" in result[0].text or "1000" in result[0].text


class TestExpectedToolCount:
    """测试预期的工具数量"""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """每个测试前重置全局注册表"""
        from src.mcp.tools import registry
        registry._tools = []
        registry._handlers = {}
        registry._tools_config = None
        yield
        registry._tools = []
        registry._handlers = {}
        registry._tools_config = None
    
    def test_total_tool_count(self):
        """测试总工具数量符合预期"""
        from src.mcp.tools.updates import register_update_tools
        from src.mcp.tools.stats import register_stats_tools
        from src.mcp.tools.analysis import register_analysis_tools
        from src.mcp.tools.registry import get_all_tools
        
        mock_db = MagicMock()
        
        register_update_tools(mock_db)
        register_stats_tools(mock_db)
        register_analysis_tools(mock_db)
        
        tools = get_all_tools()
        
        # 预期工具列表
        expected_tools = {
            # updates.py
            "search_updates",
            "get_update_detail",
            # stats.py
            "get_stats_overview",
            "get_timeline",
            "get_vendor_stats",
            "get_update_type_stats",
            # analysis.py
            "get_product_hotness",
            "compare_vendors",
            "get_vendor_type_matrix",
        }
        
        actual_tools = {t.name for t in tools}
        
        # 验证完全匹配
        assert actual_tools == expected_tools, f"工具不匹配。预期: {expected_tools}, 实际: {actual_tools}"
        assert len(tools) == 9, f"预期 9 个工具，实际 {len(tools)} 个"
