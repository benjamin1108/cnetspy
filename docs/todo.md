# 云计算竞争情报系统 - 扩展架构设计方案

## 一、扩展目标

- [ ] AI分析功能（单条翻译摘要）
- [ ] 组合式分析（月度、年度、厂家分析）
- [ ] API服务
- [ ] 前端界面
- [ ] 定时推送消息

---

## 二、目标架构

```
cnetCompSpy/
├── config/                    # 配置文件
├── src/
│   ├── core/                  # 核心业务层 (新增)
│   │   ├── crawlers/          # 爬虫模块 (原 crawlers/)
│   │   ├── analyzers/         # AI分析模块 (新增)
│   │   │   ├── base_analyzer.py
│   │   │   ├── translator.py         # 单条翻译
│   │   │   ├── summarizer.py         # 摘要生成
│   │   │   ├── classifier.py         # 更新类型分类
│   │   │   └── insights/             # 组合分析
│   │   │       ├── monthly_report.py
│   │   │       ├── yearly_report.py
│   │   │       └── vendor_analysis.py
│   │   └── notifiers/         # 消息推送模块 (新增)
│   │       ├── base_notifier.py
│   │       ├── email_notifier.py
│   │       ├── dingtalk_notifier.py
│   │       ├── wechat_notifier.py
│   │       └── slack_notifier.py
│   │
│   ├── api/                   # API服务层 (新增)
│   │   ├── __init__.py
│   │   ├── app.py             # FastAPI 应用入口
│   │   ├── routes/
│   │   │   ├── updates.py     # 更新数据接口
│   │   │   ├── analysis.py    # 分析接口
│   │   │   ├── reports.py     # 报告接口
│   │   │   └── webhooks.py    # Webhook回调
│   │   ├── schemas/           # API数据模型
│   │   └── middleware/        # 中间件（认证、限流）
│   │
│   ├── scheduler/             # 定时任务模块 (新增)
│   │   ├── __init__.py
│   │   ├── jobs.py            # 任务定义
│   │   └── scheduler.py       # APScheduler调度器
│   │
│   ├── models/                # 数据模型层 (扩展)
│   │   ├── update.py          # 原始更新
│   │   ├── analysis.py        # 分析结果 (新增)
│   │   ├── report.py          # 报告模型 (新增)
│   │   └── subscription.py    # 订阅模型 (新增)
│   │
│   ├── storage/               # 存储层 (扩展)
│   │   ├── database/
│   │   │   ├── sqlite_layer.py
│   │   │   ├── postgres_layer.py    # 生产数据库 (新增)
│   │   │   └── redis_cache.py       # 缓存层 (新增)
│   │   └── file_storage.py
│   │
│   └── utils/                 # 工具层
│
├── web/                       # 前端 (新增，独立目录)
│   ├── package.json
│   └── src/
│       ├── pages/
│       ├── components/
│       └── api/
│
├── scripts/                   # 运维脚本
├── tests/                     # 测试
└── docker-compose.yml         # 容器编排
```

---

## 三、数据流设计

```
┌─────────────────────────────────────────────────────────────────┐
│                         数据流架构                               │
└─────────────────────────────────────────────────────────────────┘

1. 数据采集流
   Scheduler ──> Crawlers ──> SQLite/PostgreSQL ──> Event Queue

2. 分析流水线 (事件驱动)
   New Update Event
       │
       ├──> Translator (翻译)
       ├──> Summarizer (摘要)
       ├──> Classifier (分类)
       │
       └──> 判断是否即时推送 ──> Notifiers

3. 定期报告流
   Scheduler (cron)
       │
       ├──> MonthlyReportGenerator
       ├──> YearlyReportGenerator
       │
       └──> Report Storage ──> API / Notifiers

4. API请求流
   Frontend / Client
       │
       └──> FastAPI ──> Service Layer ──> Storage / Cache
```

---

## 四、技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| **API框架** | FastAPI | 高性能异步框架，自带OpenAPI文档 |
| **定时任务** | APScheduler / Celery | 简单用APScheduler，分布式用Celery |
| **消息队列** | Redis / RabbitMQ | 事件驱动、任务队列 |
| **AI分析** | OpenAI API / Claude / 本地Ollama | 支持多LLM后端 |
| **缓存** | Redis | 热点数据缓存，加速API响应 |
| **数据库** | SQLite (dev) / PostgreSQL (prod) | 生产环境用PG |
| **前端** | React + Vite / Next.js | 现代前端框架 |
| **部署** | Docker + Docker Compose | 容器化部署 |

---

## 五、实施路线图

### Phase 1: AI分析基础能力 (1-2周)

- [ ] 重构目录结构，创建 `src/core/` 目录
- [ ] 实现 `base_analyzer.py` 分析器基类
- [ ] 实现 `translator.py` 单条翻译功能
- [ ] 实现 `summarizer.py` 摘要生成功能
- [ ] 实现 `classifier.py` 更新类型自动分类
- [ ] 添加 LLM 配置（支持 OpenAI/Claude/Ollama）
- [ ] 数据库扩展：添加 `analysis` 表存储分析结果

### Phase 2: API服务 (1-2周)

- [ ] 搭建 FastAPI 应用框架
- [ ] 实现更新数据 CRUD 接口 (`/api/v1/updates`)
- [ ] 实现分析接口 (`/api/v1/analysis`)
- [ ] 实现报告接口 (`/api/v1/reports`)
- [ ] 添加 API 认证中间件
- [ ] 添加请求限流
- [ ] 编写 API 文档

### Phase 3: 定时任务 (1周)

- [ ] 集成 APScheduler
- [ ] 定时爬取任务（每日凌晨）
- [ ] 定时分析任务（新数据自动分析）
- [ ] 定时报告生成（每月1号）
- [ ] 任务监控和日志

### Phase 4: 消息推送 (1周)

- [ ] 实现 `base_notifier.py` 推送基类
- [ ] 实现 `email_notifier.py` 邮件推送
- [ ] 实现 `dingtalk_notifier.py` 钉钉推送
- [ ] 实现 `wechat_notifier.py` 企业微信推送
- [ ] 实现订阅管理（用户订阅配置）
- [ ] 推送模板设计

### Phase 5: 前端界面 (2-3周)

- [ ] 初始化 React + Vite 项目
- [ ] 实现数据看板页面
- [ ] 实现更新列表页面（支持筛选、搜索）
- [ ] 实现更新详情页面（含AI分析结果）
- [ ] 实现报告查看页面
- [ ] 实现订阅设置页面
- [ ] 响应式设计

### Phase 6: 高级分析 (持续迭代)

- [ ] 月度分析报告生成
- [ ] 年度分析报告生成
- [ ] 厂商对比分析
- [ ] 趋势分析和预测
- [ ] 关键词热度分析
- [ ] 智能推荐（基于用户订阅偏好）

---

## 六、AI字段处理规范

### 1. 字段概览

| 字段 | 来源 | 输入/输出 | 说明 |
|------|------|----------|------|
| `title_translated` | AI生成 | `content` + `title` → 中文标题 | 从内容提取合适标题再翻译 |
| `content_summary` | AI生成 | `content` → 结构化摘要 | 固定格式，良好阅读体验 |
| `update_type` | AI分类 | `content` + `source_channel` → 枚举值 | 从 UpdateType 枚举中选择 |
| `product_category` | **爬虫获取** | 厂商原始数据 | 如没有则由AI补充 |
| `product_subcategory` | AI判定 | `content` + `product_name` → 子类名 | 自由文本，AI动态判定 |
| `tags` | AI提取 | `content` + `title` → 关键词 | JSON数组格式 |

### 2. title_translated 要求

**处理逻辑：**
- 不直接翻译原始 `title`，而是结合 `content` 语境理解内容
- 从 `content` 中提取最能概括更新内容的英文标题
- 将提取的英文标题翻译为中文

**输出要求：**
- 简洁明了，不超过50个字
- 体现更新的核心内容和价值
- 避免模糊表达，突出关键信息

### 3. content_summary 格式规范

**固定输出格式：**

```markdown
## 更新概要
{1-2句话概括更新核心内容}

## 主要内容
- {要点1}
- {要点2}
- {要点3}

## 影响范围
{适用场景或影响的用户/服务}

## 相关产品
{涉及的云产品名称}
```

**输出要求：**
- 总字数控制在 150-300 字
- 使用 Markdown 格式
- 要点不超过5条，突出核心价值
- 语言简洁专业，避免冗余

### 4. update_type 分类规则

**输入维度：**
- `content`: 更新的具体内容
- `source_channel`: 数据源类型 (blog / whatsnew)

**枚举选项 (UpdateType)：**
| 枚举值 | 说明 | 判断依据 |
|---------|------|----------|
| `new_product` | 新产品发布 | 全新产品/服务上线 |
| `new_feature` | 新功能发布 | 现有产品新增功能 |
| `enhancement` | 功能增强 | 现有功能优化升级 |
| `deprecation` | 功能弃用 | 功能下线/弃用通知 |
| `pricing` | 定价调整 | 价格变化相关 |
| `region` | 区域扩展 | 新区域/可用区上线 |
| `security` | 安全更新 | 安全补丁/增强 |
| `fix` | 问题修复 | Bug修复 |
| `performance` | 性能优化 | 性能提升相关 |
| `compliance` | 合规认证 | 合规/认证相关 |
| `integration` | 集成能力 | 第三方集成/API更新 |
| `other` | 其他 | 无法归类时选择 |

### 5. product_subcategory 子类判定规则

**字段说明：**
- `product_category`: 优先从爬虫获取厂商的原始分类，如没有则由AI补充
- `product_subcategory`: 由AI根据内容动态判定

**AI判定规则：**
- 结合 `content` 和 `product_name` 进行语义分析
- 输出简洁的子类名称（英文小写+下划线）
- 不使用枚举，允许自由文本

**示例：**
| product_category | product_subcategory | 内容特征 |
|-----------------|---------------------|----------|
| VPC | `peering` | VPC对等连接相关 |
| VPC | `private_link` | 私网端点连接相关 |
| VPC | `transit_gateway` | 中转网关相关 |
| VPC | `subnet` | 子网管理相关 |
| VPC | `nat` | NAT网关相关 |
| Load Balancing | `alb` | 应用型负载均衡 |
| Load Balancing | `nlb` | 网络型负载均衡 |
| CDN | `edge_cache` | 边缘缓存相关 |
| CDN | `origin_shield` | 回源保护相关 |

### 6. tags 提取规则

**输出格式：**
```json
["VPC", "网络安全", "IPv6", "多可用区"]
```

**提取规则：**
- 提取 3-8 个关键词
- 优先提取：产品名、技术特性、业务场景
- 支持中英文混合
- 避免过于宽泛的词汇（如"更新"、"功能"）

---

## 七、核心模块设计参考

### 1. AI分析器基类

```python
# src/core/analyzers/base_analyzer.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseAnalyzer(ABC):
    """AI分析器基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm_client = self._init_llm_client()
    
    @abstractmethod
    def _init_llm_client(self):
        """初始化LLM客户端（支持多种：OpenAI、Claude、本地模型）"""
        pass
    
    @abstractmethod
    def analyze(self, data: Any) -> Dict[str, Any]:
        """执行分析"""
        pass
```

### 2. 单条翻译摘要

```python
# src/core/analyzers/translator.py
class UpdateTranslator(BaseAnalyzer):
    """单条更新翻译+摘要"""
    
    def analyze(self, update: Dict) -> Dict:
        return {
            'title_zh': self._translate(update['title']),
            'summary_zh': self._summarize(update['content']),
            'key_points': self._extract_key_points(update['content']),
            'impact_level': self._assess_impact(update),
        }
```

### 3. 月度报告生成器

```python
# src/core/analyzers/insights/monthly_report.py
class MonthlyReportGenerator(BaseAnalyzer):
    """月度分析报告"""
    
    def analyze(self, updates: List[Dict], month: str, vendor: str = None) -> Dict:
        return {
            'summary': self._generate_summary(updates),
            'trends': self._analyze_trends(updates),
            'top_updates': self._rank_updates(updates),
            'vendor_comparison': self._compare_vendors(updates),
            'recommendations': self._generate_recommendations(updates),
        }
```

### 4. API路由示例

```python
# src/api/routes/updates.py
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

@router.get("/")
async def list_updates(
    vendor: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    """获取更新列表"""
    pass

@router.get("/{update_id}/analysis")
async def get_update_analysis(update_id: str):
    """获取单条更新的AI分析结果"""
    pass
```

### 5. 定时任务配置

```python
# src/scheduler/jobs.py
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

# 每天凌晨2点爬取
@scheduler.scheduled_job('cron', hour=2)
def daily_crawl_job():
    """每日爬取任务"""
    pass

# 每天8点推送昨日摘要
@scheduler.scheduled_job('cron', hour=8)
def daily_digest_job():
    """每日摘要推送"""
    pass

# 每月1号生成月报
@scheduler.scheduled_job('cron', day=1, hour=9)
def monthly_report_job():
    """月度报告生成"""
    pass
```

### 6. 消息推送基类

```python
# src/core/notifiers/base_notifier.py
from abc import ABC, abstractmethod
from typing import List, Dict

class BaseNotifier(ABC):
    """消息推送基类"""
    
    @abstractmethod
    def send(self, title: str, content: str, recipients: List[str]) -> bool:
        pass
    
    def send_update_alert(self, update: Dict, analysis: Dict):
        """发送更新提醒"""
        pass
    
    def send_daily_digest(self, updates: List[Dict]):
        """发送每日摘要"""
        pass
    
    def send_monthly_report(self, report: Dict):
        """发送月度报告"""
        pass
```

---

## 八、AI模型配置

```yaml
# config/ai_model.yaml

default:
  provider: gemini
  
  # 模型名称
  model_name: gemini-3-pro-preview
  
  # API Key 环境变量名称（实际的 API Key 从环境变量读取）
  api_key_env: GEMINI_API_KEY
  
  # 生成参数
  generation:
    # 温度：控制输出的随机性 (0.0-1.0)
    # 较低的值使输出更确定，较高的值使输出更有创造性
    temperature: 0.5
    
    # Top-p：核采样参数 (0.0-1.0)
    # 控制输出的多样性
    top_p: 0.9
    
    # Top-k：候选词数量
    # 限制每步采样的候选词数量
    top_k: 40
    
    # 最大输出令牌数
    max_output_tokens: 65535
  
  # 速率限制
  rate_limit:
    # API 调用间隔（秒）
    interval: 0.5
    
    # 最大重试次数
    max_retries: 3
    
    # 重试退避基数（指数退避）
    retry_backoff_base: 2.0
```

---

## 九、技术债务与重构建议

- [ ] **优化数据流转层级，减少新增字段时的跨文件耦合**
    - **背景**：目前新增一个字段（如 `update_type`）需要修改 5+ 个文件，存在严重的“霰弹式修改”技术债。
    - **建议方向**：
        1. **动态透传模式**：修改 `SyncDecorator` 和 `DataLayer` 等中间层，使用属性透传（`**kwargs` 或 `dict` 合并）而非硬编码白名单。
        2. **统一数据模型 (DTO)**：引入 Pydantic 建立统一的 `UpdateEntry` 模型，实现全链路类型安全。
        3. **动态 SQL 映射**：优化 Repository 层，自动根据 DTO 字段生成 SQL 插入语句，摆脱对手写 SQL 列表的依赖。

- [ ] **配置文件路径统一化**：减少各模块中硬编码的目录路径。
