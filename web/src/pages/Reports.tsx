/**
 * 竞争分析报告页面
 *
 * 使用 Recharts 高度定制，模仿 Tremor/SaaS 现代极简风格
 */

import { useState, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer
} from 'recharts';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { useAvailableMonths } from '@/hooks';
import { Select, Loading } from '@/components/ui';
import { PageHeader } from '@/components/ui/PageHeader';
import { reportsApi } from '@/api';
import { getVendorColor, getVendorName, cn } from '@/lib/utils';
import { getUpdateTypeMeta } from '@/components/icons';
import { UPDATE_TYPE_LABELS, SOURCE_CHANNEL_LABELS } from '@/types';

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

// 格式化日期范围
function formatDateRange(from?: string, to?: string) {
    if (!from || !to) return '';
    return `${from} 至 ${to}`;
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
    .replace(/!\[([^\]]+)\]\([^)]+\)/g, '$1')  // [link](url)
    .replace(/!\[([^\]]+)\]\([^)]+\)/g, '$1') // ![img](url)
    .replace(/^[\s]*[-*+]\s+/gm, '')    // list items
    .replace(/^\d+\.\s+/gm, '')         // numbered list
    .replace(/>/g, '')                  // blockquote
    .trim();
}

export function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedVendor, setSelectedVendor] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');

  const reportType = (searchParams.get('type') as 'weekly' | 'monthly') || 'monthly';
  const urlYear = searchParams.get('year') ? parseInt(searchParams.get('year')!) : undefined;
  const urlMonth = searchParams.get('month') ? parseInt(searchParams.get('month')!) : undefined;

  const { data: monthsData } = useAvailableMonths();
  const availableMonths = monthsData?.data || [];

  const getDefaultMonth = () => {
    if (urlYear && urlMonth) return { year: urlYear, month: urlMonth };
    if (availableMonths.length > 0) {
      const latest = availableMonths[0];
      return { year: latest.year, month: latest.month };
    }
    const now = new Date();
    return { year: now.getFullYear(), month: now.getMonth() + 1 };
  };

  const { year, month } = getDefaultMonth();

  const { data: reportData, isLoading, error } = useQuery({
    queryKey: ['report', reportType, year, month],
    queryFn: () => reportsApi.getReport(reportType, { year, month }),
  });

  const report = reportData?.data;

  // 1. 数据解析：AI 洞察 (仅支持结构化 JSON，带降级处理)
  const aiInsight = useMemo(() => {
    const raw = report?.ai_summary;
    if (!raw) return { insight_title: '', insight_summary: '', top_trends: [] };

    if (typeof raw === 'object') {
      return raw as any;
    }

    // 如果是字符串，尝试解析 JSON
    if (typeof raw === 'string') {
      try {
        return JSON.parse(raw);
      } catch {
        // 解析失败，说明是纯 Markdown 文本，降级处理，不报错
        return {
          insight_title: '本月摘要',
          insight_summary: raw,
          top_trends: []
        };
      }
    }
    return { insight_title: '', insight_summary: '', top_trends: [] };
  }, [report?.ai_summary]);

  // 2. 数据统计：厂商分布（饼图数据）
  const vendorPieData = useMemo(() => {
    if (!report?.vendor_summaries) return [];
    return report.vendor_summaries
      .filter(v => v.count > 0)
      .map(v => ({
        name: getVendorName(v.vendor),
        value: v.count,
        color: getVendorColor(v.vendor),
      }))
      .sort((a, b) => b.value - a.value);
  }, [report?.vendor_summaries]);

  // 3. 数据统计：热门领域（柱状图数据）
  const categoryBarData = useMemo(() => {
    if (!report?.updates_by_vendor) return [];

    // 统计每个领域的总数以及各厂商的贡献数
    const categoryStats: Record<string, { total: number; vendors: Record<string, number> }> = {};

    Object.entries(report.updates_by_vendor).forEach(([vendor, updates]) => {
      (updates as any[]).forEach((u: any) => {
        const cat = u.product_subcategory || '其他';
        if (!categoryStats[cat]) {
          categoryStats[cat] = { total: 0, vendors: {} };
        }
        categoryStats[cat].total += 1;
        categoryStats[cat].vendors[vendor] = (categoryStats[cat].vendors[vendor] || 0) + 1;
      });
    });

    return Object.entries(categoryStats)
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, 5) // 取 Top 5
      .map(([name, stats]) => {
        // 找出该领域贡献最大的厂商（Dominant Vendor）
        let dominantVendor = 'unknown';
        let maxCount = -1;

        Object.entries(stats.vendors).forEach(([v, count]) => {
          if (count > maxCount) {
            maxCount = count;
            dominantVendor = v;
          }
        });

        // 格式化名称：厂商 - 类别
        const displayName = dominantVendor !== 'unknown'
          ? `${getVendorName(dominantVendor)} - ${name}`
          : name;

        return {
          name: displayName,
          count: stats.total,
          color: getVendorColor(dominantVendor) // 使用主导厂商的颜色
        };
      });
  }, [report?.updates_by_vendor]);

  // 4. 数据筛选：更新列表
  const filteredUpdates = useMemo(() => {
    if (!report?.updates_by_vendor) return [];

    let allUpdates: Array<{ vendor: string; update: any }> = [];
    Object.entries(report.updates_by_vendor).forEach(([vendor, updates]) => {
      (updates as any[]).forEach(update => {
        allUpdates.push({ vendor, update });
      });
    });

    // 过滤厂商
    if (selectedVendor !== 'all') {
      allUpdates = allUpdates.filter(item => item.vendor === selectedVendor);
    }

    // 过滤类型
    if (selectedType !== 'all') {
      allUpdates = allUpdates.filter(item => item.update.update_type === selectedType);
    }

    // 排序：Hero (重点) > 日期
    const heroTypes = ['new_product', 'pricing', 'compliance'];

    allUpdates.sort((a, b) => {
      const isHeroA = heroTypes.includes(a.update.update_type);
      const isHeroB = heroTypes.includes(b.update.update_type);

      if (isHeroA && !isHeroB) return -1;
      if (!isHeroA && isHeroB) return 1;

      return new Date(b.update.publish_date).getTime() - new Date(a.update.publish_date).getTime();
    });

    return allUpdates;
  }, [report?.updates_by_vendor, selectedVendor, selectedType]);

  const handleMonthChange = (value: string) => {
    const [y, m] = value.split('-');
    const params = new URLSearchParams(searchParams);
    params.set('year', y);
    params.set('month', m);
    setSearchParams(params);
    setSelectedVendor('all');
    setSelectedType('all');
  };

  const typeOptions = useMemo(() => {
    const types = new Set<string>();
    if (report?.updates_by_vendor) {
      Object.values(report.updates_by_vendor).forEach((updates: any) => {
        updates.forEach((u: any) => {
          if (u.update_type) types.add(u.update_type);
        });
      });
    }
    return Array.from(types).map(t => ({ value: t, label: UPDATE_TYPE_LABELS[t] || t }));
  }, [report]);

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      <PageHeader
        title="月度竞争情报"
        eyebrow="INTELLIGENCE // REPORT"
        description={
            <span className="flex items-center gap-2">
                <span>{year}年{month.toString().padStart(2, '0')}月</span>
                <span className="opacity-50">|</span>
                <span>统计周期：{report ? formatDateRange(report.date_from, report.date_to) : '...'}</span>
            </span>
        }
      >
        <Select
          value={`${year}-${month}`}
          onChange={(e) => handleMonthChange(e.target.value)}
          className="w-40"
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
      </PageHeader>

      {isLoading ? (
        <div className="flex items-center justify-center h-64"><Loading /></div>
      ) : error || !report ? (
        <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-4">
          <p>{year}年{month}月的报告尚未生成</p>
        </div>
      ) : (
        <>
          {/* 第一层：核心指标 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="timeline-card p-4 flex flex-col justify-between">
              <div className="text-muted-foreground text-xs font-medium uppercase tracking-wider">更新总数</div>
              <div className="text-3xl font-bold text-foreground mt-1">{report.total_count}</div>
              <div className="text-xs text-muted-foreground mt-1">本月监测更新总数</div>
            </div>

            <div className="timeline-card p-4 flex flex-col justify-between">
              <div className="text-muted-foreground text-xs font-medium uppercase tracking-wider">最活跃厂商</div>
              <div className="text-xl font-bold text-foreground mt-1 truncate">
                {vendorPieData[0]?.name || '-'}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {vendorPieData[0]?.value || 0} 条更新 · 占比 {report.total_count > 0 ? Math.round((vendorPieData[0]?.value || 0) / report.total_count * 100) : 0}%
              </div>
            </div>

            <div className="timeline-card p-4 flex flex-col justify-between">
              <div className="text-muted-foreground text-xs font-medium uppercase tracking-wider">热门领域 Top 1</div>
              <div className="text-xl font-bold text-foreground mt-1 truncate">
                {categoryBarData[0]?.name || '-'}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {categoryBarData[0]?.count || 0} 条更新
              </div>
            </div>
          </div>

          {/* 第二层：统计图表 (Modern Recharts Style) */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
             {/* 环形图 (模仿 DonutChart) */}
             <div className="timeline-card p-4 h-[300px] flex flex-col">
                <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">厂商分布</div>
                <div className="flex-1 w-full min-h-0 relative">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={vendorPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={4}
                        dataKey="value"
                        stroke="none"
                        cornerRadius={4}
                      >
                        {vendorPieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <RechartsTooltip
                        contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '8px', color: 'hsl(var(--foreground))', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                        itemStyle={{ color: 'hsl(var(--foreground))', fontSize: '12px', fontWeight: 600 }}
                        formatter={(value: any) => [`${value} 条`, '更新数量']}
                        cursor={false}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                  {/* 中心文字：总数 */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                    <span className="text-2xl font-bold text-foreground">{report.total_count}</span>
                    <span className="text-[10px] text-muted-foreground uppercase tracking-wide">Total</span>
                  </div>
                </div>
                {/* 底部图例 */}
                <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 mt-2">
                    {vendorPieData.slice(0, 5).map(v => (
                        <div key={v.name} className="flex items-center gap-1.5">
                            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: v.color }}></span>
                            <span className="text-xs text-muted-foreground">{v.name}</span>
                        </div>
                    ))}
                </div>
              </div>

              {/* 极简条形图 (模仿 BarList) */}
              <div className="timeline-card p-4 h-[300px] flex flex-col">
                <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-4">热门更新领域 Top 5</div>
                <div className="flex-1 flex flex-col justify-center gap-3">
                    {categoryBarData.map((item) => {
                        // 计算百分比作为宽度
                        const max = Math.max(...categoryBarData.map(d => d.count));
                        const percent = max > 0 ? (item.count / max) * 100 : 0;

                        return (
                            <div key={item.name} className="w-full">
                                <div className="flex justify-between items-center mb-1 text-xs">
                                    <span className="font-medium text-foreground">{item.name}</span>
                                    <span className="text-muted-foreground">{item.count}</span>
                                </div>
                                <div className="h-2 w-full bg-muted/50 rounded-full overflow-hidden">
                                    <div
                                        className="h-full rounded-full transition-all duration-1000 ease-out"
                                        style={{ width: `${percent}%`, backgroundColor: item.color }}
                                    ></div>
                                </div>
                            </div>
                        );
                    })}
                    {categoryBarData.length === 0 && <div className="text-center text-muted-foreground text-xs">暂无数据</div>}
                </div>
              </div>
          </div>

          {/* 第三层：AI 洞察 */}
          <div className="timeline-card p-5 md:p-6">
            <div className="flex items-center gap-3 mb-4 border-b border-border/50 pb-3">
              <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                 <i className="fas fa-robot text-primary text-lg"></i>
              </div>
              <div>
                 <h3 className="text-lg font-bold text-foreground">AI 智能洞察</h3>
              </div>
            </div>

            <div className="ai-summary-content">
               <ReactMarkdown remarkPlugins={[remarkGfm]}>
                 {aiInsight.insight_summary}
               </ReactMarkdown>
            </div>

            {/* 趋势列表 */}
            {aiInsight.top_trends.length > 0 && (
              <div className={cn(
                "mt-6 grid grid-cols-1 gap-3",
                aiInsight.top_trends.length === 1 ? "md:grid-cols-1" :
                aiInsight.top_trends.length % 3 === 0 ? "md:grid-cols-3" : "md:grid-cols-2"
              )}>
                {aiInsight.top_trends.map((trend: any, i: number) => (
                  <div key={i} className="bg-muted/30 hover:bg-muted/50 transition-colors rounded-lg p-3 border border-border/50 flex gap-3 h-full">
                    <span className="text-xl flex-shrink-0 pt-0.5" dangerouslySetInnerHTML={{ __html: trend.emoji }} />
                    <div className="flex-1">
                      <h4 className="font-bold text-sm text-foreground mb-1">{trend.title}</h4>
                      <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3" title={trend.desc}>
                        {trend.desc}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 第四层：更新列表 */}
          <section>
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-4">
              <h2 className="text-lg font-bold flex items-center gap-2 text-foreground">
                <i className="fas fa-layer-group text-primary"></i>
                详细更新列表
                <span className="text-sm font-normal text-muted-foreground ml-2">({filteredUpdates.length})</span>
              </h2>

              <div className="flex flex-wrap gap-2">
                <select
                  value={selectedVendor}
                  onChange={(e) => setSelectedVendor(e.target.value)}
                  className="h-8 rounded-md border border-input bg-card px-2 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
                >
                  <option value="all">所有厂商</option>
                  {report.vendor_summaries.map((v: any) => (
                    <option key={v.vendor} value={v.vendor}>{getVendorName(v.vendor)}</option>
                  ))}
                </select>

                <select
                  value={selectedType}
                  onChange={(e) => setSelectedType(e.target.value)}
                  className="h-8 rounded-md border border-input bg-card px-2 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
                >
                  <option value="all">所有类型</option>
                  {typeOptions.map(t => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredUpdates.map(({ vendor, update }) => {
                const vendorColor = getVendorColor(vendor);
                const typeMeta = getUpdateTypeMeta(update.update_type);
                const TypeIcon = typeMeta.icon;
                const isHero = ['new_product', 'pricing'].includes(update.update_type);

                return (
                  <div
                    key={update.update_id}
                    className={cn(
                      "timeline-card group relative overflow-hidden transition-all hover:shadow-md hover:-translate-y-1 flex flex-col",
                      isHero && "border-primary/30 bg-primary/5"
                    )}
                  >
                    <div className="h-1 w-full absolute top-0 left-0 right-0 opacity-80" style={{ backgroundColor: vendorColor }} />

                    <div className="flex flex-col h-full p-4 pt-5">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                           <div
                              className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border"
                              style={{
                                color: vendorColor,
                                borderColor: `${vendorColor}40`,
                                backgroundColor: `${vendorColor}10`
                              }}
                           >
                              {getVendorName(vendor)}
                           </div>
                        </div>
                        <span className="text-[10px] font-mono text-muted-foreground/70">
                          {update.publish_date?.slice(5, 10)}
                        </span>
                      </div>

                      <Link
                        to={`/updates/${update.update_id}`}
                        target="_blank"
                        className="text-sm font-bold text-foreground group-hover:text-primary transition-colors mb-2 leading-snug block line-clamp-2"
                        style={{ minHeight: '2.5rem' }}
                      >
                        {update.title}
                      </Link>

                      <div className="flex-1 mb-3">
                        {update.content_summary && (
                          <p className="text-xs text-muted-foreground line-clamp-3 leading-relaxed">
                            {stripMarkdown(update.content_summary)}
                          </p>
                        )}
                      </div>

                      <div className="mt-auto pt-2 border-t border-border/40 flex items-center justify-between">
                         <div className="flex items-center gap-2">
                            {update.update_type && (
                              <span className={cn('flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border font-medium', getTypeTagClass(update.update_type))}>
                                <TypeIcon className="w-2.5 h-2.5" />
                                {UPDATE_TYPE_LABELS[update.update_type] || update.update_type}
                              </span>
                            )}
                         </div>

                         {update.source_channel && (
                            <span className={cn(
                              'text-[10px] px-1 py-0.5 rounded-full font-medium opacity-70',
                              update.source_channel === 'whatsnew' ? 'text-blue-500 bg-blue-500/10' : 'text-purple-500 bg-purple-500/10'
                            )}>
                              {SOURCE_CHANNEL_LABELS[update.source_channel] || update.source_channel}
                            </span>
                         )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {filteredUpdates.length === 0 && (
              <div className="text-center py-12 text-muted-foreground bg-muted/10 rounded-xl border border-dashed border-border">
                没有找到符合条件的更新
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}