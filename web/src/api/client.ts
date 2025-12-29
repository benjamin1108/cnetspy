/**
 * API 客户端
 * 封装所有与后端的通信
 */

import axios, { type AxiosInstance } from 'axios';
import type {
  ApiResponse,
  PaginatedResponse,
  UpdateBrief,
  UpdateDetail,
  UpdateQueryParams,
  StatsOverview,
  TimelineItem,
  VendorStatsItem,
  VendorInfo,
  ProductInfo,
  UpdateTypeInfo,
  AnalysisResult,
  AnalysisTaskStatus,
  VendorTypeMatrixItem,
  TrendData,
  ReportData,
  AvailableMonth,
} from '@/types';

// 获取 API 基础路径（生产环境使用 /next/api/v1）
const getApiBaseUrl = () => {
  if (import.meta.env.PROD) {
    return '/next/api/v1';
  }
  return '/api/v1';
};

// 创建 axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 可以在这里添加认证token等
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // 统一错误处理
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

/**
 * 更新数据相关 API
 */
export const updatesApi = {
  // 获取更新列表
  async getUpdates(params: UpdateQueryParams = {}): Promise<ApiResponse<PaginatedResponse<UpdateBrief>>> {
    // 将前端的 tag 映射到后端的 tags 参数
    const { tag, ...rest } = params;
    const apiParams = { ...rest, tags: tag };
    const response = await apiClient.get('/updates', { params: apiParams });
    return response.data;
  },

  // 获取更新详情
  async getUpdateDetail(updateId: string): Promise<ApiResponse<UpdateDetail>> {
    const response = await apiClient.get(`/updates/${updateId}`);
    return response.data;
  },

  // 获取原始 Markdown 内容
  async getUpdateRawContent(updateId: string): Promise<string> {
    const response = await apiClient.get(`/updates/${updateId}/raw`, {
      responseType: 'text',
    });
    return response.data;
  },
};

/**
 * 统计分析相关 API
 */
export const statsApi = {
  // 获取统计概览
  async getOverview(): Promise<ApiResponse<StatsOverview>> {
    const response = await apiClient.get('/stats/overview');
    return response.data;
  },

  // 获取时间线统计（支持 day/week/month/year 粒度）
  async getTimeline(params: {
    granularity?: 'day' | 'week' | 'month' | 'year';
    date_from?: string;
    date_to?: string;
    vendor?: string;
  } = {}): Promise<ApiResponse<TimelineItem[]>> {
    const response = await apiClient.get('/stats/timeline', { params });
    return response.data;
  },

  // 获取厂商统计
  async getVendorStats(params: {
    date_from?: string;
    date_to?: string;
    include_trend?: boolean;
  } = {}): Promise<ApiResponse<VendorStatsItem[]>> {
    const response = await apiClient.get('/stats/vendors', { params });
    return response.data;
  },

  // 获取更新类型统计
  async getUpdateTypeStats(params: {
    date_from?: string;
    date_to?: string;
    vendor?: string;
  } = {}): Promise<ApiResponse<Record<string, number>>> {
    const response = await apiClient.get('/stats/update-types', { params });
    return response.data;
  },

  // 获取可用年份列表
  async getAvailableYears(): Promise<ApiResponse<number[]>> {
    const response = await apiClient.get('/stats/years');
    return response.data;
  },

  // 获取产品热度排行榜
  async getProductHotness(params: {
    vendor?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    include_trend?: boolean;
  } = {}): Promise<ApiResponse<{ product_subcategory: string; count: number; trend?: TrendData }[]>> {
    const response = await apiClient.get('/stats/product-hotness', { params });
    return response.data;
  },

  // 获取厂商-更新类型矩阵
  async getVendorTypeMatrix(params: {
    date_from?: string;
    date_to?: string;
  } = {}): Promise<ApiResponse<VendorTypeMatrixItem[]>> {
    const response = await apiClient.get('/stats/vendor-type-matrix', { params });
    return response.data;
  },
};

/**
 * 元数据相关 API
 */
export const vendorsApi = {
  // 获取厂商列表
  async getVendors(): Promise<ApiResponse<VendorInfo[]>> {
    const response = await apiClient.get('/vendors');
    return response.data;
  },

  // 获取厂商的产品列表
  async getVendorProducts(vendor: string): Promise<ApiResponse<ProductInfo[]>> {
    const response = await apiClient.get(`/vendors/${vendor}/products`);
    return response.data;
  },

  // 获取更新类型枚举
  async getUpdateTypes(vendor?: string): Promise<ApiResponse<UpdateTypeInfo[]>> {
    const response = await apiClient.get('/update-types', { params: { vendor } });
    return response.data;
  },

  // 获取产品子类枚举
  async getProductSubcategories(vendor?: string): Promise<ApiResponse<{ value: string; count: number }[]>> {
    const response = await apiClient.get('/product-subcategories', { params: { vendor } });
    return response.data;
  },

  // 获取标签列表
  async getTags(vendor?: string): Promise<ApiResponse<{ value: string; count: number }[]>> {
    const response = await apiClient.get('/tags', { params: { vendor } });
    return response.data;
  },
};

/**
 * AI 分析相关 API
 */
export const analysisApi = {
  // 单条分析
  async analyzeSingle(updateId: string): Promise<ApiResponse<AnalysisResult>> {
    const response = await apiClient.post(`/analysis/single/${updateId}`);
    return response.data;
  },

  // 批量分析
  async analyzeBatch(params: {
    vendor?: string;
    limit?: number;
    force?: boolean;
  }): Promise<ApiResponse<{ task_id: string; status: string; total: number }>> {
    const response = await apiClient.post('/analysis/batch', params);
    return response.data;
  },

  // 查询任务状态
  async getTaskStatus(taskId: string): Promise<ApiResponse<AnalysisTaskStatus>> {
    const response = await apiClient.get(`/analysis/tasks/${taskId}`);
    return response.data;
  },

  // 获取任务列表
  async getTasks(params: {
    page?: number;
    page_size?: number;
  } = {}): Promise<ApiResponse<PaginatedResponse<AnalysisTaskStatus>>> {
    const response = await apiClient.get('/analysis/tasks', { params });
    return response.data;
  },

  // 翻译单条更新内容
  async translateContent(updateId: string): Promise<ApiResponse<{ update_id: string; success: boolean; content_translated?: string; error?: string }>> {
    const response = await apiClient.post(`/analysis/translate/${updateId}`, {}, { timeout: 120000 });
    return response.data;
  },
};

/**
 * 健康检查 API
 */
export const healthApi = {
  async check(): Promise<{ status: string; database: string; version: string }> {
    const response = await apiClient.get('/health');
    return response.data;
  },
};

/**
 * 竞争分析报告 API
 */
export const reportsApi = {
  // 获取报告数据
  async getReport(reportType: 'weekly' | 'monthly', params: {
    year?: number;
    month?: number;
  } = {}): Promise<ApiResponse<ReportData>> {
    const response = await apiClient.get(`/reports/${reportType}`, { params });
    return response.data;
  },

  // 获取可用月份列表
  async getAvailableMonths(reportType: 'monthly'): Promise<ApiResponse<AvailableMonth[]>> {
    const response = await apiClient.get(`/reports/${reportType}/available-months`);
    return response.data;
  },
};

export default apiClient;
