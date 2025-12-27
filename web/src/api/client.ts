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
} from '@/types';

// 创建 axios 实例
const apiClient: AxiosInstance = axios.create({
  baseURL: '/api/v1',
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
    const response = await apiClient.get('/updates', { params });
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

  // 获取时间线统计
  async getTimeline(params: {
    granularity?: 'day' | 'week' | 'month';
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
};

/**
 * AI 分析相关 API
 */
export const analysisApi = {
  // 单条分析
  async analyzeSingle(updateId: string): Promise<ApiResponse<AnalysisResult>> {
    const response = await apiClient.post('/analysis/single', { update_id: updateId });
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

export default apiClient;
