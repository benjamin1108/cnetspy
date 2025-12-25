# 统一业务数据层设计方案

## 一、设计背景与目标

### 1.1 当前系统存在的问题

当前系统在数据组织和管理上存在以下核心问题:

1. **异源信息结构不统一**: 不同厂商的数据颗粒度差异大,有的以单个更新为单位存储,有的以月度汇总形式存储(如GCP、腾讯云、华为云的whatsnew),导致数据处理逻辑复杂且难以统一

2. **元数据缺失或不完整**: 现有爬虫元数据(crawler_metadata.json)中缺少关键业务字段,如产品归属、产品大类、更新类型、完整的发布日期等,不便于后续的数据聚合、清洗、分类和分析

3. **数据访问效率低**: 基于文件系统和JSON的数据组织方式,在大规模数据查询、统计和聚合时性能不佳

4. **前端展示受限**: 由于缺乏统一的数据层,前端难以实现跨厂商、跨类型的高级查询和分析功能

5. **缺少业务维度分类**: 无法区分更新类型(新功能、安全修复、博客文章等),不利于竞争情报分析

### 1.2 设计目标

构建一个厂商无关的统一业务数据层,实现以下目标:

1. **统一数据颗粒度**: 以Update(更新)为最小颗粒度,统一所有厂商数据的组织方式,包括产品发布、新功能、博客文章、安全修复等各类更新信息

2. **完善元数据体系**: 建立完整的元数据模型,包含厂商、更新类型、产品、产品大类、发布日期、优先级等多维度信息

3. **提升数据访问性能**: 采用SQLite数据库,支持高效的索引查询和复杂的聚合统计

4. **保持系统平滑演进**: 新数据层与现有流程并行运行,前端继续使用旧数据,为未来全新前端预留扩展空间

5. **支持历史数据迁移**: 一次性迁移所有历史数据到新数据层,确保数据完整性

6. **支持业务分析**: 通过更新类型和优先级字段,支持竞争情报的多维度分析

## 二、整体架构设计

### 2.1 架构分层

系统将形成如下分层架构:

```
┌─────────────────────────────────────────────────────────┐
│                  前端展示层(未来)                          │
│         (新前端,基于统一业务数据层构建)                     │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│              统一业务数据层(Update Data Layer)             │
│      (SQLite数据库 + UpdateManager + 查询/聚合API)          │
└─────────────────────────────────────────────────────────┘
                            ↑
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  爬虫数据源   │  │  分析数据源   │  │  元数据源     │
│ (data/raw)   │  │(data/analysis)│  │ (metadata)   │
└──────────────┘  └──────────────┘  └──────────────┘
        ↑                  ↑                  ↑
┌─────────────────────────────────────────────────────────┐
│                     现有爬虫与分析流程                      │
│     (BaseCrawler + AI Analyzer + MetadataManager)       │
└─────────────────────────────────────────────────────────┘
```

### 2.2 新旧系统并行运行策略

实施阶段将采用新旧并行策略:

#### 阶段一(当前阶段)

- 现有爬虫流程继续运行,数据写入data/raw和现有元数据文件
- 新增UpdateDataLayer组件,同步将数据写入SQLite数据库
- 现有前端(Web Server)继续使用data/raw和旧元数据
- 历史数据一次性迁移到新数据层

#### 阶段二(过渡阶段)

- 新数据层功能完善,提供完整的查询和统计API
- 开发新前端,基于统一业务数据层构建
- 新旧前端共存,验证新数据层功能正确性

#### 阶段三(目标状态)

- 新前端全面上线
- 旧前端下线或作为备用
- 评估是否保留文件系统数据存储

## 三、数据模型设计

### 3.1 核心概念

#### 3.1.1 Update(更新)的定义

Update是系统的核心数据单元,代表云厂商发布的任何一条更新信息,包括但不限于:

- **产品相关**: 新产品发布、新功能上线、功能增强、产品废弃等
- **基础设施**: 新地域开放、新可用区、数据中心扩展等
- **安全与合规**: 安全漏洞修复、安全公告、合规认证更新等
- **稳定性**: Bug修复、性能优化、故障事后报告等
- **商业**: 价格调整、客户案例、合作伙伴公告等
- **内容**: 技术博客、案例分享、观点文章、网络研讨会等

#### 3.1.2 设计原则

1. **统一Schema**: 所有类型的更新存储在同一张updates表中,通过update_type字段区分

2. **真实URL优先**: source_url尽可能保持真实可访问的URL

3. **source_identifier辅助唯一性**: 对于无独立URL的更新(如Azure Updates、月度汇总),通过source_identifier补充唯一性标识

4. **业务维度优先**: 按update_type(业务类型)分类,而非按source_channel(技术来源)分类

### 3.2 核心实体模型

#### 3.2.1 Update实体

Update是系统的核心数据单元,代表一条云厂商更新信息。

| 字段名 | 类型 | 说明 | 必填 | 索引 | 适用范围 |
|--------|------|------|------|------|----------|
| update_id | TEXT | 全局唯一标识,UUID格式 | 是 | 主键 | 所有更新 |
| vendor | TEXT | 厂商标识(aws/azure/gcp/huawei/tencentcloud/volcengine) | 是 | 是 | 所有更新 |
| update_type | TEXT | 更新类型(new_feature/security_fix/blog_technical等) | 是 | 是 | 所有更新 |
| source_url | TEXT | 来源URL(真实可访问的URL) | 是 | 组合唯一索引 | 所有更新 |
| source_identifier | TEXT | 来源标识(用于同URL下区分多条记录) | 是 | 组合唯一索引 | 默认为空,Azure Updates和月度汇总必填 |
| title | TEXT | 原始标题 | 是 | - | 所有更新 |
| title_translated | TEXT | AI翻译后的标题 | 否 | - | 所有更新 |
| content_summary | TEXT | 内容摘要 | 否 | - | 所有更新 |
| publish_date | TEXT | 发布日期,YYYY-MM-DD格式 | 是 | 是 | 所有更新 |
| crawl_time | TEXT | 爬取时间,ISO 8601格式 | 是 | - | 所有更新 |
| product_name | TEXT | 产品名称 | 否 | 是 | 产品相关更新必填,博客类可为空 |
| product_category | TEXT | 产品大类(networking/compute/storage等) | 否 | 是 | 通过映射表填充,可为空 |
| priority | TEXT | 优先级(critical/high/medium/low) | 否 | 是 | 根据update_type自动设置 |
| tags | TEXT | 标签列表,JSON数组格式 | 否 | - | 所有更新,来源不同 |
| raw_filepath | TEXT | 原始文件路径(相对路径) | 是 | - | 所有更新 |
| analysis_filepath | TEXT | 分析文件路径(相对路径) | 否 | - | 所有更新 |
| file_hash | TEXT | 内容哈希值,用于检测内容变更 | 否 | - | 所有更新 |
| metadata_json | TEXT | 扩展元数据,JSON格式 | 否 | - | 所有更新,存储类型特有信息 |
| created_at | DATETIME | 记录创建时间 | 是 | - | 所有更新 |
| updated_at | DATETIME | 记录更新时间 | 是 | - | 所有更新 |

##### 字段说明

**update_id**
- 使用UUID v4生成,格式如"f47ac10b-58cc-4372-a567-0e02b2c3d479"
- 确保全局唯一性

**vendor**
- 厂商标识,支持: aws, azure, gcp, huawei, tencentcloud, volcengine

**update_type**
- 更新类型,详见3.2.2节的分类体系

**source_url**
- 有独立URL的(如AWS Whatsnew, 所有Blog): 填写真实URL
- Azure Updates: 填写固定页面'https://azure.microsoft.com/en-us/updates/'
- 月度汇总: 填写月度页面URL(如'https://cloud.google.com/release-notes/2025-05')

**source_identifier**
- 有独立URL的: 空字符串''
- Azure Updates: 填写created时间戳(如'2025-01-15T10:30:00Z')
- 月度汇总: 填写章节标识(如'section_1'或'cloud-load-balancing')
- 与source_url组合形成唯一约束

**唯一性设计示例**
```
AWS Whatsnew: (https://aws.amazon.com/.../xyz, '')
Azure Updates: (https://azure.microsoft.com/updates/, '2025-01-15T10:30:00Z')
月度汇总: (https://cloud.google.com/release-notes/2025-05, 'section_1')
```

**publish_date**
- 统一为YYYY-MM-DD格式
- 对于月度汇总数据(如"2025-05"),统一转换为该月第一天(如"2025-05-01")

**product_name**
- 产品相关更新应尽可能填写,从爬虫API或配置中提取
- 博客类更新如果无法提取可为空

**product_category**
- 通过product_category_mapping.yaml配置文件映射
- 可选值: networking, compute, storage, database, security, ai_ml, analytics, devtools, management, other

**priority**
- 根据update_type自动设置:
  - critical: security_fix, incident_report
  - high: new_product, new_feature, security_advisory
  - medium: feature_enhancement, new_region, product_ga, bugfix, performance_improvement
  - low: blog_*, case_study, announcement, webinar, whitepaper

**tags**
- 存储为JSON数组字符串,如'["VPC", "网络", "安全"]'
- 来源:
  - AWS: 从API的tags.id解析所有标签
  - Azure: API的categories或tags字段
  - Blog: 从标题或内容提取关键词
  - 其他: 从内容或配置中提取

**content_summary**
- 产品更新: API返回的description字段
- 博客: 文章开头摘要或AI生成摘要
- 用于搜索和预览,非必填

**metadata_json**
- 存储额外的非结构化元数据,按类型存储不同信息:
  - Azure Updates: {"azure_created": "2025-01-15T10:30:00Z", "azure_modified": "...", "api_products": [...], "api_categories": [...]}
  - AWS Whatsnew: {"api_tags": [...], "post_type": "launch"}
  - 月度汇总: {"base_url": "https://...", "section_index": 1, "section_title": "Cloud Load Balancing"}
  - Blog: {"author": "作者名", "reading_time": "5分钟", "related_links": [...]}

#### 3.2.2 update_type 分类体系

更新类型按业务维度分类,支持竞争情报的多维度分析:

##### 产品相关
- **new_product** - 新产品发布
- **new_feature** - 新功能发布
- **feature_enhancement** - 功能增强/改进
- **product_ga** - 产品正式发布(GA - General Availability)
- **product_preview** - 预览版/Beta版
- **product_deprecation** - 产品/功能废弃

##### 基础设施
- **new_region** - 新地域上线
- **new_az** - 新可用区
- **datacenter_expansion** - 数据中心扩展

##### 安全与合规
- **security_fix** - 安全漏洞修复
- **security_advisory** - 安全公告
- **compliance_cert** - 合规认证更新

##### 稳定性
- **bugfix** - Bug修复
- **performance_improvement** - 性能优化
- **incident_report** - 故障事后分析

##### 商业
- **pricing_change** - 价格调整
- **case_study** - 客户案例
- **partnership** - 合作伙伴公告

##### 内容
- **blog_technical** - 技术博客
- **blog_case** - 案例分享博客
- **blog_opinion** - 观点/趋势分析博客
- **webinar** - 网络研讨会
- **whitepaper** - 白皮书

##### 其他
- **announcement** - 一般公告
- **other** - 其他

#### 3.2.3 update_type 识别策略

##### 阶段一: 基于数据源的初步分类

```
AWS Whatsnew / Azure Updates / GCP Whatsnew:
  - 从标题关键词判断
  - 默认为 new_feature

AWS Blog / Azure Blog / GCP Blog:
  - 默认为 blog_technical
  - 根据标题关键词细分为 blog_case / blog_opinion

安全公告渠道:
  - 自动设置为 security_fix 或 security_advisory
```

##### 阶段二: 基于标题关键词的规则匹配

- 标题包含"安全修复"、"CVE-"、"漏洞" → security_fix
- 标题包含"新产品"、"正式发布"、"General Availability" → new_product / product_ga
- 标题包含"新功能"、"上线"、"now available" → new_feature
- 标题包含"价格调整"、"降价"、"price reduction" → pricing_change
- 标题包含"客户案例"、"成功故事"、"customer story" → case_study
- 标题包含"新区域"、"新地域"、"new region" → new_region
- 标题包含"Preview"、"Beta" → product_preview
- 标题包含"废弃"、"deprecation"、"end of life" → product_deprecation

##### 阶段三: AI辅助分类(可选,第二阶段)

对于难以通过规则判断的更新:
- 使用轻量级AI模型分析title + content_summary
- 返回update_type和置信度
- 低置信度的标记为other,待人工审核

#### 3.2.4 AnalysisTask实体

记录对Update执行的AI分析任务及结果。

| 字段名 | 类型 | 说明 | 必填 | 索引 |
|--------|------|------|------|------|
| task_id | TEXT | 任务唯一标识,UUID格式 | 是 | 主键 |
| update_id | TEXT | 关联的update_id | 是 | 外键+索引 |
| task_name | TEXT | 任务名称(如"AI标题翻译"、"AI竞争分析") | 是 | 是 |
| task_status | TEXT | 任务状态(pending/running/success/failed) | 是 | 是 |
| task_result | TEXT | 任务结果内容 | 否 | - |
| error_message | TEXT | 错误信息(如果失败) | 否 | - |
| started_at | DATETIME | 任务开始时间 | 否 | - |
| completed_at | DATETIME | 任务完成时间 | 否 | - |
| created_at | DATETIME | 记录创建时间 | 是 | - |

##### 关联关系
- update_id关联到updates表,支持级联查询
- 一个Update可以有多个AnalysisTask记录

### 3.3 数据库表结构设计

#### 3.3.1 updates表

表结构定义:
- 主键: update_id
- 组合唯一索引: (source_url, source_identifier) - 核心去重约束
- 单列索引: vendor, update_type, publish_date, product_name, product_category, priority, source_url
- 组合索引: (vendor, publish_date), (update_type, publish_date), (vendor, product_name)

字段详细定义:
- update_id: TEXT类型,主键
- vendor: TEXT类型,NOT NULL,有索引
- update_type: TEXT类型,NOT NULL,有索引
- source_url: TEXT类型,NOT NULL,有索引,参与组合唯一索引
- source_identifier: TEXT类型,NOT NULL,默认值'',参与组合唯一索引
- title: TEXT类型,NOT NULL
- title_translated: TEXT类型,允许NULL
- content_summary: TEXT类型,允许NULL
- publish_date: TEXT类型,NOT NULL,有索引
- crawl_time: TEXT类型,NOT NULL
- product_name: TEXT类型,允许NULL,有索引
- product_category: TEXT类型,允许NULL,有索引
- priority: TEXT类型,允许NULL,有索引
- tags: TEXT类型,允许NULL
- raw_filepath: TEXT类型,NOT NULL
- analysis_filepath: TEXT类型,允许NULL
- file_hash: TEXT类型,允许NULL
- metadata_json: TEXT类型,允许NULL
- created_at: DATETIME类型,默认值CURRENT_TIMESTAMP
- updated_at: DATETIME类型,默认值CURRENT_TIMESTAMP

#### 3.3.2 analysis_tasks表

表结构定义:
- 主键: task_id
- 外键: update_id REFERENCES updates(update_id) ON DELETE CASCADE
- 单列索引: update_id, task_name, task_status
- 组合索引: (update_id, task_name)

字段详细定义:
- task_id: TEXT类型,主键
- update_id: TEXT类型,NOT NULL,外键
- task_name: TEXT类型,NOT NULL
- task_status: TEXT类型,NOT NULL
- task_result: TEXT类型,允许NULL
- error_message: TEXT类型,允许NULL
- started_at: DATETIME类型,允许NULL
- completed_at: DATETIME类型,允许NULL
- created_at: DATETIME类型,默认值CURRENT_TIMESTAMP

#### 3.3.3 migration_history表

记录数据迁移历史,用于追踪和审计。

表结构定义:
- 主键: migration_id(自增INTEGER)
- 单列索引: migration_type, status

字段详细定义:
- migration_id: INTEGER类型,主键,自增
- migration_type: TEXT类型,NOT NULL,有索引
- source_path: TEXT类型,允许NULL
- updates_count: INTEGER类型,默认值0
- tasks_count: INTEGER类型,默认值0
- status: TEXT类型,NOT NULL,有索引
- error_message: TEXT类型,允许NULL
- started_at: DATETIME类型,NOT NULL
- completed_at: DATETIME类型,允许NULL
- created_at: DATETIME类型,默认值CURRENT_TIMESTAMP

### 3.4 数据库文件组织

数据库文件存放位置:

```
data/
├── sqlite/
│   ├── updates.db              # 统一业务数据层主数据库
│   ├── updates.db-wal          # SQLite WAL日志文件(自动生成)
│   ├── updates.db-shm          # SQLite共享内存文件(自动生成)
│   └── access_logs.db           # 访问日志数据库(现有)
```

数据库配置参数:
- journal_mode: WAL模式,提升并发读写性能
- synchronous: NORMAL,平衡性能与数据安全
- cache_size: 默认-64000(约64MB缓存)
- temp_store: MEMORY,临时表存于内存
- foreign_keys: ON,启用外键约束

### 3.5 统一Schema的设计优势

采用统一的updates表存储所有类型的更新,而非分表设计,带来以下核心优势:

#### 3.5.1 跨类型数据分析

优势: 可轻松进行跨源类型的聚合和对比分析

场景1: 产品全景视图
- 查询需求: 查看VPC相关的所有内容(不区分是blog还是whatsnew)
- 查询条件: product_name包含'vpc'
- 分析维度: 按厂商、update_type统计
- 业务价值: 了解各厂商在VPC领域的内容产出和关注度

场景2: 厂商内容策略分析
- 查询需求: 对比各厂商在网络领域的内容类型偏好
- 查询条件: product_category = 'networking'
- 分析维度: 按厂商、update_type分组
- 业务价值: 识别哪些厂商更注重技术博客,哪些更注重产品更新公告

场景3: 产品热度排行
- 查询需求: 最近一个月最热门的产品(综合blog和whatsnew的提及次数)
- 查询条件: publish_date近30天,product_name非空
- 分析维度: 按product_name分组计数
- 业务价值: 发现行业热点和技术趋势

#### 3.5.2 简化查询逻辑

优势: 单表查询,无需复杂的UNION或JOIN

对比分表设计:
- 分表设计需要:
  ```
  从blog_updates表查询 WHERE ...
  UNION ALL
  从whatsnew_updates表查询 WHERE ...
  UNION ALL
  从monthly_updates表查询 WHERE ...
  ```

- 统一设计只需:
  ```
  从updates表查询 WHERE ...
  ```

查询性能更优,代码更简洁,维护成本更低。

#### 3.5.3 前端开发友好

优势: 前端调用统一的API,无需关心数据来源

前端视角:
- 获取最新更新: GET /api/v1/updates?limit=20&order_by=publish_date (自动包含所有类型)
- 按产品筛选: GET /api/v1/updates?product_name=vpc (blog和whatsnew一起返回)
- 按厂商筛选: GET /api/v1/updates?vendor=aws (所有类型统一处理)

如需区分类型,仅需在查询参数中添加update_type过滤,前端组件可复用。

#### 3.5.4 扩展性强

优势: 新增厂商或新的内容类型无需改表结构

扩展场景:
- 新增厂商(如阿里云): 直接插入updates表,无需建新表
- 新增类型(如webinar、whitepaper): 仅需添加update_type值
- 新增字段: ALTER TABLE一次即可,所有类型受益

#### 3.5.5 字段灵活性设计

处理不同类型的字段差异:

通过"允许为空"策略解决:
- product_name: whatsnew通常都有,blog可能为空,WHERE product_name IS NOT NULL可过滤
- tags: 各类型来源不同,但都存为JSON数组,查询一致
- metadata_json: 每种类型存储专属信息,扩展性强

数据完整性不受影响:
- 核心字段(vendor, update_type, source_url, title, publish_date)所有类型都必填
- 可选字段为空时,不影响其他记录的查询和分析
- 通过update_type字段明确区分类型,避免混淆

#### 3.5.6 实际应用示例

示例1: 竞争情报仪表板
- 需求: 展示各厂商最近一周的更新活跃度
- 查询条件: publish_date >= 最近7天
- 分析维度: 按vendor分组,统计总数、blog数量、whatsnew数量
- 优势: 一次查询获得所有维度数据,无需多次查询或UNION

示例2: 产品演进追踪
- 需求: 追踪Amazon VPC从2024年至今的所有相关内容
- 查询条件: product_name包含'VPC', vendor='aws', publish_date >= '2024-01-01'
- 分析维度: 按月份、update_type统计
- 优势: 自动包含新功能发布、博客文章、安全更新等所有类型

示例3: 安全情报分析
- 需求: 所有厂商的安全相关更新
- 查询条件: update_type IN ('security_fix', 'security_advisory')
- 分析维度: 按厂商、产品、优先级统计
- 优势: 跨厂商、跨渠道统一查询,便于对比分析

## 四、组件设计

### 4.1 UpdateDataLayer组件

UpdateDataLayer是统一业务数据层的核心组件,负责数据库连接管理、CRUD操作和查询封装。

#### 4.1.1 组件职责

- 数据库连接管理: 维护SQLite连接池,确保线程安全
- Update CRUD操作: 提供创建、读取、更新、删除Update记录的接口
- 去重检查: 基于(source_url, source_identifier)检查Update是否已存在
- 批量操作: 支持批量插入和更新,提升写入性能
- 查询封装: 提供常用查询方法(按厂商、按类型、按日期范围等)
- 事务管理: 支持事务操作,确保数据一致性

#### 4.1.2 核心接口

查询接口:
- get_update_by_id: 根据update_id获取单条记录
- check_update_exists: 检查Update是否存在(基于source_url和source_identifier)
- query_updates: 通用查询接口,支持多条件组合过滤
- get_updates_by_vendor: 按厂商查询
- get_updates_by_type: 按更新类型查询
- get_updates_by_date_range: 按日期范围查询
- get_updates_by_product: 按产品名称查询

写入接口:
- insert_update: 插入单条Update记录
- batch_insert_updates: 批量插入Update记录
- update_update: 更新单条Update记录
- delete_update: 删除单条Update记录(软删除或硬删除)

统计接口:
- count_updates: 统计符合条件的Update数量
- get_vendor_stats: 获取各厂商的更新统计
- get_type_distribution: 获取更新类型分布
- get_product_ranking: 获取产品热度排行

### 4.2 UpdateManager组件

UpdateManager是业务逻辑层组件,提供更高层次的Update管理功能,包括数据规范化、update_type识别、priority设置等。

#### 4.2.1 组件职责

- 数据规范化: 统一不同来源数据的格式(日期格式、字段命名等)
- Update类型识别: 根据标题和内容自动识别update_type
- 优先级设置: 根据update_type自动设置priority
- 产品分类映射: 根据配置映射product_category
- 标签提取: 从不同来源提取和规范化tags
- 元数据扩展: 构建metadata_json字段
- 文件哈希计算: 计算file_hash用于内容变更检测

#### 4.2.2 核心接口

数据处理接口:
- normalize_update_data: 规范化原始Update数据
- identify_update_type: 识别Update类型
- set_priority: 设置优先级
- map_product_category: 映射产品分类
- extract_tags: 提取标签
- build_metadata_json: 构建扩展元数据

业务接口:
- create_update_from_crawler: 从爬虫数据创建Update
- create_update_from_file: 从文件数据创建Update
- sync_update: 同步Update到数据库(创建或更新)
- refresh_update_metadata: 刷新Update元数据

### 4.3 MigrationService组件

MigrationService负责历史数据迁移,将现有的文件系统数据和元数据迁移到新数据层。

#### 4.3.1 组件职责

- 数据源扫描: 扫描data/raw和data/metadata目录
- 文件解析: 解析Markdown文件和JSON元数据
- 数据转换: 将旧格式数据转换为新的Update模型
- 批量迁移: 批量写入数据库,提升迁移效率
- 进度跟踪: 记录迁移进度和状态
- 错误处理: 记录迁移失败的条目,支持重试
- 迁移验证: 验证迁移后的数据完整性和正确性

#### 4.3.2 迁移流程

阶段1: 扫描和分析
- 扫描data/raw目录,收集所有厂商和源类型
- 加载crawler_metadata.json
- 加载analysis_metadata.json
- 统计待迁移的文件数量

阶段2: 数据转换
- 逐个解析Markdown文件
- 从文件头部提取元数据(标题、发布时间、厂商等)
- 从crawler_metadata提取爬虫元数据
- 从analysis_metadata提取分析任务信息
- 构建Update对象和AnalysisTask对象

阶段3: 批量写入
- 批量插入Update记录(建议批次大小100-500)
- 批量插入AnalysisTask记录
- 记录迁移进度到migration_history表

阶段4: 验证
- 对比文件数量与数据库记录数量
- 验证关键字段完整性
- 生成迁移报告

#### 4.3.3 核心接口

迁移接口:
- migrate_all: 迁移所有历史数据
- migrate_vendor: 迁移指定厂商的数据
- migrate_source_type: 迁移指定源类型的数据
- resume_migration: 恢复中断的迁移任务

验证接口:
- validate_migration: 验证迁移结果
- generate_migration_report: 生成迁移报告
- compare_counts: 对比迁移前后的数量

### 4.4 CrawlerIntegration组件

CrawlerIntegration负责将现有爬虫与新数据层集成,实现数据双写(文件系统+数据库)。

#### 4.4.1 集成策略

采用钩子模式,在BaseCrawler的关键节点注入数据层写入逻辑:

钩子点1: save_to_markdown方法完成后
- 触发时机: 文件写入成功后
- 执行操作: 调用UpdateManager创建Update记录并写入数据库
- 错误处理: 数据库写入失败不影响文件保存,记录错误日志

钩子点2: batch_update_metadata方法完成后
- 触发时机: 元数据批量更新后
- 执行操作: 批量同步Update到数据库
- 错误处理: 失败条目单独记录,不阻塞整体流程

钩子点3: 爬虫run方法结束前
- 触发时机: 爬虫任务完成
- 执行操作: 刷新所有待写入的Update,提交事务
- 错误处理: 记录未同步的条目,支持后续补偿

#### 4.4.2 实施方案

方案1: 装饰器模式(推荐)
- 定义@sync_to_database装饰器
- 装饰BaseCrawler的save_to_markdown和batch_update_metadata方法
- 自动拦截并同步到数据库
- 侵入性小,易于维护

方案2: 继承扩展模式
- 创建DatabaseSyncedCrawler继承BaseCrawler
- 重写save_to_markdown和batch_update_metadata方法
- 在方法中调用父类方法后同步到数据库
- 需要修改各厂商爬虫的继承关系

方案3: 事件监听模式
- BaseCrawler发出文件保存事件
- CrawlerIntegration订阅事件并同步到数据库
- 解耦性最好,但实现复杂度较高

#### 4.4.3 数据映射规则

从现有爬虫数据映射到Update模型:

通用字段映射:
- vendor: 从爬虫vendor参数获取
- source_url: 从metadata的URL键或文件内容提取
- title: 从metadata的title字段或文件标题提取
- publish_date: 从metadata的publish_date或crawl_time字段提取,转换为YYYY-MM-DD格式
- crawl_time: 从metadata的crawl_time字段获取
- raw_filepath: 从metadata的filepath字段获取,转换为相对路径
- file_hash: 从metadata的file_hash字段获取

特殊字段映射:
- source_identifier:
  - Azure Updates: 使用created时间戳作为唯一标识
  - 月度汇总: 使用section_index或product_name作为标识
  - 其他: 空字符串

- update_type: 调用UpdateManager.identify_update_type识别

- product_name:
  - AWS Whatsnew: 从API的tags中提取产品名
  - Azure Updates: 从API的products字段提取
  - GCP: 从URL或章节标题提取
  - Blog: 从标题或内容提取,可为空

- tags:
  - AWS: 从API的tags.id字段提取
  - Azure: 从API的categories字段提取
  - 其他: 从标题和内容提取关键词

- metadata_json: 将原始API响应或额外元数据序列化为JSON

### 4.5 QueryAPI组件

QueryAPI提供RESTful API接口,供前端和其他服务查询统一业务数据层。

#### 4.5.1 API端点设计

查询端点:
- GET /api/v1/updates: 查询Updates列表,支持分页和多条件过滤
- GET /api/v1/updates/:update_id: 获取单条Update详情
- GET /api/v1/updates/search: 全文搜索Updates
- GET /api/v1/updates/vendors/:vendor: 按厂商查询
- GET /api/v1/updates/types/:update_type: 按类型查询
- GET /api/v1/updates/products/:product_name: 按产品查询

统计端点:
- GET /api/v1/stats/overview: 获取总体统计
- GET /api/v1/stats/vendors: 获取各厂商统计
- GET /api/v1/stats/types: 获取类型分布
- GET /api/v1/stats/products: 获取产品热度排行
- GET /api/v1/stats/trends: 获取时间趋势数据

分析任务端点:
- GET /api/v1/updates/:update_id/tasks: 获取Update的分析任务列表
- GET /api/v1/tasks/:task_id: 获取单个分析任务详情

#### 4.5.2 查询参数设计

通用查询参数:
- limit: 返回记录数,默认20,最大100
- offset: 偏移量,用于分页
- order_by: 排序字段,默认publish_date
- order: 排序方向,asc或desc,默认desc
- fields: 返回字段列表,逗号分隔,支持字段裁剪

过滤参数:
- vendor: 厂商过滤,支持逗号分隔多个值
- update_type: 类型过滤,支持逗号分隔多个值
- product_name: 产品名称过滤,支持模糊匹配
- product_category: 产品分类过滤
- priority: 优先级过滤
- date_from: 开始日期,YYYY-MM-DD格式
- date_to: 结束日期,YYYY-MM-DD格式
- keyword: 关键词搜索,匹配标题和摘要

#### 4.5.3 响应格式

标准响应格式:
```
{
  "success": true,
  "data": {
    "items": [...],
    "total": 1234,
    "limit": 20,
    "offset": 0
  },
  "message": "查询成功"
}
```

错误响应格式:
```
{
  "success": false,
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "参数vendor无效"
  }
}
```

## 五、实施要点

### 5.1 核心任务分解

#### 任务组1: 数据库基础设施
- 创建updates表、analysis_tasks表、migration_history表及所有索引
- 配置数据库参数(WAL模式、缓存大小、外键约束等)
- 设置数据库备份策略

#### 任务组2: 核心组件开发
- UpdateDataLayer: 数据库连接管理、CRUD接口、查询封装、事务管理
- UpdateManager: 数据规范化、update_type识别、priority设置、product_category映射
- MigrationService: 文件扫描解析、数据转换、批量写入、进度跟踪
- CrawlerIntegration: 装饰器钩子、数据映射、错误处理、补偿机制
- QueryAPI: RESTful端点、参数验证、响应格式化、限流缓存

#### 任务组3: 数据迁移
- 备份现有数据(data/raw和data/metadata)
- 执行批量迁移脚本
- 验证迁移结果(数量对比、字段完整性)
- 处理异常数据
- 生成迁移报告

#### 任务组4: 爬虫集成
- 为BaseCrawler添加数据层同步钩子
- 实现各厂商爬虫的数据映射逻辑
- 测试数据双写功能
- 添加同步日志和监控

#### 任务组5: API集成和测试
- 在Web Server中注册新API路由
- 实现查询参数解析和验证
- 添加API访问日志
- 性能测试和优化
- 验证数据一致性

### 5.2 关键技术实现点

#### 数据库连接管理
- 使用contextmanager模式管理连接生命周期
- 设置合理的timeout避免死锁
- 启用row_factory支持字典式访问

#### 批量写入优化
- 使用executemany批量插入,建议批次大小100-500条
- 在事务中执行批量操作,减少磁盘IO
- 预编译SQL语句,提升执行效率

#### 唯一性约束处理
- 利用UNIQUE索引自动去重
- INSERT OR IGNORE跳过重复记录
- INSERT OR REPLACE更新已存在记录

#### update_type识别优化
- 构建关键词规则库,支持中英文匹配
- 使用正则表达式提取特征
- 实现规则优先级排序,避免冲突

#### 数据映射策略
- 建立字段映射配置文件,降低硬编码
- 实现通用的数据转换函数
- 处理缺失字段和异常值

## 六、关键技术考量

### 6.1 数据迁移策略

#### 备份保障
- 迁移前完整备份data/raw和data/metadata目录
- 使用rsync或tar保留文件权限和时间戳
- 备份现有数据库文件(如果已存在)

#### 分批迁移
- 按厂商分批迁移,降低单次失败影响范围
- 每批迁移后验证数据完整性再继续
- 记录迁移进度到migration_history表,支持断点续传

#### 数据验证
- 对比文件数量与数据库记录数量
- 验证关键字段(vendor, title, publish_date)完整性
- 检查source_url和source_identifier的唯一性约束
- 生成迁移报告,列出异常数据

### 6.2 性能优化策略

#### 索引设计
- 为高频查询字段创建单列索引: vendor, update_type, publish_date, product_name
- 为常见组合查询创建组合索引: (vendor, publish_date), (update_type, publish_date)
- 避免过多索引影响写入性能,平衡读写需求

#### WAL模式优化
- 启用WAL模式提升并发读写性能
- 设置checkpoint间隔,控制WAL文件大小
- 定期执行VACUUM优化数据库文件

#### 批量操作优化
- 批量插入使用executemany,减少SQL解析开销
- 在事务中执行批量操作,减少提交次数
- 合理设置批次大小(建议100-500条),平衡内存和性能

#### 查询优化
- 使用EXPLAIN QUERY PLAN分析慢查询
- 避免SELECT *,只查询需要的字段
- 对大结果集使用LIMIT和OFFSET分页
- 实施查询结果缓存,减少数据库压力

### 6.3 数据一致性保障

#### 事务机制
- 批量写入使用事务,确保原子性
- 迁移过程使用事务,失败自动回滚
- 关键操作(如更新update_type)使用事务保护

#### 双写策略
- 文件系统写入失败,不执行数据库写入
- 数据库写入失败,记录错误日志但不影响文件保存
- 实现补偿机制,定期同步缺失的数据库记录

#### 数据校验
- 定期执行一致性检查脚本
- 对比文件系统与数据库的记录数量
- 验证关键字段的完整性和正确性
- 生成不一致报告,支持手动修复

### 6.4 错误处理机制

#### 迁移错误处理
- 记录迁移失败的文件路径和错误信息
- 迁移失败不中断整体流程,继续处理后续文件
- 提供重试机制,支持手动或自动重试失败条目

#### 爬虫集成错误处理
- 数据库写入失败记录详细日志(错误类型、堆栈、数据内容)
- 失败数据暂存到pending队列,定期重试
- 连续失败超过阈值触发告警

#### 降级策略
- 数据库不可用时,降级为仅文件系统存储
- 数据库恢复后,自动同步降级期间的数据
- 保留旧的元数据管理方式作为备份

## 七、验收标准

### 7.1 功能完整性

- 所有历史数据成功迁移到数据库,迁移成功率≥99%
- 所有厂商爬虫成功集成数据层,数据双写成功率≥99.5%
- 查询API覆盖所有核心业务场景
- 支持按厂商、类型、产品、日期等多维度查询
- 支持全文搜索和关键词过滤

### 7.2 性能指标

- 单条Update插入延迟<10ms
- 批量插入(100条)延迟<100ms
- 常规查询响应时间<50ms
- 复杂聚合查询响应时间<200ms
- 数据库并发读取支持≥100 QPS
- 数据库并发写入支持≥50 TPS

### 7.3 数据质量

- 核心字段(vendor, update_type, source_url, title, publish_date)完整率100%
- update_type识别准确率≥85%
- priority设置准确率≥95%
- product_category映射覆盖率≥80%
- 数据一致性检查通过率≥99.9%

### 7.4 稳定性

- 系统可用性≥99.9%
- 数据层同步失败率<0.5%
- API错误率<0.1%
- 无数据丢失事故
- 无严重性能问题

## 八、功能扩展方向

### 8.1 数据质量提升

- 完善update_type识别规则,增加更多关键词匹配模式
- 引入轻量级AI模型辅助分类(可选择本地模型或API)
- 优化product_category映射配置,覆盖更多产品
- 实现数据清洗逻辑,自动修正常见错误
- 添加数据质量评分机制

### 8.2 查询功能增强

- 增加全文搜索功能,支持标题和内容摘要检索
- 实现高级过滤器(多条件组合、范围查询、模糊匹配)
- 支持聚合查询(分组统计、排行榜、趋势分析)
- 添加数据导出功能(JSON, CSV, Excel格式)
- 实现查询结果缓存,提升响应速度

### 8.3 分析能力扩展

- 厂商对比分析(更新频率、产品覆盖、内容类型分布)
- 产品热度趋势(提及次数、更新频率、时间分布)
- 竞争情报仪表板(关键指标、可视化图表、定制维度)
- 关联分析(产品关联、技术关联、厂商策略)
- 异常检测(更新频率异常、产品冷热度变化)

### 8.4 系统优化方向

- 数据库性能调优(索引优化、查询优化、参数调整)
- 支持更大数据量(百万级记录、TB级存储)
- 评估数据库迁移方案(SQLite vs PostgreSQL vs MySQL)
- 实现数据归档机制(冷热数据分离)
- 引入缓存层(Redis)提升查询性能

### 8.5 智能化增强

- 基于机器学习的自动分类(update_type、priority、product_category)
- NLP技术提取产品名称和关键信息
- 构建知识图谱(产品-技术-厂商关联)
- 智能推荐(相关更新、类似产品、竞品对比)
- 趋势预测(产品发展方向、技术热点预判)
