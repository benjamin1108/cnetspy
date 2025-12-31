/**
 * React Query Hooks
 * 封装数据获取逻辑
 */

import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query';
import { updatesApi, statsApi, vendorsApi, analysisApi, reportsApi } from '@/api';
import type { UpdateQueryParams } from '@/types';

// Query Keys
export const queryKeys = {
  updates: {
    all: ['updates'] as const,
    list: (params: UpdateQueryParams) => ['updates', 'list', params] as const,
    detail: (id: string) => ['updates', 'detail', id] as const,
    raw: (id: string) => ['updates', 'raw', id] as const,
  },
  stats: {
    overview: ['stats', 'overview'] as const,
    timeline: (params?: Record<string, unknown>) => ['stats', 'timeline', params] as const,
    vendors: (params?: Record<string, unknown>) => ['stats', 'vendors', params] as const,
    updateTypes: (params?: Record<string, unknown>) => ['stats', 'updateTypes', params] as const,
    years: ['stats', 'years'] as const,
    productHotness: (params?: Record<string, unknown>) => ['stats', 'productHotness', params] as const,
    vendorTypeMatrix: (params?: Record<string, unknown>) => ['stats', 'vendorTypeMatrix', params] as const,
  },
  vendors: {
    all: ['vendors'] as const,
    list: ['vendors', 'list'] as const,
    products: (vendor: string) => ['vendors', 'products', vendor] as const,
  },
  updateTypes: ['updateTypes'] as const,
  analysis: {
    task: (id: string) => ['analysis', 'task', id] as const,
    tasks: ['analysis', 'tasks'] as const,
  },
};

/**
 * 更新列表 Hook
 */
export function useUpdates(params: UpdateQueryParams = {}) {
  return useQuery({
    queryKey: queryKeys.updates.list(params),
    queryFn: () => updatesApi.getUpdates(params),
    staleTime: 1000 * 60, // 1 minute
  });
}

/**
 * 无限滚动更新列表 Hook
 */
export function useInfiniteUpdates(params: Omit<UpdateQueryParams, 'page'> = {}) {
  return useInfiniteQuery({
    queryKey: ['updates', 'infinite', params],
    queryFn: ({ pageParam = 1 }) => updatesApi.getUpdates({ ...params, page: pageParam, page_size: 20 }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const pagination = lastPage.data?.pagination;
      if (!pagination) return undefined;
      return pagination.page < pagination.total_pages ? pagination.page + 1 : undefined;
    },
    staleTime: 1000 * 60, // 1 minute
  });
}

/**
 * 更新详情 Hook
 */
export function useUpdateDetail(updateId: string) {
  return useQuery({
    queryKey: queryKeys.updates.detail(updateId),
    queryFn: () => updatesApi.getUpdateDetail(updateId),
    enabled: !!updateId,
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * 原始内容 Hook
 */
export function useUpdateRawContent(updateId: string) {
  return useQuery({
    queryKey: queryKeys.updates.raw(updateId),
    queryFn: () => updatesApi.getUpdateRawContent(updateId),
    enabled: !!updateId,
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
}

/**
 * 统计概览 Hook
 */
export function useStatsOverview() {
  return useQuery({
    queryKey: queryKeys.stats.overview,
    queryFn: () => statsApi.getOverview(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * 时间线统计 Hook
 */
export function useStatsTimeline(params: {
  granularity?: 'day' | 'week' | 'month' | 'year';
  date_from?: string;
  date_to?: string;
  vendor?: string;
} = {}) {
  return useQuery({
    queryKey: queryKeys.stats.timeline(params),
    queryFn: () => statsApi.getTimeline(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * 厂商统计 Hook
 */
export function useVendorStats(params: {
  date_from?: string;
  date_to?: string;
  include_trend?: boolean;
} = {}) {
  return useQuery({
    queryKey: queryKeys.stats.vendors(params),
    queryFn: () => statsApi.getVendorStats(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * 更新类型统计 Hook
 */
export function useUpdateTypeStats(params: {
  date_from?: string;
  date_to?: string;
  vendor?: string;
} = {}) {
  return useQuery({
    queryKey: queryKeys.stats.updateTypes(params),
    queryFn: () => statsApi.getUpdateTypeStats(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * 可用年份列表 Hook
 */
export function useAvailableYears() {
  return useQuery({
    queryKey: queryKeys.stats.years,
    queryFn: () => statsApi.getAvailableYears(),
    staleTime: 1000 * 60 * 60, // 1 hour
  });
}

/**
 * 产品热度排行 Hook
 */
export function useProductHotness(params: {
  vendor?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  include_trend?: boolean;
} = {}) {
  return useQuery({
    queryKey: queryKeys.stats.productHotness(params),
    queryFn: () => statsApi.getProductHotness(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * 厂商-更新类型矩阵 Hook
 */
export function useVendorTypeMatrix(params: {
  date_from?: string;
  date_to?: string;
} = {}) {
  return useQuery({
    queryKey: queryKeys.stats.vendorTypeMatrix(params),
    queryFn: () => statsApi.getVendorTypeMatrix(params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * 厂商列表 Hook
 */
export function useVendors() {
  return useQuery({
    queryKey: queryKeys.vendors.list,
    queryFn: () => vendorsApi.getVendors(),
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
}

/**
 * 厂商产品列表 Hook
 */
export function useVendorProducts(vendor: string) {
  return useQuery({
    queryKey: queryKeys.vendors.products(vendor),
    queryFn: () => vendorsApi.getVendorProducts(vendor),
    enabled: !!vendor,
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
}

/**
 * 更新类型列表 Hook
 */
export function useUpdateTypes(vendor?: string) {
  return useQuery({
    queryKey: ['updateTypes', vendor] as const,
    queryFn: () => vendorsApi.getUpdateTypes(vendor),
    enabled: !!vendor,
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
}

/**
 * 产品子类列表 Hook
 */
export function useProductSubcategories(vendor?: string) {
  return useQuery({
    queryKey: ['productSubcategories', vendor] as const,
    queryFn: () => vendorsApi.getProductSubcategories(vendor),
    enabled: !!vendor,
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
}

/**
 * 标签列表 Hook
 */
export function useTags(vendor?: string) {
  return useQuery({
    queryKey: ['tags', vendor] as const,
    queryFn: () => vendorsApi.getTags(vendor),
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
}

/**
 * 单条分析 Mutation
 */
export function useAnalyzeSingle() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (updateId: string) => analysisApi.analyzeSingle(updateId),
    onSuccess: (_, updateId) => {
      // 刷新更新详情缓存
      queryClient.invalidateQueries({ queryKey: queryKeys.updates.detail(updateId) });
      // 刷新列表缓存
      queryClient.invalidateQueries({ queryKey: queryKeys.updates.all });
    },
  });
}

/**
 * 批量分析 Mutation
 */
export function useAnalyzeBatch() {
  return useMutation({
    mutationFn: (params: { vendor?: string; limit?: number; force?: boolean }) =>
      analysisApi.analyzeBatch(params),
  });
}

/**
 * 分析任务状态 Hook
 */
export function useAnalysisTask(taskId: string) {
  return useQuery({
    queryKey: queryKeys.analysis.task(taskId),
    queryFn: () => analysisApi.getTaskStatus(taskId),
    enabled: !!taskId,
    refetchInterval: (query) => {
      // 如果任务还在运行，每2秒刷新一次
      const status = query.state.data?.data?.status;
      return status === 'queued' || status === 'running' ? 2000 : false;
    },
  });
}

/**
 * 翻译单条更新内容 Mutation
 */
export function useTranslateContent() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (updateId: string) => analysisApi.translateContent(updateId),
    onSuccess: (_, updateId) => {
      // 刷新更新详情缓存
      queryClient.invalidateQueries({ queryKey: queryKeys.updates.detail(updateId) });
    },
  });
}

// ==================== 竞争分析报告 ====================

/**
 * 报告数据 Hook
 */
export function useReportData(reportType: 'weekly' | 'monthly', params: {
  year?: number;
  month?: number;
  week?: number;
} = {}) {
  return useQuery({
    queryKey: ['reports', reportType, params],
    queryFn: () => reportsApi.getReport(reportType, params),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
}

/**
 * 可用月份列表 Hook
 */
export function useAvailableMonths() {
  return useQuery({
    queryKey: ['reports', 'available-months'],
    queryFn: () => reportsApi.getAvailableMonths('monthly'),
    staleTime: 1000 * 60 * 60, // 1 hour
  });
}

/**
 * 可用周列表 Hook
 */
export function useAvailableWeeks() {
  return useQuery({
    queryKey: ['reports', 'available-weeks'],
    queryFn: () => reportsApi.getAvailableWeeks(),
    staleTime: 1000 * 60 * 60, // 1 hour
  });
}
