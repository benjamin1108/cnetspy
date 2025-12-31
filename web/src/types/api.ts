/**
 * API 响应类型定义
 * 与后端 FastAPI schemas 对应
 */

// 通用 API 响应
export interface ApiResponse<T> {
  success: boolean;
  data: T | null;
  message?: string;
  error?: string;
}

// 分页元数据
export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[];
  pagination: PaginationMeta;
}

// 更新列表项（简化版）
export interface UpdateBrief {
  update_id: string;
  vendor: string;
  source_channel: string;
  title: string;
  title_translated: string | null;
  description: string | null;
  content_summary: string | null;
  publish_date: string;
  product_name: string | null;
  product_category: string | null;
  product_subcategory: string | null;
  update_type: string | null;
  tags: string[];
  has_analysis: boolean;
}

// 更新详情（完整版）
export interface UpdateDetail extends UpdateBrief {
  content: string;
  content_translated: string | null;  // 翻译后的全文内容
  content_summary: string | null;
  product_subcategory: string | null;
  source_url: string;
  crawl_time: string | null;
  raw_filepath: string | null;
  analysis_filepath: string | null;
  created_at: string | null;
  updated_at: string | null;
}

// 查询参数
export interface UpdateQueryParams {
  vendor?: string;
  source_channel?: string;
  update_type?: string;
  product_name?: string;
  product_category?: string;
  product_subcategory?: string;
  date_from?: string;
  date_to?: string;
  has_analysis?: boolean;
  keyword?: string;
  tag?: string;  // 单个标签筛选
  sort_by?: string;
  order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

// 统计概览
export interface StatsOverview {
  total_updates: number;
  vendors: Record<string, VendorStats>;
  update_types: Record<string, number>;
  last_crawl_time: string | null;
  last_daily_task_time: string | null;
  analysis_coverage: number;
}

export interface VendorStats {
  total: number;
  analyzed: number;
}

// 时间线统计项
export interface TimelineItem {
  date: string;
  count: number;
  vendors: Record<string, number>;
}

// 环比趋势数据
export interface TrendData {
  change_percent: number;
  direction: 'up' | 'down' | 'flat';
  current_period: number;
  previous_period: number;
}

// 厂商统计项
export interface VendorStatsItem {
  vendor: string;
  count: number;
  analyzed: number;
  trend?: TrendData;
}

// 厂商-更新类型矩阵项
export interface VendorTypeMatrixItem {
  vendor: string;
  total: number;
  update_types: Record<string, number>;
}

// 产品热度项
export interface ProductHotnessItem {
  product_subcategory: string;
  count: number;
}

// 厂商信息
export interface VendorInfo {
  vendor: string;
  name: string;
  total_updates: number;
  source_channels: string[];
}

// 产品信息
export interface ProductInfo {
  product_name: string;
  category: string;
  count: number;
}

// 更新类型枚举
export interface UpdateTypeInfo {
  value: string;
  label: string;
  description: string;
  count: number;
}

// 分析结果
export interface AnalysisResult {
  title_translated: string;
  content_summary: string;
  update_type: string;
  product_subcategory: string;
  tags: string[];
}

// 批量分析任务状态
export interface AnalysisTaskStatus {
  task_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: {
    completed: number;
    total: number;
  };
  started_at: string;
  completed_at: string | null;
  errors: string[];
}

// 厂商显示名称映射
export const VENDOR_DISPLAY_NAMES: Record<string, string> = {
  aws: 'Amazon Web Services',
  azure: 'Microsoft Azure',
  gcp: 'Google Cloud',
  huawei: '华为云',
  tencentcloud: '腾讯云',
  volcengine: '火山引擎',
};

// 更新类型显示名称映射
export const UPDATE_TYPE_LABELS: Record<string, string> = {
  new_product: '新产品发布',
  new_feature: '新功能发布',
  enhancement: '功能增强',
  deprecation: '功能弃用',
  pricing: '定价调整',
  region: '区域扩展',
  security: '安全更新',
  fix: '问题修复',
  performance: '性能优化',
  compliance: '合规认证',
  integration: '集成能力',
  other: '其他',
};

// 来源渠道显示名称 - 对用户只暴露 "公告" 和 "博客"
export const SOURCE_CHANNEL_LABELS: Record<string, string> = {
  whatsnew: '公告',
  // 所有 blog 类型统一显示为"博客"
  blog: '博客',
  'network-blog': '博客',
  'tech-blog': '博客',
  'infra-blog': '博客',
};

// ==================== 报告相关类型 ====================

// 报告中的更新项
export interface ReportUpdateItem {
  update_id: string;
  vendor: string;
  title: string;
  title_translated: string | null;
  content_summary: string | null;
  publish_date: string;
  update_type: string | null;
  source_channel: string;
}

// 厂商统计摘要
export interface VendorSummary {
  vendor: string;
  count: number;
  analyzed: number;
  update_types: Record<string, number>;
}

// 报告数据
export interface ReportData {
  report_type: 'weekly' | 'monthly';
  date_from: string;
  date_to: string;
  generated_at: string | null;
  ai_summary: string | null;
  html_filepath: string | null;
  total_count: number;
  vendor_summaries: VendorSummary[];
  updates_by_vendor: Record<string, ReportUpdateItem[]>;
}

// 可用月份
export interface AvailableMonth {
  year: number;
  month: number;
  label: string;
}

// 报告类型标签
export const REPORT_TYPE_LABELS: Record<string, string> = {
  weekly: '周报',
  monthly: '月报',
};
