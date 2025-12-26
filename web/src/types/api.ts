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
  tags?: string;
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

// 厂商统计项
export interface VendorStatsItem {
  vendor: string;
  count: number;
  analyzed: number;
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

// 来源渠道显示名称
export const SOURCE_CHANNEL_LABELS: Record<string, string> = {
  whatsnew: '公告',
  'network-blog': '博客',
  'tech-blog': '博客',
  blog: '博客',
};
