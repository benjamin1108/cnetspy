/**
 * 仪表盘页面 - 竞争情报大盘风格
 */

import { useStatsOverview, useVendorStats, useProductHotness, useVendorTypeMatrix, useAvailableYears } from '@/hooks';
import { Card, CardContent, CardHeader, CardTitle, Loading } from '@/components/ui';
import { PageHeader } from '@/components/ui/PageHeader';
import { getUpdateTypeMeta } from '@/components/icons';
import { formatNumber, formatPercent, getVendorColor, cn, getChartThemeColors } from '@/lib/utils';
import { VENDOR_DISPLAY_NAMES, UPDATE_TYPE_LABELS } from '@/types';
import type { TrendData } from '@/types';
import { format } from 'date-fns';
import { 
  Layers, Activity, Calendar, TrendingUp, TrendingDown, Minus
} from 'lucide-react';
import { useState, useMemo } from 'react';
import { useTheme } from '@/contexts/ThemeContext';

// 趋势标签组件
function TrendBadge({ trend }: { trend?: TrendData }) {
  if (!trend) return null;
  
  const { change_percent, direction } = trend;
  
  if (direction === 'up') {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-emerald-500">
        <TrendingUp className="h-3 w-3" />
        +{change_percent.toFixed(0)}%
      </span>
    );
  } else if (direction === 'down') {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-red-500">
        <TrendingDown className="h-3 w-3" />
        {change_percent.toFixed(0)}%
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
      <Minus className="h-3 w-3" />
      0%
    </span>
  );
}

// 进度条组件
interface ProgressBarProps {
  value: number;
  max: number;
  color: string;
  label: string;
  count: number;
  delay?: number;
  size?: 'sm' | 'md' | 'lg';
  showPercent?: boolean;
  trend?: TrendData;
}

function ProgressBar({ 
  value, 
  max, 
  color, 
  label, 
  count, 
  delay = 0,
  size = 'md',
  showPercent = true,
  trend
}: ProgressBarProps) {
  const percent = max > 0 ? (value / max) * 100 : 0;
  const heightClass = size === 'sm' ? 'h-1.5' : size === 'lg' ? 'h-4' : 'h-3';
  
  return (
    <div className="group">
      <div className="flex justify-between text-sm mb-1.5">
        <span className="font-medium text-foreground">{label}</span>
        <div className="flex items-center gap-2">
          {trend && <TrendBadge trend={trend} />}
          <span className="text-muted-foreground group-hover:text-foreground transition-colors">
            {formatNumber(count)}{showPercent && ` (${percent.toFixed(0)}%)`}
          </span>
        </div>
      </div>
      <div className={cn('progress-track', heightClass)}>
        <div 
          className={cn('h-full rounded-full progress-bar-animated', heightClass)}
          style={{ 
            backgroundColor: color,
            '--progress-width': `${percent}%`,
            '--progress-delay': `${delay}ms`
          } as React.CSSProperties}
        />
      </div>
    </div>
  );
}

// 统计数字卡片
interface StatBlockProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  progress?: {
    value: number;
    max: number;
    label?: string;
  };
  children?: React.ReactNode;
}

function StatBlock({ title, value, subtitle, icon, progress, children }: StatBlockProps) {
  return (
    <div className="glass-card rounded-2xl p-6 fade-in-up h-full flex flex-col">
      <div className="flex items-center gap-2 text-muted-foreground mb-1">
        {icon}
        <span className="text-sm font-medium">{title}</span>
      </div>
      <div className="text-4xl font-bold text-foreground mt-2">{value}</div>
      {subtitle && <div className="text-sm text-muted-foreground mt-1">{subtitle}</div>}
      {progress && (
        <div className="mt-6">
          <div className="text-sm text-muted-foreground mb-2">{progress.label || '覆盖率'}</div>
          <div className="progress-track h-2">
            <div 
              className="h-full rounded-full progress-bar-animated bg-primary"
              style={{ 
                '--progress-width': `${progress.max > 0 ? (progress.value / progress.max) * 100 : 0}%`
              } as React.CSSProperties}
            />
          </div>
          <div className="flex justify-between text-xs text-muted-foreground mt-2">
            <span>已完成</span>
            <span className="text-foreground font-medium">
              {formatPercent(progress.max > 0 ? progress.value / progress.max : 0)}
            </span>
          </div>
        </div>
      )}
      {children && <div className="mt-auto pt-6">{children}</div>}
    </div>
  );
}

// 策略热力卡片
interface StrategyCardProps {
  title: string;
  icon: React.ElementType;
  iconColor: string;
  items: Array<{
    label: string;
    value: number;
    color: string;
  }>;
  maxValue: number;
  description?: string;
}

function StrategyCard({ title, icon: Icon, iconColor, items, maxValue, description }: StrategyCardProps) {
  return (
    <div className="bg-card/50 rounded-2xl p-5 border border-border relative overflow-hidden group hover:border-primary/30 transition-colors">
      <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
        <div className={cn('text-6xl', iconColor)}>
            <Icon className="w-12 h-12" />
        </div>
      </div>
      <div className="relative z-10">
        <h4 className={cn('text-lg font-semibold mb-4', iconColor)}>{title}</h4>
        <div className="space-y-3">
          {items.map((item, idx) => (
            <div key={item.label}>
              <div className="flex justify-between text-sm items-center">
                <span className="text-foreground/80">{item.label}</span>
                {idx === 0 && item.value > 0 && (
                  <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded">
                    High Activity
                  </span>
                )}
              </div>
              <div className="progress-track h-1.5 mt-1">
                <div 
                  className="h-full rounded-full progress-bar-animated"
                  style={{ 
                    backgroundColor: item.color,
                    '--progress-width': `${maxValue > 0 ? (item.value / maxValue) * 100 : 0}%`,
                    '--progress-delay': `${idx * 100}ms`
                  } as React.CSSProperties}
                />
              </div>
            </div>
          ))}
        </div>
        {description && (
          <p className="text-xs text-muted-foreground mt-3 line-clamp-2">{description}</p>
        )}
      </div>
    </div>
  );
}

export function DashboardPage() {
  // 主题
  const { effectiveTheme } = useTheme();
  const isDark = effectiveTheme === 'dark';
  const chartColors = getChartThemeColors(isDark);

  // 全局筛选器状态
  const [selectedYear, setSelectedYear] = useState('');
  
  // 产品热度排行榜独立的厂商筛选
  const [productVendorFilter, setProductVendorFilter] = useState('');

  // 获取可用年份（动态查询）
  const { data: yearsData } = useAvailableYears();
  const availableYears = yearsData?.data || [];

  // 计算日期范围
  const dateRange = useMemo(() => {
    if (!selectedYear) return {};
    return {
      date_from: `${selectedYear}-01-01`,
      date_to: `${selectedYear}-12-31`,
    };
  }, [selectedYear]);

  // 获取统计概览
  const { data: overviewData, isLoading: overviewLoading } = useStatsOverview();

  // 获取厂商统计（应用日期筛选 + 选择年份时包含趋势数据）
  const { data: vendorData, isLoading: vendorLoading } = useVendorStats({
    ...dateRange,
    include_trend: !!selectedYear  // 只有选择了具体年份才显示趋势
  });

  // 获取产品热度排行（使用独立的厂商筛选 + 全局日期筛选 + 选择年份时包含趋势）
  const { data: productHotnessData, isLoading: productLoading } = useProductHotness({
    vendor: productVendorFilter || undefined,
    limit: 10,
    ...dateRange,
    include_trend: !!selectedYear  // 只有选择了具体年份才显示趋势
  });

  // 获取厂商更新类型矩阵（应用日期筛选）
  const { data: vendorTypeData, isLoading: vendorTypeLoading } = useVendorTypeMatrix(dateRange);

  // 厂商数据处理
  const vendors = vendorData?.data || [];
  const totalUpdates = vendors.reduce((sum, v) => sum + v.count, 0);
  
  // 按更新数量排序的厂商列表
  const sortedVendors = useMemo(() => {
    return [...vendors].sort((a, b) => b.count - a.count);
  }, [vendors]);

  // 主要厂商（前3）和次要厂商
  const majorVendors = sortedVendors.slice(0, 3);
  const minorVendors = sortedVendors.slice(3, 6);

  // 产品热度数据
  const productHotness = productHotnessData?.data || [];
  const maxProductCount: number = productHotness.length > 0 ? productHotness[0].count : 0;

  // 更新类型统计聚合
  const typeStats = useMemo(() => {
    const matrix = vendorTypeData?.data || [];
    const aggregated: Record<string, { total: number; byVendor: Record<string, number> }> = {};
    
    matrix.forEach((vendor) => {
      Object.entries(vendor.update_types).forEach(([type, count]) => {
        if (!aggregated[type]) {
          aggregated[type] = { total: 0, byVendor: {} };
        }
        aggregated[type].total += count;
        aggregated[type].byVendor[vendor.vendor] = count;
      });
    });
    
    return Object.entries(aggregated)
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, 6);
  }, [vendorTypeData]);



  // 初始加载状态（仅在首次加载无数据时显示全局Loading）
  const isInitialLoading = overviewLoading && !overviewData;
  if (isInitialLoading) {
    return <Loading message="加载仪表盘数据..." />;
  }

  const overview = overviewData?.data;

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <PageHeader
        title="竞争分析大盘"
        eyebrow="DASHBOARD // OVERVIEW"
        description={
            <span className="flex items-center gap-2">
                <span>Last updated: {overview?.last_crawl_time 
                ? format(new Date(overview.last_crawl_time), 'MM-dd HH:mm')
                : 'N/A'}</span>
            </span>
        }
      />

      {/* 主统计区 */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* 左侧：总数统计 + 全局筛选器 */}
        <div className="md:col-span-4">
          <StatBlock
            title="全网监测更新数"
            value={formatNumber(totalUpdates)}
            icon={<Layers className="h-4 w-4" />}
            progress={{
              value: Math.round((overview?.analysis_coverage || 0) * (overview?.total_updates || 0)),
              max: overview?.total_updates || 0,
              label: 'AI 分析覆盖率'
            }}
          >
            {/* 年份筛选按钮 */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Calendar className="h-3 w-3" />
                <span>年份筛选</span>
              </div>
              <div className="flex flex-wrap gap-2 justify-center">
                <button
                  onClick={() => setSelectedYear('')}
                  className={cn(
                    'px-3 py-1.5 text-xs rounded-lg border transition-colors',
                    selectedYear === ''
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'border-border text-muted-foreground hover:text-foreground hover:border-primary/50'
                  )}
                >
                  全部
                </button>
                {availableYears.map((year) => (
                  <button
                    key={year}
                    onClick={() => setSelectedYear(year === Number(selectedYear) ? '' : String(year))}
                    className={cn(
                      'px-3 py-1.5 text-xs rounded-lg border transition-colors',
                      String(year) === selectedYear
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'border-border text-muted-foreground hover:text-foreground hover:border-primary/50'
                    )}
                  >
                    {year}
                  </button>
                ))}
              </div>
            </div>
          </StatBlock>
        </div>

        {/* 右侧：厂商活跃度份额 */}
        <div className="md:col-span-8 glass-card rounded-2xl p-6 fade-in-up-delay-1">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-xl font-bold text-foreground">厂商活跃度份额</h3>
            <span className="text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded">
              {selectedYear ? `${selectedYear} 年` : '累计数据'}
            </span>
          </div>
          
          {vendorLoading ? (
            <div className="h-[200px] flex items-center justify-center">
              <Loading />
            </div>
          ) : (
            <>
              {/* 主要厂商 */}
              <div className="space-y-4">
                {majorVendors.map((vendor, idx) => (
                  <ProgressBar
                    key={vendor.vendor}
                    label={VENDOR_DISPLAY_NAMES[vendor.vendor] || vendor.vendor}
                    value={vendor.count}
                    max={totalUpdates}
                    count={vendor.count}
                    color={getVendorColor(vendor.vendor)}
                    delay={idx * 100}
                    size="md"
                    trend={vendor.trend}
                  />
                ))}
              </div>
              
              {/* 次要厂商 - 一行显示 */}
              {minorVendors.length > 0 && (
                <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-border">
                  {minorVendors.map((vendor, idx) => (
                    <ProgressBar
                      key={vendor.vendor}
                      label={VENDOR_DISPLAY_NAMES[vendor.vendor] || vendor.vendor}
                      value={vendor.count}
                      max={totalUpdates}
                      count={vendor.count}
                      color={getVendorColor(vendor.vendor)}
                      delay={300 + idx * 100}
                      size="sm"
                      trend={vendor.trend}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* 产品热度排行 */}
      <div className="glass-card rounded-2xl p-6 fade-in-up-delay-2">
        <div className="flex flex-col md:flex-row justify-between md:items-start mb-6 gap-4">
          <div>
            <h3 className="text-xl font-bold text-foreground">产品热度排行榜</h3>
            <p className="text-sm text-muted-foreground mt-1">
              按更新数量排名，反映各产品领域的活跃程度
            </p>
          </div>
          {/* 厂商快捷筛选按钮 */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setProductVendorFilter('')}
              className={cn(
                'px-3 py-1 text-xs rounded-full border transition-colors',
                productVendorFilter === ''
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'border-border text-muted-foreground hover:text-foreground hover:border-primary/50'
              )}
            >
              全部
            </button>
            {sortedVendors.slice(0, 6).map((v) => (
              <button
                key={v.vendor}
                onClick={() => setProductVendorFilter(v.vendor === productVendorFilter ? '' : v.vendor)}
                className={cn(
                  'px-3 py-1 text-xs rounded-full border transition-colors',
                  productVendorFilter === v.vendor
                    ? 'text-white border-transparent'
                    : 'border-border text-muted-foreground hover:text-foreground'
                )}
                style={productVendorFilter === v.vendor ? { backgroundColor: getVendorColor(v.vendor) } : undefined}
              >
                {VENDOR_DISPLAY_NAMES[v.vendor] || v.vendor}
              </button>
            ))}
          </div>
        </div>

        {productLoading ? (
          <div className="h-[200px] flex items-center justify-center">
            <Loading />
          </div>
        ) : productHotness.length === 0 ? (
          <div className="h-[200px] flex items-center justify-center text-muted-foreground">
            暂无数据
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {productHotness.map((item, idx) => (
              <ProgressBar
                key={item.product_subcategory}
                label={item.product_subcategory}
                value={item.count}
                max={maxProductCount}
                count={item.count}
                color={productVendorFilter ? getVendorColor(productVendorFilter) : chartColors.primary}
                delay={idx * 50}
                size="sm"
                showPercent={false}
                trend={item.trend}
              />
            ))}
          </div>
        )}
      </div>

      {/* 更新类型战略分布 */}
      <div className="glass-card rounded-2xl p-6 fade-in-up-delay-3">
        <div className="flex flex-col md:flex-row justify-between md:items-center mb-8 gap-4">
          <div>
            <h3 className="text-xl font-bold text-foreground">更新类型战略分布</h3>
            <p className="text-sm text-muted-foreground mt-1">
              基于更新内容的语义分析，识别各类型的更新热度
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">按更新数量排序</span>
          </div>
        </div>

        {vendorTypeLoading ? (
          <div className="h-[200px] flex items-center justify-center">
            <Loading />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {typeStats.map(([type, data]) => {
              // 获取该类型下前2个厂商
              const topVendors = Object.entries(data.byVendor)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 2);
              
              // 获取类型配置
              const typeMeta = getUpdateTypeMeta(type);
              
              return (
                <StrategyCard
                  key={type}
                  title={UPDATE_TYPE_LABELS[type] || type}
                  icon={typeMeta.icon}
                  iconColor={typeMeta.colorClass}
                  maxValue={typeStats[0]?.[1].total || 100}
                  items={topVendors.map(([vendor, count]) => ({
                    label: VENDOR_DISPLAY_NAMES[vendor] || vendor,
                    value: count,
                    color: getVendorColor(vendor),
                  }))}
                  description={`共 ${formatNumber(data.total)} 次更新`}
                />
              );
            })}
          </div>
        )}
      </div>

      {/* 厂商统计详情 */}
      <Card className="fade-in-up-delay-3">
        <CardHeader>
          <CardTitle>厂商统计详情</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-3 px-4 text-left font-medium text-muted-foreground">厂商</th>
                  <th className="py-3 px-4 text-right font-medium text-muted-foreground">更新总数</th>
                  <th className="py-3 px-4 text-right font-medium text-muted-foreground">已分析</th>
                  <th className="py-3 px-4 text-left font-medium text-muted-foreground w-1/3">占比</th>
                </tr>
              </thead>
              <tbody>
                {sortedVendors.map((vendor, vendorIdx) => (
                  <tr 
                    key={vendor.vendor} 
                    className="border-b border-border hover:bg-accent/50 transition-colors"
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: getVendorColor(vendor.vendor) }}
                        />
                        {VENDOR_DISPLAY_NAMES[vendor.vendor] || vendor.vendor}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right font-medium">{formatNumber(vendor.count)}</td>
                    <td className="py-3 px-4 text-right">{formatNumber(vendor.analyzed)}</td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 progress-track h-2">
                          <div 
                            className="h-full rounded-full progress-bar-animated"
                            style={{ 
                              backgroundColor: getVendorColor(vendor.vendor),
                              '--progress-width': `${totalUpdates > 0 ? (vendor.count / totalUpdates) * 100 : 0}%`,
                              '--progress-delay': `${vendorIdx * 50}ms`
                            } as React.CSSProperties}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground w-12 text-right">
                          {formatPercent(totalUpdates > 0 ? vendor.count / totalUpdates : 0)}
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}