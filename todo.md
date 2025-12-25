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

## 六、核心模块设计参考

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

## 七、AI模型配置

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

## 八、备注

- 建议从 Phase 1 开始，AI分析是后续所有功能的基础
- 每个 Phase 完成后进行回归测试
- 机密信息（API Key等）统一使用 `.env` 文件管理
- 生产环境建议使用 PostgreSQL 替代 SQLite
