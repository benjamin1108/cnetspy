/**
 * 竞争分析报告页面
 * 
 * 直接用前端组件渲染报告数据，样式与 HTML 报告一致
 */

import { useState, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAvailableMonths } from '@/hooks';
import { Select, Loading } from '@/components/ui';
import { reportsApi } from '@/api';
import { getVendorColor, cn } from '@/lib/utils';
import { UPDATE_TYPE_LABELS, SOURCE_CHANNEL_LABELS } from '@/types';

// 厂商显示名
const VENDOR_NAMES: Record<string, string> = {
  aws: 'AWS',
  gcp: 'GCP',
  azure: 'Azure',
  huawei: '华为云',
  tencentcloud: '腾讯云',
  volcengine: '火山引擎',
};

// 厂商 FontAwesome 图标
const VENDOR_ICONS: Record<string, string> = {
  aws: 'fab fa-aws',
  gcp: 'fab fa-google',
  azure: 'fab fa-microsoft',
  huawei: 'fas fa-cloud',
  tencentcloud: 'fas fa-cloud',
  volcengine: 'fas fa-cloud',
};

// 更新类型标签样式映射
function getTypeTagClass(updateType: string | null | undefined): string {
  if (!updateType) return 'timeline-type-default';
  
  const typeMap: Record<string, string> = {
    new_feature: 'timeline-type-feature',
    new_product: 'timeline-type-feature',
    enhancement: 'timeline-type-feature',
    pricing: 'timeline-type-pricing',
    security: 'timeline-type-security',
    compliance: 'timeline-type-security',
  };
  
  return typeMap[updateType] || 'timeline-type-default';
}

// 清理 markdown 标记，返回纯文本
function stripMarkdown(text: string | null | undefined): string {
  if (!text) return '';
  return text
    .replace(/\*\*([^*]+)\*\*/g, '$1')  // **bold**
    .replace(/\*([^*]+)\*/g, '$1')      // *italic*
    .replace(/__([^_]+)__/g, '$1')      // __bold__
    .replace(/_([^_]+)_/g, '$1')        // _italic_
    .replace(/`([^`]+)`/g, '$1')        // `code`
    .replace(/#{1,6}\s*/g, '')          // # headers
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')  // [link](url)
    .replace(/!\[([^\]]+)\]\([^)]+\)/g, '$1') // ![img](url)
    .replace(/^[\s]*[-*+]\s+/gm, '')    // list items
    .replace(/^\d+\.\s+/gm, '')         // numbered list
    .replace(/>/g, '')                  // blockquote
    .trim();
}



// 解析 AI 摘要 Markdown 为结构化数据
function parseAiSummary(markdown: string | undefined) {
  if (!markdown) return { title: '', summary: '', trends: [] };
  
  const lines = markdown.split('\n').filter(l => l.trim());
  let title = '';
  let summary = '';
  const trends: Array<{ emoji: string; title: string; desc: string }> = [];
  
  let inTrends = false;
  let currentTrend: { emoji: string; title: string; desc: string } | null = null;
  
  for (const line of lines) {
    // 标题 (## xxx)
    if (line.startsWith('## ') && !title) {
      title = line.replace('## ', '').trim();
      continue;
    }
    
    // 趋势标题 (### 本月趋势)
    if (line.startsWith('### ')) {
      inTrends = true;
      continue;
    }
    
    // 趋势项 (emoji **标题**: 描述)
    const trendMatch = line.match(/^([^\s]+)\s+\*\*([^*]+)\*\*[：:]\s*(.+)$/);
    if (trendMatch && inTrends) {
      if (currentTrend) trends.push(currentTrend);
      currentTrend = {
        emoji: trendMatch[1],
        title: trendMatch[2],
        desc: trendMatch[3],
      };
      continue;
    }
    
    // 普通段落
    if (!inTrends && !title) continue;
    if (!inTrends && title) {
      summary += (summary ? ' ' : '') + line.trim();
    } else if (currentTrend) {
      currentTrend.desc += ' ' + line.trim();
    }
  }
  
  if (currentTrend) trends.push(currentTrend);
  
  return { title, summary, trends };
}

export function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedVendor, setSelectedVendor] = useState<string>('all');
  
  const reportType = (searchParams.get('type') as 'weekly' | 'monthly') || 'monthly';
  const urlYear = searchParams.get('year') ? parseInt(searchParams.get('year')!) : undefined;
  const urlMonth = searchParams.get('month') ? parseInt(searchParams.get('month')!) : undefined;
  
  const { data: monthsData } = useAvailableMonths();
  const availableMonths = monthsData?.data || [];
  
  // 计算默认月份：优先使用有效报告列表的最新月份
  const getDefaultMonth = () => {
    if (urlYear && urlMonth) return { year: urlYear, month: urlMonth };
    
    // 如果有可用报告列表，使用最新的一个（列表第一个）
    if (availableMonths.length > 0) {
      const latest = availableMonths[0];
      return { year: latest.year, month: latest.month };
    }
    
    // 否则默认为当前月（截止今天）
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  };
  
  const { year, month } = getDefaultMonth();
  
  // 获取报告数据
  const { data: reportData, isLoading, error } = useQuery({
    queryKey: ['report', reportType, year, month],
    queryFn: () => reportsApi.getReport(reportType, { year, month }),
  });
  
  const report = reportData?.data;
  const topVendor = report?.vendor_summaries?.[0];
  
  // 解析 AI 摘要
  const aiInsight = useMemo(() => parseAiSummary(report?.ai_summary ?? undefined), [report?.ai_summary]);
  
  // 统计热点产品
  const hotProducts = useMemo(() => {
    if (!report?.updates_by_vendor) return [];
    const productCount: Record<string, number> = {};
    
    Object.values(report.updates_by_vendor).forEach((updates: any) => {
      updates.forEach((u: any) => {
        const cat = u.product_subcategory || '其他';
        productCount[cat] = (productCount[cat] || 0) + 1;
      });
    });
    
    return Object.entries(productCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([name, count]) => ({ name, count }));
  }, [report?.updates_by_vendor]);
  
  // 获取筛选后的更新列表
  const filteredUpdates = useMemo(() => {
    if (!report?.updates_by_vendor) return [];
    
    const allUpdates: Array<{ vendor: string; update: any }> = [];
    Object.entries(report.updates_by_vendor).forEach(([vendor, updates]) => {
      (updates as any[]).forEach(update => {
        allUpdates.push({ vendor, update });
      });
    });
    
    // 按日期排序
    allUpdates.sort((a, b) => 
      new Date(b.update.publish_date).getTime() - new Date(a.update.publish_date).getTime()
    );
    
    if (selectedVendor !== 'all') {
      return allUpdates.filter(item => item.vendor === selectedVendor);
    }
    
    return allUpdates;
  }, [report?.updates_by_vendor, selectedVendor]);
  
  // 切换月份
  const handleMonthChange = (value: string) => {
    const [y, m] = value.split('-');
    const params = new URLSearchParams(searchParams);
    params.set('year', y);
    params.set('month', m);
    setSearchParams(params);
    setSelectedVendor('all');
  };
  
  return (
    <div className="space-y-6 fade-in-up max-w-6xl mx-auto">
      {/* 页面头部 */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 pb-6 border-b border-border">
        <div>
          <p className="text-xs uppercase tracking-widest text-primary font-bold mb-2">
            Monthly Competitive Intelligence
          </p>
          <h1 className="text-3xl md:text-4xl font-bold text-foreground">
            {year}年{month.toString().padStart(2, '0')}月 · 云厂商竞争态势报告
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            统计周期：{report?.date_from || `${year}-${month.toString().padStart(2, '0')}-01`} 至 {report?.date_to || `${year}-${month.toString().padStart(2, '0')}-30`}
          </p>
        </div>
        
        <Select
          value={`${year}-${month}`}
          onChange={(e) => handleMonthChange(e.target.value)}
          className="w-36"
        >
          {availableMonths.length > 0 ? (
            availableMonths.map((m) => (
              <option key={`${m.year}-${m.month}`} value={`${m.year}-${m.month}`}>
                {m.label}
              </option>
            ))
          ) : (
            <option value={`${year}-${month}`}>
              {year}年{month.toString().padStart(2, '0')}月
            </option>
          )}
        </Select>
      </header>
      
      {isLoading ? (
        <div className="flex items-center justify-center h-64">
          <Loading />
        </div>
      ) : error || !report ? (
        <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-4">
          <p>{year}年{month}月的报告尚未生成</p>
        </div>
      ) : (
        <>
          {/* 统计摘要面板 */}
          <section className="timeline-card group rounded-xl p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* 左侧：更新总数 */}
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-primary/20 to-accent/20 flex items-center justify-center">
                  <i className="fas fa-chart-line text-3xl text-primary"></i>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground mb-1">本月更新</div>
                  <div className="text-3xl font-bold text-foreground">{report.total_count}</div>
                </div>
              </div>
              
              {/* 中间：最活跃厂商 */}
              <div className="flex items-center gap-4">
                {topVendor?.vendor && (
                  <div 
                    className="w-16 h-16 rounded-xl flex items-center justify-center text-white"
                    style={{ backgroundColor: getVendorColor(topVendor.vendor) }}
                  >
                    <i className={`${VENDOR_ICONS[topVendor.vendor] || 'fas fa-cloud'} text-3xl`}></i>
                  </div>
                )}
                <div>
                  <div className="text-xs text-muted-foreground mb-1">最活跃厂商</div>
                  <div className="text-lg font-bold text-foreground">
                    {topVendor?.vendor ? VENDOR_NAMES[topVendor.vendor] || topVendor.vendor : '-'}
                  </div>
                  <div className="text-xs text-muted-foreground">{topVendor?.count || 0} 条更新</div>
                </div>
              </div>
              
              {/* 右侧：热点领域 */}
              <div>
                <div className="text-xs text-muted-foreground mb-3">热点领域 TOP 3</div>
                <div className="space-y-2">
                  {hotProducts.slice(0, 3).map((p, i) => (
                    <div key={p.name} className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded flex items-center justify-center bg-primary/10 text-primary text-xs font-bold">
                        {i + 1}
                      </div>
                      <div className="flex-1 text-sm text-foreground truncate">{p.name}</div>
                      <div className="text-sm font-bold text-primary">{p.count}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
          
          {/* AI 分析师总结 */}
          {aiInsight.title && (
            <section className="timeline-card group rounded-xl p-5">
              <div className="text-xs font-bold uppercase tracking-widest text-primary mb-3 flex items-center gap-2">
                💡 分析师总结
              </div>
              
              <h3 className="font-bold text-base text-foreground mb-2">{aiInsight.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground mb-4">{aiInsight.summary}</p>
              
              {aiInsight.trends.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 border-t border-border/50 pt-4">
                  {aiInsight.trends.map((trend, i) => (
                    <div key={i} className="timeline-card group rounded-lg p-3 flex gap-3">
                      <span className="text-xl flex-shrink-0">{trend.emoji}</span>
                      <div>
                        <h4 className="font-medium text-sm mb-1 text-foreground group-hover:text-primary transition-colors">{trend.title}</h4>
                        <p className="text-xs leading-relaxed text-muted-foreground">{trend.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
          
          {/* 重点更新 */}
          <section>
            <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4 mb-6">
              <h2 className="text-xl font-bold flex items-center gap-2 text-foreground">
                <i className="fas fa-layer-group text-primary"></i>
                本月重点更新
              </h2>
              
              {/* 厂商筛选 */}
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => setSelectedVendor('all')}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                    selectedVendor === 'all'
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-card border-border text-muted-foreground hover:border-primary'
                  }`}
                >
                  全部
                </button>
                {report.vendor_summaries?.map((v: any) => (
                  <button
                    key={v.vendor}
                    onClick={() => setSelectedVendor(v.vendor)}
                    className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                      selectedVendor === v.vendor
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'bg-card border-border text-muted-foreground hover:border-primary'
                    }`}
                  >
                    {VENDOR_NAMES[v.vendor] || v.vendor}
                  </button>
                ))}
              </div>
            </div>
            
            {/* 更新卡片网格 - 与时间流样式一致 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredUpdates.map(({ vendor, update }) => {
                const vendorColor = getVendorColor(vendor);
                
                return (
                  <div key={update.update_id} className="timeline-card group">
                    {/* 厂商颜色条 */}
                    <div 
                      className="timeline-vendor-bar" 
                      style={{ backgroundColor: vendorColor }}
                    />
                    
                    {/* 使用 flex 布局：标题顶对齐，标签底对齐 */}
                    <div className="flex flex-col h-full pl-3">
                      {/* 顶部固定区域：厂商 + 日期 + 标题 */}
                      <div className="flex-shrink-0 space-y-2">
                        {/* 头部：厂商图标 + 日期 */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div 
                              className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white"
                              style={{ backgroundColor: vendorColor }}
                            >
                              {(VENDOR_NAMES[vendor] || vendor).charAt(0)}
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {VENDOR_NAMES[vendor] || vendor}
                            </span>
                          </div>
                          <span className="timeline-timestamp">
                            {update.publish_date?.slice(5, 10)}
                          </span>
                        </div>
                        
                        {/* 标题：固定2行高度 */}
                        <Link 
                          to={`/updates/${update.update_id}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-foreground group-hover:text-primary transition-colors line-clamp-2 block min-h-[2.5rem]"
                        >
                          {update.title}
                        </Link>
                      </div>
                      
                      {/* 中间弹性区域：摘要 */}
                      <div className="flex-1 py-2">
                        {update.content_summary && (
                          <p className="text-xs text-muted-foreground line-clamp-2 group-hover:text-muted-foreground/80">
                            {stripMarkdown(update.content_summary)}
                          </p>
                        )}
                      </div>
                      
                      {/* 底部固定区域：标签 */}
                      <div className="flex-shrink-0 flex flex-wrap items-center gap-2 pt-2 border-t border-border/30">
                        {/* 来源渠道 */}
                        {update.source_channel && (
                          <span className={cn(
                            'text-[10px] px-1.5 py-0.5 rounded font-medium',
                            update.source_channel === 'whatsnew' ? 'channel-whatsnew' : 'channel-blog'
                          )}>
                            {SOURCE_CHANNEL_LABELS[update.source_channel] || update.source_channel}
                          </span>
                        )}
                        
                        {/* 更新类型 */}
                        {update.update_type && (
                          <span className={cn('timeline-type-tag', getTypeTagClass(update.update_type))}>
                            {UPDATE_TYPE_LABELS[update.update_type] || update.update_type}
                          </span>
                        )}
                        
                        {/* 产品子类 */}
                        {update.product_subcategory && (
                          <span className="text-xs text-muted-foreground/70">
                            {update.product_subcategory}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

          </section>
          
          {/* 页脚 */}
          <footer className="text-center py-8 border-t border-border">
            <p className="text-xs text-muted-foreground">
              Generated by CloudNetSpy Engine · <a href="https://cnetspy.site" target="_blank" rel="noopener noreferrer" className="hover:text-primary transition-colors">cnetspy.site</a>
            </p>
          </footer>
        </>
      )}
    </div>
  );
}
