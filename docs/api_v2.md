# 🏗️ CloudNetSpy API 模块架构方案

> **版本**: v2.0  
> **更新日期**: 2024-12-26  
> **状态**: 生产就绪方案

## 一、业务目标与设计原则

### 1.1 核心业务定位

**项目使命**: 云计算竞争情报系统 - 多云更新聚合 + AI智能分析 + 情报推送

**API层的职责**:
- 🎯 **主要用户**: 内部前端界面（数据看板、更新列表、详情页）
- 🔧 **次要用户**: 后台定时任务（爬虫触发、批量分析、报告生成）
- 🚀 **未来扩展**: 第三方集成（Webhook、开放API）

### 1.2 分阶段实施策略

| 阶段 | 业务目标 | 核心接口 | 实施时间 |
|------|---------|---------|----------|
| **阶段一：MVP** | 支持前端基础查询 + AI分析触发 | 更新列表/详情、统计看板、分析触发 | **当前开发** |
| **阶段二：高级分析** | 支持月度/年度报告生成 | 报告生成/查询、厂商对比 | Phase 6（后续） |
| **阶段三：订阅推送** | 支持用户订阅与消息推送 | 订阅管理、推送配置、通知历史 | Phase 4（后续） |

### 1.3 设计原则

- ✅ **业务驱动**: 每个接口都对应明确的业务场景
- ✅ **代码一致性**: 严格对齐数据库Schema与现有爬虫代码
- ✅ **前后端解耦**: API返回纯JSON，前端自由选型
- ✅ **可测试性**: Service层独立，易于Mock测试
- ✅ **可运维性**: 内置健康检查、错误日志、性能监控

---

## 二、目录结构

```plaintext
src/api/
├── __init__.py                 # 导出 app
├── app.py                      # FastAPI 应用入口
├── config.py                   # API 配置类
├── dependencies.py             # 依赖注入（数据库、认证等）
│
├── routes/                     # 路由模块
│   ├── __init__.py
│   ├── health.py              # 健康检查
│   ├── updates.py             # 更新数据接口（核心）
│   ├── analysis.py            # AI 分析接口
│   ├── stats.py               # 统计分析接口
│   └── vendors.py             # 厂商/产品元数据接口
│
├── schemas/                    # Pydantic 数据模型
│   ├── __init__.py
│   ├── update.py              # 更新相关模型
│   ├── analysis.py            # 分析相关模型
│   ├── common.py              # 公共模型（分页、响应包装）
│   └── stats.py               # 统计模型
│
├── services/                   # 业务逻辑层（重要！）
│   ├── __init__.py
│   ├── update_service.py      # 更新数据服务
│   ├── analysis_service.py    # 分析服务
│   └── stats_service.py       # 统计服务
│
├── middleware/                 # 中间件
│   ├── __init__.py
│   ├── cors.py                # 跨域配置
│   └── error_handler.py       # 全局错误处理
│
└── utils/                      # 工具函数
    ├── __init__.py
    ├── response.py            # 统一响应格式化
    └── validators.py          # 自定义验证器
```

---

## 三、核心API接口设计

### 3.1 健康检查

```plaintext
GET  /                          # API 根路径，返回版本信息
GET  /health                    # 健康检查（数据库连接状态）
GET  /docs                      # Swagger UI（FastAPI 自动生成）
```

### 3.2 更新数据接口（routes/updates.py）

```plaintext
GET  /api/v1/updates                    # 列表查询（核心）
     参数：
     - vendor: str                      # 厂商过滤（aws/azure/gcp等）
     - source_channel: str              # 来源类型（blog/whatsnew）
     - update_type: str                 # 更新类型（new_feature/enhancement等）
     - product_name: str                # 产品名称（模糊匹配）
     - product_category: str            # 产品分类（Networking/Compute等）
     - date_from/date_to: str           # 日期范围（YYYY-MM-DD）
     - has_analysis: bool               # 是否已AI分析
     - keyword: str                     # 关键词搜索（标题+内容）
     - tags: str                        # 标签过滤（逗号分隔）
     - sort_by: str                     # 排序字段（publish_date/crawl_time）
     - order: str                       # 排序方向（asc/desc）
     - page: int = 1                    # 页码
     - page_size: int = 20              # 每页数量（最大100）
     返回：分页列表（UpdateBrief对象）

GET  /api/v1/updates/{update_id}        # 单条详情
     返回：UpdateDetail对象（含AI分析字段）

GET  /api/v1/updates/{update_id}/raw    # 获取原始 Markdown 内容
     响应：text/markdown
```

### 3.3 AI 分析接口（routes/analysis.py）

```plaintext
POST /api/v1/analysis/single            # 单条分析（同步）
     Body: {"update_id": "xxx"}
     返回：{
         "success": true,
         "data": {
             "title_translated": "...",
             "content_summary": "...",
             "update_type": "new_feature",
             "tags": [...]
         },
         "execution_time_ms": 2500
     }

POST /api/v1/analysis/batch             # 批量分析（异步任务）
     Body: {
         "vendor": "aws",               # 可选
         "limit": 100,                  # 可选
         "force": false                 # 可选
     }
     返回：{"task_id": "xxx", "status": "queued", "total": 123}

GET  /api/v1/analysis/tasks/{task_id}   # 查询批量任务状态
     返回：{
         "task_id": "xxx",
         "status": "running",
         "progress": {"completed": 50, "total": 100},
         "errors": [],
         "started_at": "2024-01-01T10:00:00Z"
     }

GET  /api/v1/analysis/tasks             # 任务列表
     返回：最近的批量分析任务（分页）
```

### 3.4 统计分析接口（routes/stats.py）

```plaintext
GET  /api/v1/stats/overview             # 全局概览
     返回：{
         "total_updates": 1234,
         "vendors": {
             "aws": {"total": 500, "analyzed": 450},
             "azure": {"total": 400, "analyzed": 380}
         },
         "update_types": {
             "new_feature": 300,
             "enhancement": 250
         },
         "last_crawl_time": "2024-01-01T10:00:00Z",
         "analysis_coverage": 0.85
     }

GET  /api/v1/stats/timeline             # 时间线统计
     参数：
     - granularity: str                 # day/week/month
     - date_from/date_to: str
     - vendor: str                      # 可选
     返回：[
         {
             "date": "2024-01-01",
             "count": 10,
             "vendors": {"aws": 5, "azure": 5}
         }
     ]

GET  /api/v1/stats/vendors              # 按厂商统计
     参数：date_from, date_to
     返回：[
         {"vendor": "aws", "count": 500, "analyzed": 450}
     ]
```

### 3.5 元数据接口（routes/vendors.py）

```plaintext
GET  /api/v1/vendors                    # 厂商列表
     返回：[
         {
             "vendor": "aws",
             "name": "Amazon Web Services",
             "total_updates": 500,
             "source_channels": ["blog", "whatsnew"]
         }
     ]

GET  /api/v1/vendors/{vendor}/products  # 厂商的产品列表
     返回：[
         {"product_name": "VPC", "category": "Networking", "count": 100}
     ]

GET  /api/v1/update-types               # 更新类型枚举
     返回：[
         {"value": "new_feature", "label": "新功能发布", "description": "..."}
     ]
```

---

## 四、数据模型设计（Pydantic Schemas）

### 4.1 通用响应模型（schemas/common.py）

```python
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    success: bool = True
    data: Optional[T] = None
    message: str = ""
    error: Optional[str] = None

class PaginationMeta(BaseModel):
    """分页元数据"""
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)
    total: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)

class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    items: List[T]
    pagination: PaginationMeta
```

### 4.2 更新数据模型（schemas/update.py）

```python
from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator

class UpdateBrief(BaseModel):
    """更新列表项（简化版）- 用于列表展示"""
    update_id: str
    vendor: str
    source_channel: str                 # blog/whatsnew（数据库字段名）
    title: str
    title_translated: Optional[str] = None
    description: Optional[str] = None
    publish_date: date                  # 从数据库TEXT转换而来
    product_name: Optional[str] = None
    product_category: Optional[str] = None
    update_type: Optional[str] = None
    tags: List[str] = []                # 从数据库JSON字符串解析
    has_analysis: bool                  # 计算字段
    
    @field_validator('publish_date', mode='before')
    @classmethod
    def parse_publish_date(cls, v):
        """兼容数据库TEXT类型日期"""
        if isinstance(v, str):
            from datetime import datetime
            return datetime.strptime(v, '%Y-%m-%d').date()
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "update_id": "aws_blog_20240101_abc123",
                "vendor": "aws",
                "source_channel": "blog",
                "title": "Announcing VPC Lattice...",
                "title_translated": "AWS发布VPC Lattice服务网格",
                "description": "VPC Lattice is a new service...",
                "publish_date": "2024-01-01",
                "product_name": "VPC",
                "product_category": "Networking",
                "update_type": "new_feature",
                "tags": ["VPC", "服务网格", "IPv6"],
                "has_analysis": True
            }
        }

class UpdateDetail(UpdateBrief):
    """更新详情（完整版）- 用于详情页展示"""
    content: str
    content_summary: Optional[str] = None
    product_subcategory: Optional[str] = None
    source_url: str
    crawl_time: str                     # ISO 8601格式
    raw_filepath: Optional[str] = None
    analysis_filepath: Optional[str] = None

class UpdateQueryParams(BaseModel):
    """查询参数验证"""
    vendor: Optional[str] = None
    source_channel: Optional[str] = None
    update_type: Optional[str] = None
    product_name: Optional[str] = None
    product_category: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    has_analysis: Optional[bool] = None
    keyword: Optional[str] = None
    tags: Optional[str] = None
    sort_by: str = "publish_date"
    order: str = "desc"
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
```

### 4.3 分析相关模型（schemas/analysis.py）

```python
from pydantic import BaseModel
from typing import List, Optional

class AnalysisResult(BaseModel):
    """AI 分析结果"""
    title_translated: str
    content_summary: str
    update_type: str
    product_subcategory: str
    tags: List[str]

class AnalysisTaskStatus(BaseModel):
    """批量分析任务状态"""
    task_id: str
    status: str                     # queued/running/completed/failed
    progress: dict                  # {"completed": 50, "total": 100}
    started_at: str
    estimated_completion: Optional[str] = None
    completed_at: Optional[str] = None
    errors: List[str] = []
```

---

## 五、Service 层设计

### 5.1 UpdateService（services/update_service.py）

```python
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from src.storage.database.sqlite_layer import UpdateDataLayer
from src.api.schemas.common import PaginationMeta

class UpdateService:
    """更新数据业务服务"""
    
    def __init__(self, db: UpdateDataLayer):
        self.db = db
    
    def get_updates_paginated(
        self, 
        filters: dict, 
        page: int, 
        page_size: int,
        sort_by: str = "publish_date",
        order: str = "desc"
    ) -> Tuple[List[Dict], PaginationMeta]:
        """分页查询更新列表"""
        # 1. 查询总数
        total = self.db.count_updates_with_filters(**filters)
        
        # 2. 计算分页
        total_pages = (total + page_size - 1) // page_size
        offset = (page - 1) * page_size
        
        # 3. 查询当前页数据
        rows = self.db.query_updates_paginated(
            filters=filters, 
            limit=page_size, 
            offset=offset, 
            sort_by=sort_by, 
            order=order
        )
        
        # 4. 处理数据
        items = [self._process_update_row(row) for row in rows]
        
        # 5. 返回数据 + 分页元数据
        pagination = PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages
        )
        
        return items, pagination
    
    def get_update_detail(self, update_id: str) -> Optional[Dict]:
        """获取更新详情"""
        row = self.db.get_update_by_id(update_id)
        if not row:
            return None
        
        return self._process_update_row(row)
    
    def _process_update_row(self, row: dict) -> dict:
        """
        处理数据库行，转换为API格式
        
        关键处理：
        1. tags: JSON字符串 -> Python list
        2. has_analysis: 基于 title_translated 字段增强判定
        3. publish_date: TEXT -> date对象
        4. 过滤掉前端不需要的字段
        """
        result = dict(row)
        
        # 1. 解析tags JSON字符串
        tags_str = result.get('tags')
        if tags_str:
            try:
                result['tags'] = json.loads(tags_str)
                if not isinstance(result['tags'], list):
                    result['tags'] = []
            except (json.JSONDecodeError, TypeError):
                result['tags'] = []
        else:
            result['tags'] = []
        
        # 2. 判定是否已分析（增强验证，排除无效值）
        title_trans = result.get('title_translated', '').strip()
        result['has_analysis'] = bool(
            title_trans and 
            len(title_trans) >= 2 and  # 排除单字符无效值
            title_trans not in ['N/A', '暂无', 'None', 'null']  # 排除常见无效值
        )
        
        # 3. 转换日期类型
        if 'publish_date' in result and isinstance(result['publish_date'], str):
            try:
                result['publish_date'] = datetime.strptime(result['publish_date'], '%Y-%m-%d').date()
            except ValueError:
                pass  # 保留原始字符串
        
        # 4. 过滤掉前端不需要的内部字段
        internal_fields = ['source_identifier', 'file_hash', 'metadata_json', 'priority']
        for field in internal_fields:
            result.pop(field, None)
        
        return result
```

### 5.2 AnalysisService（services/analysis_service.py）

```python
import json
import uuid
from typing import Dict, Optional
from datetime import datetime
from src.storage.database.sqlite_layer import UpdateDataLayer
from src.analyzers.update_analyzer import UpdateAnalyzer
from src.utils.threading.thread_pool import AdaptiveThreadPool

class AnalysisService:
    """AI 分析业务服务"""
    
    def __init__(self, db: UpdateDataLayer, analyzer: UpdateAnalyzer, config: Dict):
        self.db = db
        self.analyzer = analyzer
        
        # 批量处理配置
        batch_config = config.get('ai_model', {}).get('batch_processing', {})
        self.max_workers = batch_config.get('max_workers', 10)
        api_rate_limit = config.get('ai_model', {}).get('api', {}).get('rate_limit', 60)
        
        # 初始化线程池
        self.thread_pool = AdaptiveThreadPool(
            api_rate_limit=api_rate_limit,
            initial_threads=2,
            max_threads=self.max_workers
        )
    
    def analyze_single(self, update_id: str) -> Dict:
        """同步分析单条"""
        # 1. 查询更新数据
        update = self.db.get_update_by_id(update_id)
        if not update:
            raise ValueError(f"更新记录不存在: {update_id}")
        
        # 2. 调用 UpdateAnalyzer.analyze()
        result = self.analyzer.analyze(update)
        
        if not result:
            raise RuntimeError(f"分析失败: {update_id}")
        
        # 3. 注意：UpdateAnalyzer已在内部完成tags序列化，无需重复处理
        
        # 4. 保存分析结果到文件（可选）
        file_path = self._save_analysis_to_file(update_id, update, result)
        if file_path:
            result['analysis_filepath'] = file_path
        
        # 5. 更新数据库
        success = self.db.update_analysis_fields(update_id, result)
        
        if not success:
            raise RuntimeError(f"更新分析结果失败: {update_id}")
        
        return result
    
    def analyze_batch_async(
        self, 
        vendor: Optional[str], 
        limit: int,
        force: bool
    ) -> str:
        """异步批量分析（返回 task_id）"""
        # 1. 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 2. 查询待分析记录
        updates = self.db.get_unanalyzed_updates(
            limit=limit,
            vendor=vendor,
            include_analyzed=force
        )
        
        if not updates:
            raise ValueError("没有待分析的记录")
        
        # 3. 创建任务记录
        self.db.create_analysis_task({
            'task_id': task_id,
            'task_name': 'batch_analysis',
            'task_status': 'queued',
            'vendor': vendor,
            'total_count': len(updates),
            'completed_count': 0,
            'started_at': datetime.now().isoformat()
        })
        
        # 4. 启动线程池异步处理
        self.thread_pool.start()
        
        for update in updates:
            self.thread_pool.add_task(
                self._analyze_single_item,
                update,
                task_id,
                task_meta={'identifier': update['update_id']}
            )
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Dict:
        """查询任务状态"""
        task = self.db.get_task_by_id(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")
        
        return {
            'task_id': task['task_id'],
            'status': task['task_status'],
            'progress': {
                'completed': task.get('completed_count', 0),
                'total': task.get('total_count', 0)
            },
            'started_at': task['started_at'],
            'completed_at': task.get('completed_at'),
            'errors': json.loads(task.get('error_message', '[]'))
        }
    
    def _analyze_single_item(self, update_data: Dict, task_id: str) -> bool:
        """分析单条记录（线程安全）"""
        update_id = update_data.get('update_id')
        
        try:
            # 执行分析
            result = self.analyzer.analyze(update_data)
            
            if result:
                # 保存分析结果到文件
                file_path = self._save_analysis_to_file(update_id, update_data, result)
                if file_path:
                    result['analysis_filepath'] = file_path
                
                # 更新数据库
                success = self.db.update_analysis_fields(update_id, result)
                
                # 更新任务进度
                self.db.increment_task_progress(task_id, success)
                
                return success
            else:
                self.db.increment_task_progress(task_id, False)
                return False
                
        except Exception as e:
            self.db.increment_task_progress(task_id, False, str(e))
            return False
    
    def _save_analysis_to_file(self, update_id: str, update_data: Dict, result: Dict) -> Optional[str]:
        """保存分析结果到文件"""
        # 参考 scripts/analyze_updates.py 实现
        # 返回文件路径或None
        pass
```

---

## 六、数据库层扩展方法

### 6.1 通用分页查询（添加到 UpdateDataLayer）

**⚠️ 重要提示**: 
- 现有`count_updates()`方法仅支持4个过滤条件，**必须扩展**
- 以下方法均为**新增方法**，需添加到`sqlite_layer.py`
- 必须严格验证输入参数，防止SQL注入

```python
def query_updates_paginated(
    self,
    filters: Dict[str, Any],
    limit: int,
    offset: int,
    sort_by: str = "publish_date",
    order: str = "desc"
) -> List[Dict[str, Any]]:
    """
    通用分页查询方法
    
    Args:
        filters: 过滤条件字典，支持：
            - vendor, source_channel, update_type
            - product_name（模糊匹配）, product_category
            - date_from, date_to
            - has_analysis
            - keyword（搜索title+content）
            - tags（逗号分隔，OR匹配）
        limit: 每页数量
        offset: 偏移量
        sort_by: 排序字段
        order: 排序方向
    """
    try:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            where_clauses = []
            params = []
            
            # vendor过滤
            if filters.get('vendor'):
                where_clauses.append("vendor = ?")
                params.append(filters['vendor'])
            
            # source_channel过滤
            if filters.get('source_channel'):
                where_clauses.append("source_channel = ?")
                params.append(filters['source_channel'])
            
            # update_type过滤
            if filters.get('update_type'):
                where_clauses.append("update_type = ?")
                params.append(filters['update_type'])
            
            # product_name模糊匹配
            if filters.get('product_name'):
                where_clauses.append("product_name LIKE ?")
                params.append(f"%{filters['product_name']}%")
            
            # product_category过滤
            if filters.get('product_category'):
                where_clauses.append("product_category = ?")
                params.append(filters['product_category'])
            
            # 日期范围
            if filters.get('date_from'):
                where_clauses.append("publish_date >= ?")
                params.append(filters['date_from'])
            
            if filters.get('date_to'):
                where_clauses.append("publish_date <= ?")
                params.append(filters['date_to'])
            
            # has_analysis过滤
            if filters.get('has_analysis') is not None:
                if filters['has_analysis']:
                    where_clauses.append("title_translated IS NOT NULL AND title_translated != ''")
                else:
                    where_clauses.append("(title_translated IS NULL OR title_translated = '')")
            
            # keyword关键词搜索
            if filters.get('keyword'):
                where_clauses.append("(title LIKE ? OR content LIKE ?)")
                keyword_param = f"%{filters['keyword']}%"
                params.extend([keyword_param, keyword_param])
            
            # tags标签过滤
            # ⚠️ 性能警告: LIKE查询无法使用索引，大数据量时考虑使用FTS5全文搜索
            if filters.get('tags'):
                tag_list = [t.strip() for t in filters['tags'].split(',')]
                tag_conditions = []
                for tag in tag_list:
                    tag_conditions.append("tags LIKE ?")
                    # 注意：匹配JSON数组中的字符串值
                    params.append(f'%"{tag}"%')
                where_clauses.append(f"({' OR '.join(tag_conditions)})")
            
            # 构建WHERE子句
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # 验证排序字段
            allowed_sort_fields = ['publish_date', 'crawl_time', 'update_id', 'vendor']
            if sort_by not in allowed_sort_fields:
                sort_by = 'publish_date'
            
            # 验证排序方向（防止SQL注入）
            order = order.upper()
            if order not in ['ASC', 'DESC']:
                order = 'DESC'
            
            # 构建SQL
            sql = f"""
                SELECT * FROM updates
                WHERE {where_clause}
                ORDER BY {sort_by} {order}
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
            
    except Exception as e:
        self.logger.error(f"分页查询失败: {e}")
        return []
```

### 6.2 扩展统计方法

```python
def count_updates_with_filters(self, **filters) -> int:
    """扩展版统计方法（支持所有过滤条件）"""
    # 复用 query_updates_paginated 的过滤逻辑，改为 COUNT(*)
    try:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 复用相同的过滤逻辑
            where_clauses = []
            params = []
            
            # ... (与 query_updates_paginated 相同的过滤逻辑)
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            sql = f"SELECT COUNT(*) as count FROM updates WHERE {where_clause}"
            
            cursor.execute(sql, params)
            result = cursor.fetchone()
            return result['count'] if result else 0
            
    except Exception as e:
        self.logger.error(f"统计查询失败: {e}")
        return 0

def get_vendor_statistics(
    self, 
    date_from: Optional[str] = None, 
    date_to: Optional[str] = None
) -> List[Dict[str, Any]]:
    """按厂商统计"""
    try:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            where_clauses = []
            params = []
            
            if date_from:
                where_clauses.append("publish_date >= ?")
                params.append(date_from)
            
            if date_to:
                where_clauses.append("publish_date <= ?")
                params.append(date_to)
            
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            sql = f"""
                SELECT 
                    vendor,
                    COUNT(*) as count,
                    SUM(CASE WHEN title_translated IS NOT NULL AND title_translated != '' 
                        THEN 1 ELSE 0 END) as analyzed
                FROM updates
                WHERE {where_clause}
                GROUP BY vendor
                ORDER BY count DESC
            """
            
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
            
    except Exception as e:
        self.logger.error(f"厂商统计查询失败: {e}")
        return []

def get_analysis_coverage(self) -> float:
    """计算分析覆盖率"""
    try:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as total FROM updates")
            total = cursor.fetchone()['total']
            
            if total == 0:
                return 0.0
            
            # ⚠️ 注意：增强has_analysis判定，排除无效值
            cursor.execute(
                "SELECT COUNT(*) as analyzed FROM updates "
                "WHERE title_translated IS NOT NULL "
                "AND title_translated != '' "
                "AND LENGTH(TRIM(title_translated)) >= 2"  # 排除单字符无效值
            )
            analyzed = cursor.fetchone()['analyzed']
            
            return round(analyzed / total, 4)
            
    except Exception as e:
        self.logger.error(f"分析覆盖率计算失败: {e}")
        return 0.0

# ==================== 批量分析任务管理方法（新增） ====================

def create_analysis_task(self, task_data: Dict[str, Any]) -> bool:
    """创建批量分析任务记录"""
    try:
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO analysis_tasks (
                        task_id, update_id, task_name, task_status,
                        task_result, started_at
                    ) VALUES (?, 'batch', ?, ?, ?, ?)
                ''', (
                    task_data['task_id'],
                    task_data.get('task_name', 'batch_analysis'),
                    task_data.get('task_status', 'queued'),
                    json.dumps({
                        'vendor': task_data.get('vendor'),
                        'total_count': task_data.get('total_count', 0),
                        'completed_count': 0
                    }),
                    task_data.get('started_at')
                ))
                
                conn.commit()
                return True
                
    except Exception as e:
        self.logger.error(f"创建任务失败: {e}")
        return False

def update_task_status(
    self, 
    task_id: str, 
    status: str, 
    progress: Optional[Dict] = None,
    error: Optional[str] = None
) -> bool:
    """更新任务状态"""
    try:
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                update_fields = ['task_status = ?']
                params = [status]
                
                if progress:
                    update_fields.append('task_result = ?')
                    params.append(json.dumps(progress))
                
                if error:
                    update_fields.append('error_message = ?')
                    params.append(error)
                
                if status == 'completed' or status == 'failed':
                    update_fields.append('completed_at = ?')
                    params.append(datetime.now().isoformat())
                
                params.append(task_id)
                
                sql = f"UPDATE analysis_tasks SET {', '.join(update_fields)} WHERE task_id = ?"
                cursor.execute(sql, params)
                conn.commit()
                
                return cursor.rowcount > 0
                
    except Exception as e:
        self.logger.error(f"更新任务状态失败: {e}")
        return False

def increment_task_progress(
    self, 
    task_id: str, 
    success: bool,
    error_msg: Optional[str] = None
) -> bool:
    """增加任务进度计数（线程安全）"""
    try:
        with self.lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取当前进度
                cursor.execute(
                    'SELECT task_result FROM analysis_tasks WHERE task_id = ?',
                    (task_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return False
                
                result = json.loads(row['task_result'])
                result['completed_count'] = result.get('completed_count', 0) + 1
                
                if success:
                    result['success_count'] = result.get('success_count', 0) + 1
                else:
                    result['fail_count'] = result.get('fail_count', 0) + 1
                    if error_msg:
                        errors = result.get('errors', [])
                        errors.append(error_msg)
                        result['errors'] = errors[-100:]  # 保留最近100条错误
                
                # 判断是否完成
                if result['completed_count'] >= result['total_count']:
                    status = 'completed'
                    completed_at = datetime.now().isoformat()
                    cursor.execute(
                        'UPDATE analysis_tasks SET task_status = ?, task_result = ?, completed_at = ? WHERE task_id = ?',
                        (status, json.dumps(result), completed_at, task_id)
                    )
                else:
                    cursor.execute(
                        'UPDATE analysis_tasks SET task_result = ? WHERE task_id = ?',
                        (json.dumps(result), task_id)
                    )
                
                conn.commit()
                return True
                
    except Exception as e:
        self.logger.error(f"更新任务进度失败: {e}")
        return False

def get_task_by_id(self, task_id: str) -> Optional[Dict[str, Any]]:
    """根据task_id获取任务记录"""
    try:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM analysis_tasks WHERE task_id = ?', (task_id,))
            
            row = cursor.fetchone()
            if row:
                task = dict(row)
                # 解析task_result JSON
                if task.get('task_result'):
                    task['task_result'] = json.loads(task['task_result'])
                return task
            return None
            
    except Exception as e:
        self.logger.error(f"获取任务记录失败: {e}")
        return None

def list_tasks_paginated(
    self, 
    limit: int = 20, 
    offset: int = 0
) -> List[Dict[str, Any]]:
    """分页查询任务列表（按创建时间倒序）"""
    try:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM analysis_tasks
                WHERE task_name = 'batch_analysis'
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            
            tasks = []
            for row in cursor.fetchall():
                task = dict(row)
                if task.get('task_result'):
                    task['task_result'] = json.loads(task['task_result'])
                tasks.append(task)
            
            return tasks
            
    except Exception as e:
        self.logger.error(f"查询任务列表失败: {e}")
        return []
```

---

## 七、中间件与安全

### 7.1 CORS 配置（middleware/cors.py）

```python
from fastapi.middleware.cors import CORSMiddleware

def setup_cors(app):
    """配置CORS中间件"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # 前端开发地址
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
```

### 7.2 全局错误处理（middleware/error_handler.py）

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse

async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": str(exc),
            "message": "服务器内部错误"
        }
    )
```

---

## 八、技术栈与依赖

### 8.1 新增依赖（requirements.txt）

```
# API 框架
fastapi==0.115.0
uvicorn[standard]==0.32.0
pydantic==2.9.0
pydantic-settings==2.6.0

# 限流（可选）
slowapi==0.1.9
```

### 8.2 配置管理（api/config.py）

```python
from pydantic_settings import BaseSettings
from typing import List

class APISettings(BaseSettings):
    """API 配置"""
    app_name: str = "CloudNetSpy API"
    version: str = "2.0.0"
    debug: bool = False
    
    # 数据库
    db_path: str = "data/sqlite/updates.db"
    
    # CORS
    cors_origins: List[str] = ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        env_prefix = "API_"

settings = APISettings()
```

---

## 九、部署与运行

### 9.1 启动脚本（添加到 run.sh）

```bash
# API 服务器启动
api_server() {
    echo "启动 API 服务器..."
    cd "${PROJECT_ROOT}"
    uvicorn src.api.app:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        --log-level info
}

# 生产模式
api_server_prod() {
    uvicorn src.api.app:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 4 \
        --log-level warning
}
```

---

## 十、实施检查清单

### 阶段0：数据库层扩展（必须先完成，P0优先级）

**❗ 关键依赖**: 以下方法是API开发的基础，必须优先完成

#### 0.1 核心查询方法（1天）
- [ ] 实现 `query_updates_paginated()`
  - 支持11个过滤条件（vendor/source_channel/update_type/product_name/product_category/date_from/date_to/has_analysis/keyword/tags/sort_by）
  - 严格验证sort_by和order参数（防SQL注入）
  - 注意tags过滤使用LIKE查询，大数据量时需优化
- [ ] 实现 `count_updates_with_filters()`
  - 复用query_updates_paginated的过滤逻辑
  - 将SELECT *改为SELECT COUNT(*)
- [ ] 实现 `get_vendor_statistics()`
  - 按厂商统计总数和已分析数
  - 支持date_from/date_to过滤
- [ ] 实现 `get_analysis_coverage()`
  - 增强has_analysis判定：LENGTH(TRIM(title_translated)) >= 2
  - 返回分析覆盖率（小数，4位精度）

#### 0.2 批量任务管理方法（1天）
- [ ] 实现 `create_analysis_task()`
  - 插入analysis_tasks表
  - task_result字段存储JSON：{vendor, total_count, completed_count, success_count, fail_count}
- [ ] 实现 `update_task_status()`
  - 更新task_status/task_result/completed_at
- [ ] 实现 `increment_task_progress()`
  - 线程安全的进度计数（使用self.lock）
  - 自动判断任务完成状态
- [ ] 实现 `get_task_by_id()`
  - 返回任务详情，自动解析task_result JSON
- [ ] 实现 `list_tasks_paginated()`
  - 分页查询batch_analysis任务
  - 按created_at倒序

#### 0.3 单元测试（0.5天）
- [ ] 测试query_updates_paginated过滤逻辑
  - 单条件过滤
  - 组合条件过滤
  - keyword搜索
  - tags过滤
  - 排序功能
- [ ] 测试批量任务CRUD
  - 并发场景下的increment_task_progress
  - 任务状态流转正确性

### 阶段1：基础框架（1天）
- [ ] 创建目录结构（参照第二节）
- [ ] 实现 app.py（FastAPI 初始化）
  - 配置CORS中间件
  - 注册全局异常处理
  - 挂载路由模块
- [ ] 实现 dependencies.py（数据库依赖注入）
  - 创建get_db()依赖函数
  - 支持测试时注入Mock DB
- [ ] 实现 schemas/common.py（通用响应模型）
  - ApiResponse[T]
  - PaginationMeta
  - PaginatedResponse[T]
- [ ] 实现 routes/health.py（健康检查）
  - GET / 返回版本信息
  - GET /health 检查数据库连接
- [ ] 测试：`curl http://localhost:8000/health`

### 阶段2：核心接口（3-4天）
- [ ] 实现 services/update_service.py
- [ ] 实现 schemas/update.py
- [ ] 实现 routes/updates.py（列表、详情、raw）
- [ ] 测试：分页功能
- [ ] 测试：过滤功能（单条件、组合条件、keyword、tags）
- [ ] 测试：排序功能

### 阶段3：分析接口（2天）
- [ ] 实现 services/analysis_service.py
  - ❗注意：UpdateAnalyzer已完成tags序列化，Service层无需重复
  - 实现analyze_batch_async()调用线程池
  - 任务状态持久化到analysis_tasks表
- [ ] 实现 schemas/analysis.py
  - AnalysisResult
  - AnalysisTaskStatus
  - BatchAnalysisRequest
- [ ] 实现 routes/analysis.py（单条、批量）
  - POST /api/v1/analysis/single
  - POST /api/v1/analysis/batch
  - GET /api/v1/analysis/tasks/{task_id}
  - GET /api/v1/analysis/tasks
- [ ] 验证：tags字段在Analyzer已序列化为JSON字符串
- [ ] 测试：分析流程
  - 单条同步分析
  - 批量异步分析任务创建
  - 任务状态查询

### 阶段4：统计接口（2天）
- [ ] 实现 services/stats_service.py
- [ ] 实现 routes/stats.py
- [ ] 测试：各类统计查询

### 阶段5：安全与优化（1-2天）
- [ ] 配置 CORS
- [ ] 全局错误处理
- [ ] 性能测试

### 阶段6：文档与部署（1天）
- [ ] 完善 OpenAPI 文档
- [ ] 编写部署脚本
- [ ] 编写前端对接文档

---

## 十一、字段对照表

| 数据库字段 | API返回类型 | 数据转换 | 说明 |
|-----------|------------|---------|------|
| `update_id` | str | 无 | 主键 |
| `vendor` | str | 无 | 厂商标识 |
| `source_channel` | str | 无 | blog/whatsnew |
| `update_type` | Optional[str] | 无 | AI分类结果 |
| `source_url` | str | 无 | 原始URL |
| `title` | str | 无 | 英文标题 |
| `title_translated` | Optional[str] | 无 | 中文标题 |
| `description` | Optional[str] | 无 | 简要描述 |
| `content` | str | 无 | Markdown内容 |
| `content_summary` | Optional[str] | 无 | AI摘要 |
| `publish_date` | TEXT | → date | Service层转换 |
| `crawl_time` | TEXT | → str | ISO 8601格式 |
| `product_name` | Optional[str] | 无 | 产品名称 |
| `product_category` | Optional[str] | 无 | 产品大类 |
| `product_subcategory` | Optional[str] | 无 | 产品子类 |
| `tags` | TEXT(JSON) | → List[str] | json.loads/dumps |
| `raw_filepath` | Optional[str] | 无 | 原始文件路径 |
| `analysis_filepath` | Optional[str] | 无 | 分析文件路径 |
| `has_analysis` | 计算字段 | title_translated判定 | 不存储 |

**内部字段（不返回给前端）**:
- `source_identifier`, `file_hash`, `metadata_json`, `priority`
- `created_at`, `updated_at`

---

## 十二、关键实现注意事项

### 12.1 数据一致性保障

#### has_analysis判定逻辑统一
```python
# ✅ 正确的判定逻辑（三个位置保持一致）：
# 1. UpdateDataLayer.get_unanalyzed_updates()
# 2. UpdateDataLayer.get_analysis_coverage()
# 3. UpdateService._process_update_row()

title_trans = result.get('title_translated', '').strip()
has_analysis = bool(
    title_trans and 
    len(title_trans) >= 2 and
    title_trans not in ['N/A', '暂无', 'None', 'null']
)
```

#### tags字段序列化规范
```python
# ✅ 序列化只在一个地方完成：
# UpdateAnalyzer._validate_and_fix_fields() 已完成序列化
validated['tags'] = json.dumps(tags, ensure_ascii=False)

# ❌ Service层不要重复序列化
# AnalysisService.analyze_single() 中删除以下代码：
# if 'tags' in result and isinstance(result['tags'], list):
#     result['tags'] = json.dumps(result['tags'], ensure_ascii=False)
```

### 12.2 安全性要求

#### SQL注入防护
```python
# ✅ 必须使用白名单验证
allowed_sort_fields = ['publish_date', 'crawl_time', 'update_id', 'vendor']
if sort_by not in allowed_sort_fields:
    sort_by = 'publish_date'

order = order.upper()
if order not in ['ASC', 'DESC']:
    order = 'DESC'

# ❌ 禁止直接拼接用户输入
# sql = f"SELECT * FROM updates ORDER BY {user_input}"  # 危险！
```

#### 参数化查询
```python
# ✅ 所有过滤条件必须使用参数化查询
where_clauses.append("vendor = ?")
params.append(filters['vendor'])

# ❌ 禁止字符串拼接
# sql = f"WHERE vendor = '{filters['vendor']}'"  # 危险！
```

### 12.3 性能优化建议

#### tags过滤性能警告
```python
# ⚠️ 当前实现：LIKE查询无法使用索引
tag_conditions.append("tags LIKE ?")
params.append(f'%"{tag}"%')

# 💡 优化方案（后续阶段）：
# 1. SQLite 3.38+ 使用 JSON_EXTRACT()
# 2. 使用FTS5全文搜索
# 3. 建立tags反向索引表
```

#### 复合索引建议
```sql
-- 优化has_analysis过滤查询
CREATE INDEX IF NOT EXISTS idx_updates_has_analysis 
ON updates(title_translated, publish_date)
WHERE title_translated IS NOT NULL AND title_translated != '';

-- 优化厂商+日期查询（已存在）
-- CREATE INDEX idx_updates_vendor_date ON updates(vendor, publish_date);
```

### 12.4 测试要求

#### 数据库测试隔离
```python
# ✅ 使用内存数据库测试
def test_query_updates():
    db = UpdateDataLayer(db_path=":memory:")
    # 测试逻辑

# ✅ 或使用临时文件
import tempfile
with tempfile.NamedTemporaryFile(suffix='.db') as f:
    db = UpdateDataLayer(db_path=f.name)
```

#### API集成测试
```python
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    return TestClient(app)

def test_list_updates(client):
    response = client.get("/api/v1/updates?vendor=aws&page=1")
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert 'pagination' in data['data']
```

### 12.5 错误处理规范

#### Service层异常处理
```python
# ✅ 明确的异常类型
if not update:
    raise ValueError(f"更新记录不存在: {update_id}")

if not success:
    raise RuntimeError(f"更新分析结果失败: {update_id}")

# ✅ 在Route层捕获并转换为HTTP响应
@router.post("/analysis/single")
async def analyze_single(request: AnalysisRequest):
    try:
        result = analysis_service.analyze_single(request.update_id)
        return ApiResponse(success=True, data=result)
    except ValueError as e:
        return ApiResponse(success=False, error=str(e), message="记录不存在")
    except RuntimeError as e:
        return ApiResponse(success=False, error=str(e), message="分析失败")
```

### 12.6 已知限制与未来优化

#### 批量任务限制
- 当前设计：任务状态存储在数据库，服务重启后可恢复
- 限制：无法实时推送进度（需WebSocket或SSE）
- 优化方向：引入Redis存储实时进度+WebSocket推送

#### 分页性能
- 当前设计：使用LIMIT/OFFSET分页
- 限制：深分页性能下降（OFFSET 10000性能差）
- 优化方向：基于游标的分页（WHERE id > last_id）

#### tags搜索
- 当前设计：LIKE匹配JSON字符串
- 限制：无法使用索引，性能较差
- 优化方向：FTS5全文搜索或tags反向索引表

---

## 十三、开发检查清单速查

### ✅ 开发前检查
- [ ] 已阅读第十二节「关键实现注意事项」
- [ ] 已理解has_analysis判定逻辑
- [ ] 已理解tags序列化规范（仅在Analyzer完成）
- [ ] 已准备测试数据库（:memory:或临时文件）

### ✅ 代码审查检查
- [ ] 无SQL注入风险（参数化查询+白名单验证）
- [ ] has_analysis判定逻辑一致（三个位置）
- [ ] tags未重复序列化
- [ ] 异常处理明确（ValueError/RuntimeError）
- [ ] 测试覆盖率>80%

### ✅ 部署前检查
- [ ] 数据库索引已创建
- [ ] API文档已生成（/docs）
- [ ] 健康检查正常（/health）
- [ ] CORS配置正确
- [ ] 日志级别设置为WARNING（生产环境）
