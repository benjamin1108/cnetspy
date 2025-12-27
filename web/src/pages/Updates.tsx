/**
 * 更新列表页面
 */

import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useInfiniteUpdates, useVendors, useUpdateTypes, useProductSubcategories, useAvailableYears } from '@/hooks';
import {
  Card,
  CardContent,
  Loading,
  EmptyState,
  Button,
  Input,
  Select,
} from '@/components/ui';
import { formatDate, getVendorColor, cn, truncate } from '@/lib/utils';
import {
  VENDOR_DISPLAY_NAMES,
  UPDATE_TYPE_LABELS,
  SOURCE_CHANNEL_LABELS,
} from '@/types';
import type { UpdateQueryParams, UpdateBrief } from '@/types';
import { Search, X, CheckCircle, Circle, Calendar, Loader2 } from 'lucide-react';

export function UpdatesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchInput, setSearchInput] = useState(searchParams.get('keyword') || '');

  // 从 URL 解析查询参数（不包含 page，因为使用无限滚动）
  const queryParams: Omit<UpdateQueryParams, 'page'> = useMemo(() => ({
    vendor: searchParams.get('vendor') || undefined,
    source_channel: searchParams.get('source_channel') || undefined,
    update_type: searchParams.get('update_type') || undefined,
    product_category: searchParams.get('product_category') || undefined,
    product_subcategory: searchParams.get('product_subcategory') || undefined,
    date_from: searchParams.get('date_from') || undefined,
    date_to: searchParams.get('date_to') || undefined,
    has_analysis: searchParams.get('has_analysis') === 'true' 
      ? true 
      : searchParams.get('has_analysis') === 'false' 
        ? false 
        : undefined,
    keyword: searchParams.get('keyword') || undefined,
    page_size: 20,
    sort_by: searchParams.get('sort_by') || 'publish_date',
    order: (searchParams.get('order') as 'asc' | 'desc') || 'desc',
  }), [searchParams]);

  // 获取更新列表（无限滚动）
  const { 
    data, 
    isLoading, 
    error, 
    fetchNextPage, 
    hasNextPage, 
    isFetchingNextPage 
  } = useInfiniteUpdates(queryParams);

  // 滚动加载监听
  const loadMoreRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 }
    );
    
    if (loadMoreRef.current) {
      observer.observe(loadMoreRef.current);
    }
    
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // 获取厂商列表
  const { data: vendorsData } = useVendors();

  // 获取动态枚举（需要先选择厂商）
  const { data: updateTypesData } = useUpdateTypes(queryParams.vendor);
  const { data: subcategoriesData } = useProductSubcategories(queryParams.vendor);

  // 获取可用年份列表
  const { data: yearsData } = useAvailableYears();
  const availableYears = yearsData?.data || [];

  // 更新查询参数
  const updateParams = useCallback((updates: Partial<UpdateQueryParams>) => {
    const newParams = new URLSearchParams(searchParams);
    
    Object.entries(updates).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        newParams.set(key, String(value));
      } else {
        newParams.delete(key);
      }
    });
    
    // 如果改变了筛选条件，重置页码
    if (!('page' in updates)) {
      newParams.set('page', '1');
    }
    
    setSearchParams(newParams);
  }, [searchParams, setSearchParams]);

  // 处理搜索
  const handleSearch = useCallback(() => {
    updateParams({ keyword: searchInput || undefined });
  }, [searchInput, updateParams]);

  // 处理键盘事件
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  }, [handleSearch]);

  // 清除所有筛选
  const clearFilters = useCallback(() => {
    setSearchParams(new URLSearchParams());
    setSearchInput('');
  }, [setSearchParams]);

  // 检查是否有活跃的筛选条件
  const hasActiveFilters = useMemo(() => {
    return !!(
      queryParams.vendor ||
      queryParams.source_channel ||
      queryParams.update_type ||
      queryParams.product_subcategory ||
      queryParams.date_from ||
      queryParams.date_to ||
      queryParams.has_analysis !== undefined ||
      queryParams.keyword
    );
  }, [queryParams]);

  // 合并所有页面的数据
  const updates = useMemo(() => {
    if (!data?.pages) return [];
    return data.pages.flatMap(page => page.data?.items || []);
  }, [data]);
  
  const totalCount = data?.pages[0]?.data?.pagination?.total || 0;
  const vendors = vendorsData?.data || [];
  const updateTypes = updateTypesData?.data || [];
  const subcategories = subcategoriesData?.data || [];

  if (error) {
    return (
      <EmptyState
        title="加载失败"
        description="无法获取更新列表，请稍后重试"
        action={
          <Button onClick={() => window.location.reload()}>重新加载</Button>
        }
      />
    );
  }

  // 可删除的筛选标签组件
  const FilterTag = ({ 
    children, 
    onRemove 
  }: { 
    children: React.ReactNode; 
    onRemove: () => void;
  }) => (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-sm font-medium group">
      {children}
      <button
        onClick={(e) => {
          e.preventDefault();
          onRemove();
        }}
        className="hover:bg-blue-200 rounded-full p-0.5 transition-colors"
        title="移除筛选"
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  );

  // 生成筛选标签列表
  const filterTags = useMemo(() => {
    const tags: { key: string; label: React.ReactNode; onRemove: () => void }[] = [];
    
    // 厂商
    if (queryParams.vendor) {
      tags.push({
        key: 'vendor',
        label: VENDOR_DISPLAY_NAMES[queryParams.vendor] || queryParams.vendor,
        onRemove: () => updateParams({ vendor: undefined, product_subcategory: undefined, update_type: undefined }),
      });
    }
    
    // 来源类型 - 对用户只暴露 "公告" 和 "博客"，不区分底层的具体 blog 类型
    if (queryParams.source_channel) {
      const channelLabel = queryParams.source_channel === 'whatsnew' ? '公告' : '博客';
      tags.push({
        key: 'channel',
        label: channelLabel,
        onRemove: () => updateParams({ source_channel: undefined }),
      });
    }
    
    // 更新类型
    if (queryParams.update_type) {
      tags.push({
        key: 'type',
        label: UPDATE_TYPE_LABELS[queryParams.update_type] || queryParams.update_type,
        onRemove: () => updateParams({ update_type: undefined }),
      });
    }
    
    // 产品子类
    if (queryParams.product_subcategory) {
      tags.push({
        key: 'subcategory',
        label: queryParams.product_subcategory,
        onRemove: () => updateParams({ product_subcategory: undefined }),
      });
    }
    
    // 分析状态
    if (queryParams.has_analysis === true) {
      tags.push({
        key: 'analyzed',
        label: '已分析',
        onRemove: () => updateParams({ has_analysis: undefined }),
      });
    } else if (queryParams.has_analysis === false) {
      tags.push({
        key: 'not-analyzed',
        label: '未分析',
        onRemove: () => updateParams({ has_analysis: undefined }),
      });
    }
    
    // 日期范围
    if (queryParams.date_from || queryParams.date_to) {
      let dateText = '';
      if (queryParams.date_from && queryParams.date_to) {
        dateText = `${queryParams.date_from} 至 ${queryParams.date_to}`;
      } else if (queryParams.date_from) {
        dateText = `${queryParams.date_from} 起`;
      } else {
        dateText = `至 ${queryParams.date_to}`;
      }
      tags.push({
        key: 'date',
        label: dateText,
        onRemove: () => updateParams({ date_from: undefined, date_to: undefined }),
      });
    }
    
    // 关键词
    if (queryParams.keyword) {
      tags.push({
        key: 'keyword',
        label: <>关键词「{queryParams.keyword}」</>,
        onRemove: () => {
          updateParams({ keyword: undefined });
          setSearchInput('');
        },
      });
    }
    
    return tags;
  }, [queryParams, updateParams]);

  return (
    <div className="space-y-4">
      {/* 页面标题 - 横跨全宽 */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">更新列表</h1>
        <div className="text-gray-500 mt-2 flex flex-wrap items-center gap-1.5">
          {filterTags.length === 0 ? (
            <span>浏览所有云厂商的产品更新</span>
          ) : (
            <>
              <span className="text-gray-400 mr-1">筛选：</span>
              {filterTags.map((tag) => (
                <FilterTag key={tag.key} onRemove={tag.onRemove}>
                  {tag.label}
                </FilterTag>
              ))}
              {filterTags.length > 1 && (
                <button
                  onClick={clearFilters}
                  className="text-xs text-gray-400 hover:text-red-500 ml-1 transition-colors"
                >
                  清除全部
                </button>
              )}
            </>
          )}
          {totalCount > 0 && (
            <span className="text-gray-400">· 共 {totalCount} 条记录</span>
          )}
        </div>
      </div>

      {/* 双栏布局 */}
      <div className="flex gap-6">
        {/* 左侧主内容区 */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* 搜索框 */}
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="搜索标题或内容..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={handleKeyDown}
                className="pl-10"
              />
            </div>
            <Button onClick={handleSearch}>搜索</Button>
          </div>

          {/* 更新列表 */}
          {isLoading ? (
            <Loading message="加载更新列表..." />
          ) : updates.length === 0 ? (
            <EmptyState
              title="暂无更新"
              description={hasActiveFilters ? '尝试调整筛选条件' : '暂时没有任何更新记录'}
              action={
                hasActiveFilters && (
                  <Button variant="outline" onClick={clearFilters}>
                    清除筛选
                  </Button>
                )
              }
            />
          ) : (
            <>
              <div className="space-y-3">
                {updates.map((update) => (
                  <UpdateCard key={update.update_id} update={update} onFilter={updateParams} />
                ))}
              </div>
              
              {/* 无限滚动加载触发器 */}
              <div ref={loadMoreRef} className="py-8 flex justify-center">
                {isFetchingNextPage ? (
                  <div className="flex items-center gap-2 text-gray-500">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    <span>加载中...</span>
                  </div>
                ) : hasNextPage ? (
                  <span className="text-gray-400 text-sm">向下滚动加载更多</span>
                ) : updates.length > 0 ? (
                  <span className="text-gray-400 text-sm">已加载全部 {totalCount} 条记录</span>
                ) : null}
              </div>
            </>
          )}
        </div>

        {/* 右侧边栏 */}
        <div className="w-64 flex-shrink-0 hidden lg:block">
          <Card className="sticky top-20">
            <CardContent className="p-4">
              <h3 className="font-medium text-gray-900 mb-3">筛选条件</h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">厂商</label>
                  <Select
                    value={queryParams.vendor || ''}
                    onChange={(e) => updateParams({ 
                      vendor: e.target.value || undefined,
                      product_subcategory: undefined,
                      update_type: undefined
                    })}
                    className="w-full"
                  >
                    <option value="">全部厂商</option>
                    {vendors.map((v) => (
                      <option key={v.vendor} value={v.vendor}>
                        {VENDOR_DISPLAY_NAMES[v.vendor] || v.vendor}
                      </option>
                    ))}
                  </Select>
                </div>

                <div>
                  <label className="block text-xs text-gray-500 mb-1">来源</label>
                  <Select
                    value={queryParams.source_channel || ''}
                    onChange={(e) => updateParams({ source_channel: e.target.value || undefined })}
                    className="w-full"
                  >
                    <option value="">全部</option>
                    <option value="whatsnew">公告</option>
                    <option value="blog">博客</option>
                  </Select>
                </div>

                <div>
                  <label className="block text-xs text-gray-500 mb-1">产品子类</label>
                  <Select
                    value={queryParams.product_subcategory || ''}
                    onChange={(e) => updateParams({ product_subcategory: e.target.value || undefined })}
                    disabled={!queryParams.vendor}
                    className="w-full"
                  >
                    <option value="">{queryParams.vendor ? '全部' : '先选厂商'}</option>
                    {subcategories.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.value}
                      </option>
                    ))}
                  </Select>
                </div>

                <div>
                  <label className="block text-xs text-gray-500 mb-1">更新类型</label>
                  <Select
                    value={queryParams.update_type || ''}
                    onChange={(e) => updateParams({ update_type: e.target.value || undefined })}
                    disabled={!queryParams.vendor}
                    className="w-full"
                  >
                    <option value="">{queryParams.vendor ? '全部' : '先选厂商'}</option>
                    {updateTypes.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </Select>
                </div>

                <div>
                  <label className="block text-xs text-gray-500 mb-1">分析状态</label>
                  <Select
                    value={queryParams.has_analysis === undefined ? '' : String(queryParams.has_analysis)}
                    onChange={(e) => {
                      const value = e.target.value;
                      updateParams({
                        has_analysis: value === '' ? undefined : value === 'true',
                      });
                    }}
                    className="w-full"
                  >
                    <option value="">全部</option>
                    <option value="true">已分析</option>
                    <option value="false">未分析</option>
                  </Select>
                </div>

                <div>
                  <label className="block text-xs text-gray-500 mb-1">年份</label>
                  <Select
                    value={queryParams.date_from?.substring(0, 4) || ''}
                    onChange={(e) => {
                      const year = e.target.value;
                      if (year) {
                        updateParams({ 
                          date_from: `${year}-01-01`,
                          date_to: `${year}-12-31`
                        });
                      } else {
                        updateParams({ date_from: undefined, date_to: undefined });
                      }
                    }}
                    className="w-full"
                  >
                    <option value="">全部</option>
                    {availableYears.map((year) => (
                      <option key={year} value={year}>{year}</option>
                    ))}
                  </Select>
                </div>

                {hasActiveFilters && (
                  <Button variant="ghost" size="sm" onClick={clearFilters} className="w-full text-xs">
                    <X className="h-3 w-3 mr-1" />
                    清除所有筛选
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

// 更新卡片组件
interface UpdateCardProps {
  update: UpdateBrief;
  onFilter: (params: Partial<UpdateQueryParams>) => void;
}

function UpdateCard({ update, onFilter }: UpdateCardProps) {
  // 可点击的标签组件
  const ClickableBadge = ({ 
    children, 
    onClick, 
    className = '' 
  }: { 
    children: React.ReactNode; 
    onClick: () => void; 
    className?: string;
  }) => (
    <button
      onClick={(e) => {
        e.preventDefault();
        onClick();
      }}
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium transition-all",
        "hover:ring-2 hover:ring-offset-1 hover:ring-blue-300 cursor-pointer",
        className
      )}
    >
      {children}
    </button>
  );

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardContent className="p-4">
        <div className="flex flex-col gap-2">
          {/* 第一行：标题 */}
          <Link
            to={`/updates/${update.update_id}`}
            className="block group"
          >
            <h3 className="text-base font-medium text-gray-900 group-hover:text-blue-600 transition-colors line-clamp-2">
              {update.title_translated || update.title}
            </h3>
          </Link>

          {/* 第二行：描述/摘要 */}
          {(update.content_summary || update.description) && (
            <p className="text-sm text-gray-500 line-clamp-2">
              {truncate(update.content_summary || update.description || '', 150)}
            </p>
          )}

          {/* 第三行：元信息标签 */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs pt-1">
            {/* 发布时间 */}
            <span className="flex items-center gap-1 text-gray-400">
              <Calendar className="h-3 w-3" />
              {formatDate(update.publish_date)}
            </span>
            
            {/* 厂商标签 - 可点击 */}
            <ClickableBadge
              onClick={() => onFilter({ vendor: update.vendor })}
              className="border bg-white"
            >
              <span
                className="w-1.5 h-1.5 rounded-full mr-1"
                style={{ backgroundColor: getVendorColor(update.vendor) }}
              />
              {VENDOR_DISPLAY_NAMES[update.vendor] || update.vendor}
            </ClickableBadge>

            {/* 来源渠道 - 可点击 */}
            <ClickableBadge
              onClick={() => {
                // blog 类型统一使用 'blog' 进行筛选（后端会模糊匹配所有 *-blog）
                // whatsnew 使用精确匹配
                const channelFilter = update.source_channel === 'whatsnew' ? 'whatsnew' : 'blog';
                onFilter({ source_channel: channelFilter });
              }}
              className="bg-gray-100 text-gray-600"
            >
              {SOURCE_CHANNEL_LABELS[update.source_channel] || update.source_channel}
            </ClickableBadge>

            {/* 更新类型 - 可点击 */}
            {update.update_type && (
              <ClickableBadge
                onClick={() => onFilter({ vendor: update.vendor, update_type: update.update_type ?? undefined })}
                className="bg-blue-100 text-blue-700"
              >
                {UPDATE_TYPE_LABELS[update.update_type] || update.update_type}
              </ClickableBadge>
            )}

            {/* 产品子类 - 可点击 */}
            {update.product_subcategory && (
              <ClickableBadge
                onClick={() => onFilter({ vendor: update.vendor, product_subcategory: update.product_subcategory ?? undefined })}
                className="bg-purple-100 text-purple-700"
              >
                {update.product_subcategory}
              </ClickableBadge>
            )}

            {/* 分析状态 */}
            <span className={cn(
              'flex items-center gap-0.5 ml-auto',
              update.has_analysis ? 'text-green-600' : 'text-gray-300'
            )}>
              {update.has_analysis ? (
                <CheckCircle className="h-3.5 w-3.5" />
              ) : (
                <Circle className="h-3.5 w-3.5" />
              )}
            </span>
          </div>

          {/* 第四行：Tags 标签（单独一行） */}
          {update.tags && update.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {update.tags.map((tag, idx) => (
                <span
                  key={idx}
                  className="px-1.5 py-0.5 bg-gray-50 text-gray-500 rounded text-xs border border-gray-200"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
