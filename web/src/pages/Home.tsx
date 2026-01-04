/**
 * 首页 - 时间流情报更新
 */

import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useInfiniteUpdates, useStatsOverview, useVendors } from '@/hooks';
import { Loading, EmptyState, Button } from '@/components/ui';
import { PageHeader } from '@/components/ui/PageHeader';
import { getUpdateTypeMeta } from '@/components/icons';
import { getVendorColor, cn } from '@/lib/utils';
import {
  VENDOR_DISPLAY_NAMES,
  UPDATE_TYPE_LABELS,
  SOURCE_CHANNEL_LABELS,
} from '@/types';
import type { UpdateBrief } from '@/types';
import { Radar, ChevronRight, Loader2 } from 'lucide-react';
import { format, isToday, isYesterday, parseISO } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { SEO } from '@/components/SEO';

// 格式化日期分组标签
function formatDateGroup(dateStr: string): string {
  try {
    const date = parseISO(dateStr);
    if (isToday(date)) return '今天';
    if (isYesterday(date)) return '昨天';
    return format(date, 'M月d日 EEEE', { locale: zhCN });
  } catch {
    return dateStr;
  }
}

// 时间流卡片组件
function TimelineCard({ update }: { update: UpdateBrief }) {
  const vendorColor = getVendorColor(update.vendor);
  const typeMeta = getUpdateTypeMeta(update.update_type);
  const TypeIcon = typeMeta.icon;
  
  return (
    <div className="timeline-card group">
      {/* 厂商颜色条 */}
      <div 
        className="timeline-vendor-bar" 
        style={{ backgroundColor: vendorColor }}
      />
      
      <div className="flex flex-col sm:flex-row sm:items-start gap-3 pl-3">
        {/* 类型图标区 */}
        <div className="flex-shrink-0 mt-1">
          <div 
            className={cn("w-9 h-9 rounded-xl flex items-center justify-center bg-card border border-border/50 shadow-sm transition-all group-hover:scale-110 group-hover:border-primary/30", typeMeta.colorClass)}
          >
            <TypeIcon className="w-5 h-5" />
          </div>
        </div>
        
        {/* 内容区 */}
        <div className="flex-1 min-w-0">
          {/* 标题行 */}
          <div className="flex justify-between items-start gap-2">
            <Link 
              to={`/updates/${update.update_id}`}
              className="text-base font-bold text-foreground group-hover:text-primary transition-colors line-clamp-2 flex-1"
            >
              {update.title_translated || update.title}
            </Link>
            <span className="font-mono text-[10px] font-bold text-primary/30 tracking-widest uppercase mt-1">
              {update.source_channel === 'whatsnew' ? 'WHATSNEW' : 'TECH BLOG'}
            </span>
          </div>
          
          {/* 描述 */}
          {(update.content_summary || update.description) && (
            <p className="text-sm text-muted-foreground mt-1.5 line-clamp-2 group-hover:text-muted-foreground/80 leading-relaxed">
              {update.content_summary || update.description}
            </p>
          )}
          
          {/* 标签行 */}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {/* 厂商名称 */}
            <span 
              className="text-[10px] px-2 py-0.5 rounded font-medium border border-border/50 bg-muted/30"
              style={{ color: vendorColor, borderColor: `${vendorColor}20` }}
            >
              {VENDOR_DISPLAY_NAMES[update.vendor] || update.vendor}
            </span>

            {/* 更新类型 */}
            {update.update_type && (
              <span className={cn('text-[10px] px-2 py-0.5 rounded font-medium', typeMeta.bgClass, typeMeta.borderClass, typeMeta.colorClass)}>
                {UPDATE_TYPE_LABELS[update.update_type] || update.update_type}
              </span>
            )}
            
            {/* 来源渠道 */}
            <span className={cn(
              'text-[10px] px-2 py-0.5 rounded font-medium opacity-80',
              update.source_channel === 'whatsnew' ? 'channel-whatsnew' : 'channel-blog'
            )}>
              {SOURCE_CHANNEL_LABELS[update.source_channel] || update.source_channel}
            </span>
            
            {/* 产品子类 */}
            {update.product_subcategory && (
              <span className="text-xs text-muted-foreground/70 flex items-center gap-1">
                <span className="w-1 h-1 rounded-full bg-muted-foreground/50" />
                {update.product_subcategory}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// 今日摘要面板
function DailyBrief({ updates, stats }: { updates: UpdateBrief[]; stats?: { total_updates?: number } }) {
  // 统计各类型数量
  const typeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    updates.forEach(u => {
      if (u.update_type) {
        counts[u.update_type] = (counts[u.update_type] || 0) + 1;
      }
    });
    return counts;
  }, [updates]);
  
  const featureCount = (typeCounts['new_feature'] || 0) + (typeCounts['new_product'] || 0) + (typeCounts['enhancement'] || 0);
  const regionCount = typeCounts['region'] || 0;
  const pricingCount = typeCounts['pricing'] || 0;
  
  return (
    <div className="daily-brief-panel fade-in-up">
      <div className="flex items-start gap-4">
        <div className="flex-1">
          <h2 className="text-sm font-bold text-primary uppercase tracking-wider mb-2 flex items-center gap-2">
            <Radar className="h-4 w-4" />
            今日动态
          </h2>
          <p className="text-muted-foreground text-sm leading-relaxed">
            今日监测到 <span className="text-foreground font-bold">{updates.length}</span> 条更新
            {stats?.total_updates && (
              <>，累计收录 <span className="text-foreground font-medium">{stats.total_updates.toLocaleString()}</span> 条</>
            )}
          </p>
        </div>
        <div className="hidden md:flex gap-4 text-center">
          {featureCount > 0 && (
            <div>
              <div className="text-xl font-bold text-foreground">{featureCount}</div>
              <div className="text-[10px] text-muted-foreground uppercase">Feature</div>
            </div>
          )}
          {regionCount > 0 && (
            <div>
              <div className="text-xl font-bold text-foreground">{regionCount}</div>
              <div className="text-[10px] text-muted-foreground uppercase">Region</div>
            </div>
          )}
          {pricingCount > 0 && (
            <div>
              <div className="text-xl font-bold text-foreground">{pricingCount}</div>
              <div className="text-[10px] text-muted-foreground uppercase">Price</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function HomePage() {
  // 厂商筛选状态
  const [selectedVendor, setSelectedVendor] = useState<string>('');
  
  // 获取厂商列表
  const { data: vendorsData } = useVendors();
  const vendors = vendorsData?.data || [];
  
  // 获取最新更新（支持厂商筛选）
  const { 
    data, 
    isLoading, 
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteUpdates({ 
    page_size: 30, 
    sort_by: 'publish_date', 
    order: 'desc',
    vendor: selectedVendor || undefined,
  });
  
  // 获取统计概览
  const { data: statsData } = useStatsOverview();
  
  // 合并所有页面的数据
  const updates = useMemo(() => {
    if (!data?.pages) return [];
    return data.pages.flatMap(page => page.data?.items || []);
  }, [data]);
  
  // 按日期分组
  const groupedUpdates = useMemo(() => {
    const groups: Record<string, UpdateBrief[]> = {};
    
    updates.forEach(update => {
      const dateKey = update.publish_date.split('T')[0];
      if (!groups[dateKey]) {
        groups[dateKey] = [];
      }
      groups[dateKey].push(update);
    });
    
    // 按日期倒序排列
    return Object.entries(groups).sort((a, b) => b[0].localeCompare(a[0]));
  }, [updates]);
  
  // 今日更新
  const todayUpdates = useMemo(() => {
    const today = format(new Date(), 'yyyy-MM-dd');
    return updates.filter(u => u.publish_date.startsWith(today));
  }, [updates]);

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

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <SEO 
        title="首页" 
        description="CloudNetSpy 实时监控 AWS, Azure, GCP 等云厂商的网络产品更新，提供深度对比分析和竞争情报。" 
        type="website"
      />
      {/* 页面头部 */}
      <PageHeader
        title="更新时间线"
        eyebrow="LIVE FEED // UPDATES"
        description={
          <span className="flex items-center gap-2">
            <span>{format(new Date(), 'yyyy-MM-dd')}</span>
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-emerald-500 text-xs font-medium">Monitoring Active</span>
          </span>
        }
      >
        {/* 全部按钮 */}
        <button
          onClick={() => setSelectedVendor('')}
          className={cn(
            'px-3 py-1.5 text-xs border rounded transition font-medium',
            selectedVendor === ''
              ? 'bg-primary text-primary-foreground border-primary shadow-sm'
              : 'bg-card text-muted-foreground border-border hover:text-foreground hover:border-primary/50'
          )}
        >
          全部
        </button>
        {/* 厂商筛选按钮 */}
        {vendors.slice(0, 6).map((v) => (
          <button
            key={v.vendor}
            onClick={() => setSelectedVendor(v.vendor === selectedVendor ? '' : v.vendor)}
            className={cn(
              'px-3 py-1.5 text-xs border rounded transition font-medium',
              selectedVendor === v.vendor
                ? 'text-white border-transparent shadow-sm'
                : 'bg-card text-muted-foreground border-border hover:text-foreground hover:border-primary/50'
            )}
            style={selectedVendor === v.vendor ? { backgroundColor: getVendorColor(v.vendor) } : undefined}
          >
            {VENDOR_DISPLAY_NAMES[v.vendor] || v.vendor}
          </button>
        ))}
      </PageHeader>

      {/* 今日摘要 */}
      {!isLoading && todayUpdates.length > 0 && (
        <DailyBrief updates={todayUpdates} stats={statsData?.data ?? undefined} />
      )}

      {/* 时间流主体 */}
      {isLoading ? (
        <Loading message="加载更新流..." />
      ) : updates.length === 0 ? (
        <EmptyState
          title="暂无更新"
          description="暂时没有任何更新记录"
        />
      ) : (
        <div className="timeline-container pl-2">
          {groupedUpdates.map(([dateKey, dateUpdates], groupIdx) => (
            <div key={dateKey} className={cn('mb-8 relative', groupIdx > 0 && 'opacity-90 hover:opacity-100 transition-opacity')}>
              {/* 日期标签 */}
              <div className="timeline-date-label sticky top-20 z-10 backdrop-blur-sm bg-background/80 py-1 mb-4 inline-block px-3 rounded-full border border-border/50 text-xs font-mono text-primary shadow-sm">
                {formatDateGroup(dateKey)}
              </div>
              
              {/* 该日期的更新列表 */}
              <div className="space-y-4">
                {dateUpdates.map((update) => (
                  <TimelineCard key={update.update_id} update={update} />
                ))}
              </div>
            </div>
          ))}
          
          {/* 加载更多 */}
          <div className="text-center py-8">
            {isFetchingNextPage ? (
              <div className="flex items-center justify-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                加载中...
              </div>
            ) : hasNextPage ? (
              <button 
                onClick={() => fetchNextPage()}
                className="text-sm text-muted-foreground hover:text-primary transition flex items-center justify-center gap-2 w-full py-4 hover:bg-muted/30 rounded-lg"
              >
                <ChevronRight className="h-4 w-4 rotate-90" />
                加载更多历史更新
              </button>
            ) : (
              <span className="text-sm text-muted-foreground/70">已加载全部记录</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}