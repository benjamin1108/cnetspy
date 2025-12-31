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
import { 
  BookOpen, 
  Lightbulb, 
  Zap, 
  List, 
  Quote, 
  ArrowRight, 
  FileText,
  Target,
  Sparkles,
  ChevronDown,
  ChevronUp,
  BarChart
} from 'lucide-react';

import { useAvailableMonths, useAvailableWeeks } from '@/hooks';
import { Select, Loading } from '@/components/ui';
import { PageHeader } from '@/components/ui/PageHeader';
import { reportsApi } from '@/api';
import { getVendorColor, getVendorName, cn } from '@/lib/utils';
import { getUpdateTypeMeta } from '@/components/icons';
import { UPDATE_TYPE_LABELS, SOURCE_CHANNEL_LABELS } from '@/types';

// --- 类型定义 ---

interface TopUpdate {
  update_id?: string;
  vendor: string;
  product: string;
  title?: string;
  pain_point?: string;
  value?: string;
  comment?: string;
}

interface TopTrend {
  emoji?: string;
  title: string;
  desc: string;
}

interface FeaturedBlog {
  update_id?: string;
  vendor?: string; // Weekly specific
  emoji?: string; // Monthly specific
  title: string;
  url?: string;
  reason?: string; // Weekly specific
  desc?: string; // Monthly specific
}

interface QuickScanGroup {
  vendor: string;
  items: string[];
}

interface AiInsight {
  insight_title: string;
  insight_summary: string;
  top_updates?: TopUpdate[];
  top_trends?: TopTrend[];
  featured_blogs?: FeaturedBlog[];
  quick_scan?: QuickScanGroup[];
}

// --- 辅助函数 ---

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
  const [showAi, setShowAi] = useState(true);
  const [showStats, setShowStats] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const reportType = (searchParams.get('type') as 'weekly' | 'monthly') || 'monthly';
  const urlYear = searchParams.get('year') ? parseInt(searchParams.get('year')!) : undefined;
  const urlMonth = searchParams.get('month') ? parseInt(searchParams.get('month')!) : undefined;
  const urlWeek = searchParams.get('week') ? parseInt(searchParams.get('week')!) : undefined;

  const { data: monthsData } = useAvailableMonths();
  const availableMonths = monthsData?.data || [];

  const { data: weeksData } = useAvailableWeeks();
  const availableWeeks = weeksData?.data || [];

  const getDefaultParams = () => {
    if (reportType === 'monthly') {
      if (urlYear && urlMonth) return { year: urlYear, month: urlMonth };
      if (availableMonths?.length > 0) {
        const latest = availableMonths[0];
        return { year: latest.year, month: latest.month };
      }
      const now = new Date();
      return { year: now.getFullYear(), month: now.getMonth() + 1 };
    } else {
      if (urlYear && urlWeek) return { year: urlYear, week: urlWeek };
      if (availableWeeks?.length > 0) {
        const latest = availableWeeks[0];
        return { year: latest.year, week: latest.week };
      }
      // 默认当前年份和第一周，等待数据加载
      const now = new Date();
      return { year: now.getFullYear(), week: 1 };
    }
  };

  const currentParams = getDefaultParams();

  // 兼容旧代码变量引用
  const year = currentParams.year;
  const month = currentParams.month;
  const week = (currentParams as any).week;

  const { data: reportData, isLoading, error } = useQuery({
    queryKey: ['report', reportType, currentParams],
    queryFn: () => reportsApi.getReport(reportType, currentParams),
    enabled: !!((reportType === 'monthly' && currentParams.month) || (reportType === 'weekly' && currentParams.week))
  });

  const report = reportData?.data;

  // 1. 数据解析：AI 洞察 (增强版解析)
  const aiInsight = useMemo<AiInsight>(() => {
    const raw = report?.ai_summary;
    const defaultInsight = { insight_title: '', insight_summary: '' };
    
    if (!raw) return defaultInsight;

    let parsed: any = raw;

    // 如果是字符串，尝试解析 JSON
    if (typeof raw === 'string') {
      try {
        parsed = JSON.parse(raw);
      } catch {
        // 解析失败，说明是纯 Markdown 文本
        return {
          ...defaultInsight,
          insight_title: '本期摘要',
          insight_summary: raw,
        };
      }
    }

    // 再次确认解析后的对象结构
    if (typeof parsed === 'object' && parsed !== null) {
        return {
            insight_title: parsed.insight_title || '',
            insight_summary: typeof parsed.insight_summary === 'string' 
                ? parsed.insight_summary 
                : (JSON.stringify(parsed.insight_summary) || ''), // 防止非字符串导致崩溃
            top_updates: Array.isArray(parsed.top_updates) ? parsed.top_updates : undefined,
            top_trends: Array.isArray(parsed.top_trends) ? parsed.top_trends : undefined,
            featured_blogs: Array.isArray(parsed.featured_blogs) ? parsed.featured_blogs : undefined,
            quick_scan: Array.isArray(parsed.quick_scan) ? parsed.quick_scan : undefined,
        };
    }

    return defaultInsight;
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
      allUpdates = allUpdates.filter(item => item.update?.update_type === selectedType);
    }

    // 排序：Hero (重点) > 日期
    const heroTypes = ['new_product', 'pricing', 'compliance'];

    allUpdates.sort((a, b) => {
      const isHeroA = heroTypes.includes(a.update?.update_type);
      const isHeroB = heroTypes.includes(b.update?.update_type);

      if (isHeroA && !isHeroB) return -1;
      if (!isHeroA && isHeroB) return 1;

      return new Date(b.update?.publish_date).getTime() - new Date(a.update?.publish_date).getTime();
    });

    return allUpdates;
  }, [report?.updates_by_vendor, selectedVendor, selectedType]);

  const handleTypeChange = (type: 'weekly' | 'monthly') => {
    const params = new URLSearchParams(searchParams);
    params.set('type', type);

    // 清除不相关的参数
    if (type === 'monthly') {
      params.delete('week');
      if (availableMonths?.length > 0) {
        params.set('year', availableMonths[0].year.toString());
        params.set('month', availableMonths[0].month.toString());
      }
    } else {
      params.delete('month');
      if (availableWeeks?.length > 0) {
        params.set('year', availableWeeks[0].year.toString());
        params.set('week', availableWeeks[0].week.toString());
      }
    }

    setSearchParams(params);
    setSelectedVendor('all');
    setSelectedType('all');
  };

  const handleDateChange = (value: string) => {
    const params = new URLSearchParams(searchParams);
    const [y, mOrW] = value.split('-');
    params.set('year', y);

    if (reportType === 'monthly') {
      params.set('month', mOrW);
      params.delete('week');
    } else {
      params.set('week', mOrW);
      params.delete('month');
    }

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
        title={reportType === 'monthly' ? "月度竞争情报" : "周度竞争情报"}
        eyebrow="INTELLIGENCE // REPORT"
        description={
            <span className="flex items-center gap-2">
                <span>{year}年{reportType === 'monthly' && month ? `${month.toString().padStart(2, '0')}月` : `第${week}周`}</span>
                <span className="opacity-50">|</span>
                <span>统计周期：{report ? formatDateRange(report.date_from, report.date_to) : '...'}</span>
            </span>
        }
      >
        <div className="flex gap-2">
          <div className="flex rounded-md bg-muted p-1">
            <button
              onClick={() => handleTypeChange('weekly')}
              className={cn(
                "px-3 py-1 text-sm font-medium rounded-sm transition-all",
                reportType === 'weekly' ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              周报
            </button>
            <button
              onClick={() => handleTypeChange('monthly')}
              className={cn(
                "px-3 py-1 text-sm font-medium rounded-sm transition-all",
                reportType === 'monthly' ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              )}
            >
              月报
            </button>
          </div>

          <Select
            value={reportType === 'monthly' ? `${currentParams.year}-${currentParams.month}` : `${currentParams.year}-${currentParams.week}`}
            onChange={(e) => handleDateChange(e.target.value)}
            className="w-60"
          >
            {reportType === 'monthly' ? (
              availableMonths?.length > 0 ? (
                availableMonths.map((m) => (
                  <option key={`${m.year}-${m.month}`} value={`${m.year}-${m.month}`}>
                    {m.label}
                  </option>
                ))
              ) : (
                currentParams.month && (
                  <option value={`${currentParams.year}-${currentParams.month}`}>
                    {currentParams.year}年{currentParams.month.toString().padStart(2, '0')}月
                  </option>
                )
              )
            ) : (
              availableWeeks?.length > 0 ? (
                availableWeeks.map((w) => (
                  <option key={`${w.year}-${w.week}`} value={`${w.year}-${w.week}`}>
                    {w.label} ({w.date_from.slice(5)}~{w.date_to.slice(5)})
                  </option>
                ))
              ) : (
                <option value={`${currentParams.year}-${currentParams.week}`}>
                  {currentParams.year}年第{currentParams.week}周
                </option>
              )
            )}
          </Select>
        </div>
      </PageHeader>

      {isLoading ? (
        <div className="flex items-center justify-center h-64"><Loading /></div>
      ) : error || !report ? (
        <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-4">
          <p>
            {reportType === 'monthly'
              ? `${currentParams.year}年${currentParams.month}月的报告尚未生成`
              : `${currentParams.year}年第${currentParams.week}周的报告尚未生成`
            }
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {/* SECTION 1: AI Insight */}
            <div className="rounded-xl border border-border/40 bg-card overflow-hidden shadow-sm transition-all duration-300 hover:shadow-md">
                <button 
                    onClick={() => setShowAi(!showAi)}
                    className="w-full flex items-center justify-between py-2.5 px-4 cursor-pointer group bg-transparent hover:bg-muted/30 transition-colors text-left"
                >
                    <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-md bg-primary/10 text-primary flex items-center justify-center transition-all duration-300 group-hover:scale-110 group-hover:bg-primary group-hover:text-primary-foreground shadow-sm">
                            <Sparkles className="w-4 h-4" />
                        </div>
                        <div>
                            <h3 className="text-base font-bold text-foreground leading-tight group-hover:text-primary transition-colors">
                                {aiInsight.insight_title || "AI 智能洞察"}
                            </h3>
                            <div className="flex items-center gap-2 h-4 mt-0.5">
                                <p className="text-[10px] text-muted-foreground font-medium tracking-wide uppercase opacity-70">
                                    Intelligence // Analysis
                                </p>
                            </div>
                        </div>
                    </div>
                    <ChevronDown className={cn("w-5 h-5 text-muted-foreground transition-transform duration-300", showAi && "rotate-180 text-primary")} />
                </button>

                {showAi && (
                    <div className="px-6 pb-8 pt-2 animate-in fade-in slide-in-from-top-4 duration-500 space-y-8">
                        {/* Insight Summary */}
                        <div className="ai-summary-content prose prose-base max-w-4xl text-foreground/90 leading-relaxed mb-10 pl-6 border-l-4 border-primary/20">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {aiInsight.insight_summary}
                            </ReactMarkdown>
                        </div>

                        {/* A. Top Updates */}
                        {aiInsight.top_updates && aiInsight.top_updates.length > 0 && (
                            <div className="mb-10">
                                <h4 className="flex items-center gap-2 font-bold text-foreground mb-4 text-xs uppercase tracking-widest opacity-70">
                                    <Zap className="w-3.5 h-3.5 text-yellow-500" />
                                    核心亮点 // Key Updates
                                </h4>
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                                    {aiInsight.top_updates.map((item, idx) => {
                                         const vendorColor = getVendorColor(item.vendor);
                                         const displayName = item.title || item.product;
                                         return (
                                            <div key={idx} className="group flex flex-col h-full bg-card rounded-xl border border-border/50 hover:border-primary/40 hover:shadow-lg transition-all duration-300 overflow-hidden">
                                                <div className="p-4 pb-3 space-y-2.5">
                                                    <div className="flex items-center justify-between">
                                                        <div 
                                                            className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider border"
                                                            style={{ color: vendorColor, borderColor: `${vendorColor}30`, backgroundColor: `${vendorColor}08` }}
                                                        >
                                                            {item.vendor}
                                                        </div>
                                                    </div>
                                                    
                                                    {item.update_id ? (
                                                        <Link 
                                                            to={`/updates/${item.update_id}`} 
                                                            target="_blank"
                                                            className="font-bold text-base text-foreground leading-snug group-hover:text-primary transition-colors hover:underline decoration-primary/30 underline-offset-4 block"
                                                        >
                                                            {displayName}
                                                        </Link>
                                                    ) : (
                                                        <h5 className="font-bold text-base text-foreground leading-snug group-hover:text-primary transition-colors">
                                                            {displayName}
                                                        </h5>
                                                    )}
                                                </div>
                                                
                                                <div className="px-5 pb-5 flex-1 flex flex-col gap-4">
                                                    <div className="space-y-4">
                                                        {item.pain_point && (
                                                            <div className="relative pl-3 border-l-2 border-red-500/30">
                                                                <span className="text-[10px] font-bold text-muted-foreground/70 uppercase block mb-1">Pain Point</span>
                                                                <span className="text-sm text-foreground/80 leading-relaxed block">{item.pain_point}</span>
                                                            </div>
                                                        )}
                                                        {item.value && (
                                                            <div className="relative pl-3 border-l-2 border-green-500/30">
                                                                <span className="text-[10px] font-bold text-muted-foreground/70 uppercase block mb-1">Value</span>
                                                                <span className="text-sm text-foreground leading-relaxed block">{item.value}</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>

                                                {/* Footer - Compact Fixed Height */}
                                                <div className="h-16 bg-muted/30 border-t border-border/40 p-3 px-5 flex items-start">
                                                    {item.comment && (
                                                        <div className="flex gap-2 items-start overflow-hidden">
                                                            <Quote className="w-3.5 h-3.5 text-primary/40 flex-shrink-0 mt-0.5" />
                                                            <p className="text-xs text-muted-foreground italic leading-relaxed line-clamp-2" title={item.comment}>
                                                                {item.comment}
                                                            </p>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                         )
                                    })}
                                </div>
                            </div>
                        )}

                        {/* B. Top Trends (Fallback) */}
                        {aiInsight.top_trends && (!aiInsight.top_updates || aiInsight.top_updates.length === 0) && aiInsight.top_trends.length > 0 && (
                          <div className="animate-in fade-in slide-in-from-bottom-2 duration-700">
                              <h4 className="flex items-center gap-2 font-bold text-foreground mb-4 text-xs uppercase tracking-widest opacity-70">
                                    <Target className="w-3.5 h-3.5 text-blue-500" />
                                    本月趋势 // Trends
                                </h4>
                              <div className={cn(
                                "grid grid-cols-1 gap-4",
                                (aiInsight.top_trends.length === 1) ? "md:grid-cols-1" :
                                (aiInsight.top_trends.length % 3 === 0) ? "md:grid-cols-3" : "md:grid-cols-2"
                              )}>
                                {aiInsight.top_trends.map((trend: any, i: number) => (
                                  <div key={i} className="group bg-card hover:bg-muted/30 transition-all rounded-xl p-4 border border-border/50 hover:border-primary/30 flex gap-4 h-full">
                                    <span className="text-2xl flex-shrink-0 pt-1 filter grayscale group-hover:grayscale-0 transition-all" dangerouslySetInnerHTML={{ __html: trend.emoji || '🌟' }} />
                                    <div className="flex-1 min-w-0">
                                      <h4 className="font-bold text-sm text-foreground mb-2 group-hover:text-primary transition-colors">{trend.title}</h4>
                                      <p className="text-xs text-muted-foreground leading-relaxed line-clamp-3">
                                        {trend.desc}
                                      </p>
                                    </div>
                                  </div>
                                ))}
                              </div>
                          </div>
                        )}

                        {/* C. Featured Blogs (Editorial Layout) */}
                        {aiInsight.featured_blogs && aiInsight.featured_blogs.length > 0 && (
                            <div className="animate-in fade-in slide-in-from-bottom-2 duration-700 delay-100 py-8 border-t border-dashed border-border/50">
                                <h4 className="flex items-center gap-2 font-bold text-foreground mb-8 text-xs uppercase tracking-widest opacity-70">
                                    <BookOpen className="w-3.5 h-3.5 text-purple-500" />
                                    必读好文 // Recommended
                                </h4>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-16 gap-y-10">
                                    {aiInsight.featured_blogs.map((blog, idx) => {
                                         const vendor = blog.vendor || (blog.title.match(/\[(.*?)\]/)?.[1]) || 'Unknown';
                                         const title = blog.title.replace(`[${vendor}]`, '').trim();
                                         const desc = blog.reason || blog.desc || '';
                                         const vendorColor = getVendorColor(vendor);
                                         
                                         const internalLink = blog.update_id ? `/updates/${blog.update_id}` : null;
                                         const externalLink = blog.url;
                                         const hasLink = !!(internalLink || externalLink);

                                         return (
                                            <div key={idx} className="group flex flex-col items-start relative pl-6 border-l-2 border-transparent hover:border-primary/30 transition-all duration-300">
                                                <div className="flex items-center gap-2 mb-2">
                                                    <span 
                                                        className="text-[10px] px-2 py-0.5 rounded-md font-bold uppercase tracking-wider border"
                                                        style={{ color: vendorColor, borderColor: `${vendorColor}30`, backgroundColor: `${vendorColor}08` }}
                                                    >
                                                        {vendor}
                                                    </span>
                                                </div>
                                                
                                                {internalLink ? (
                                                    <Link to={internalLink} target="_blank" className="block w-full">
                                                        <h5 className="text-lg font-bold text-foreground leading-snug group-hover:text-primary transition-colors mb-3 flex items-start gap-1 line-clamp-2">
                                                            {title}
                                                            <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 -rotate-45 transition-all mt-1.5 flex-shrink-0 text-primary" />
                                                        </h5>
                                                    </Link>
                                                ) : externalLink ? (
                                                    <a href={externalLink} target="_blank" rel="noopener noreferrer" className="block w-full">
                                                        <h5 className="text-lg font-bold text-foreground leading-snug group-hover:text-primary transition-colors mb-3 flex items-start gap-1 line-clamp-2">
                                                            {title}
                                                            <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 -rotate-45 transition-all mt-1.5 flex-shrink-0 text-primary" />
                                                        </h5>
                                                    </a>
                                                ) : (
                                                    <h5 className="text-lg font-bold text-foreground leading-snug mb-3 line-clamp-2 cursor-default">
                                                        {title}
                                                    </h5>
                                                )}
                                                
                                                <p className="text-sm text-muted-foreground leading-relaxed line-clamp-3">
                                                    {desc}
                                                </p>
                                            </div>
                                         )
                                    })}
                                </div>
                            </div>
                        )}
                        
                        {/* D. Quick Scan (Weekly) - Newspaper Layout */}
                        {aiInsight.quick_scan && aiInsight.quick_scan.length > 0 && (
                             <div className="animate-in fade-in slide-in-from-bottom-2 duration-700 delay-200 pt-8 border-t border-dashed border-border/50">
                                <h4 className="flex items-center gap-2 font-bold text-foreground mb-6 text-xs uppercase tracking-widest opacity-70">
                                    <List className="w-3.5 h-3.5 text-green-500" />
                                    快速浏览 // Quick Scan
                                </h4>
                                <div className="columns-1 md:columns-2 lg:columns-3 gap-8 space-y-8">
                                    {aiInsight.quick_scan.map((group, idx) => {
                                        if (!group.items || group.items.length === 0) return null;
                                        return (
                                        <div key={idx} className="break-inside-avoid mb-6">
                                            <div className="flex items-baseline justify-between mb-3 pb-1 border-b border-border/40">
                                                <span className="font-bold text-sm text-foreground tracking-tight">{group.vendor}</span>
                                                <div className="h-1 w-8 rounded-full opacity-50" style={{ backgroundColor: getVendorColor(group.vendor) }}></div>
                                            </div>
                                            <ul className="space-y-2">
                                                {group.items.map((item, i) => (
                                                    <li key={i} className="text-xs leading-relaxed text-muted-foreground flex gap-2 items-start hover:text-foreground transition-colors">
                                                        <span className="flex-shrink-0 w-1 h-1 rounded-full bg-border mt-1.5"></span>
                                                        <span>{item}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* SECTION 2: Statistics */}
            <div className="rounded-xl border border-border/40 bg-card overflow-hidden shadow-sm transition-all duration-300 hover:shadow-md">
                <button 
                    onClick={() => setShowStats(!showStats)}
                    className="w-full flex items-center justify-between py-2.5 px-4 cursor-pointer group bg-transparent hover:bg-muted/30 transition-colors text-left"
                >
                    <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-md bg-blue-500/10 text-blue-500 flex items-center justify-center transition-all duration-300 group-hover:scale-110 group-hover:bg-blue-500 group-hover:text-white shadow-sm">
                            <BarChart className="w-4 h-4" />
                        </div>
                        <div>
                            <h3 className="text-base font-bold text-foreground leading-tight group-hover:text-blue-500 transition-colors">
                                数据概览
                            </h3>
                            <div className="flex items-center gap-2 h-4 mt-0.5">
                                <p className="text-[10px] text-muted-foreground font-medium tracking-wide uppercase opacity-70">
                                    Statistics // Metrics
                                </p>
                            </div>
                        </div>
                    </div>
                    <ChevronDown className={cn("w-5 h-5 text-muted-foreground transition-transform duration-300", showStats && "rotate-180 text-blue-500")} />
                </button>
                
                {showStats && (
                    <div className="px-6 pb-8 pt-2 animate-in fade-in slide-in-from-top-4 duration-500">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                            <div className="timeline-card p-4 flex flex-col justify-between h-24">
                                <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider mb-1">更新总数</div>
                                <div className="text-3xl font-bold text-foreground leading-none">{report?.total_count || 0}</div>
                                <div className="text-[10px] text-muted-foreground">监测周期内汇总</div>
                            </div>

                            <div className="timeline-card p-4 flex flex-col justify-between h-24">
                                <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider mb-1">最活跃厂商</div>
                                <div className="text-xl font-bold text-foreground truncate leading-tight">
                                    {vendorPieData[0]?.name || '-'}
                                </div>
                                <div className="text-[10px] text-muted-foreground">
                                    占比 {report?.total_count && report.total_count > 0 ? Math.round((vendorPieData[0]?.value || 0) / report.total_count * 100) : 0}%
                                </div>
                            </div>

                            <div className="timeline-card p-4 flex flex-col justify-between h-24">
                                <div className="text-muted-foreground text-[10px] font-bold uppercase tracking-wider mb-1">热门领域 Top 1</div>
                                <div className="text-xl font-bold text-foreground truncate leading-tight">
                                    {categoryBarData[0]?.name || '-'}
                                </div>
                                <div className="text-[10px] text-muted-foreground">
                                    {categoryBarData[0]?.count || 0} 条更新
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="timeline-card p-4 h-[250px] flex flex-col">
                                <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-2">厂商分布</div>
                                <div className="flex-1 w-full min-h-0 relative">
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                    <Pie
                                        data={vendorPieData}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={50}
                                        outerRadius={70}
                                        paddingAngle={4}
                                        dataKey="value"
                                        stroke="none"
                                        cornerRadius={4}
                                    >
                                        {vendorPieData && vendorPieData.map((entry, index) => (
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
                                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                                    <span className="text-2xl font-bold text-foreground">{report?.total_count || 0}</span>
                                </div>
                                </div>
                                {/* 底部图例 */}
                                <div className="flex flex-wrap justify-center gap-x-4 gap-y-2 mt-2">
                                    {vendorPieData?.slice(0, 5)?.map(v => (
                                        <div key={v.name} className="flex items-center gap-1.5">
                                            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: v.color }}></span>
                                            <span className="text-xs text-muted-foreground">{v.name}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="timeline-card p-4 h-[250px] flex flex-col">
                                <div className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground mb-4">热门更新领域 Top 5</div>
                                <div className="flex-1 flex flex-col justify-center gap-3">
                                    {categoryBarData && categoryBarData.map((item) => {
                                        const max = categoryBarData && categoryBarData.length > 0 ? Math.max(...categoryBarData.map((d: any) => d.count)) : 0;
                                        const percent = max > 0 ? (item.count / max) * 100 : 0;

                                        return (
                                            <div key={item.name} className="w-full">
                                                <div className="flex justify-between items-center mb-1 text-[10px]">
                                                    <span className="font-medium text-foreground">{item.name}</span>
                                                    <span className="text-muted-foreground">{item.count}</span>
                                                </div>
                                                <div className="h-1.5 w-full bg-muted/50 rounded-full overflow-hidden border border-border/20">
                                                    <div
                                                        className="h-full rounded-full transition-all duration-1000 ease-out"
                                                        style={{ width: `${percent}%`, backgroundColor: item.color }}
                                                    ></div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* SECTION 3: Detailed List */}
            <div className="rounded-xl border border-border/40 bg-card overflow-hidden shadow-sm transition-all duration-300 hover:shadow-md">
                <button 
                    onClick={() => setShowDetails(!showDetails)}
                    className="w-full flex items-center justify-between py-2.5 px-4 cursor-pointer group bg-transparent hover:bg-muted/30 transition-colors text-left"
                >
                    <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-md bg-purple-500/10 text-purple-500 flex items-center justify-center transition-all duration-300 group-hover:scale-110 group-hover:bg-purple-500 group-hover:text-white shadow-sm">
                            <FileText className="w-4 h-4" />
                        </div>
                        <div>
                            <h3 className="text-base font-bold text-foreground leading-tight group-hover:text-purple-500 transition-colors">
                                详细更新列表
                            </h3>
                            <div className="flex items-center gap-2 h-4 mt-0.5">
                                <p className="text-[10px] text-muted-foreground font-medium tracking-wide uppercase opacity-70">
                                    Details // Full List
                                </p>
                                <span className="bg-muted px-1.5 py-0.5 rounded text-[10px] font-bold text-muted-foreground">
                                    {filteredUpdates?.length || 0}
                                </span>
                            </div>
                        </div>
                    </div>
                    <ChevronDown className={cn("w-5 h-5 text-muted-foreground transition-transform duration-300", showDetails && "rotate-180 text-purple-500")} />
                </button>

                {showDetails && (
                    <div className="border-t border-border/40 animate-in fade-in slide-in-from-top-4 duration-500">
                    <div className="flex flex-wrap gap-2 mb-4 justify-end">
                        <select
                        value={selectedVendor}
                        onChange={(e) => setSelectedVendor(e.target.value)}
                        className="h-8 rounded-md border border-input bg-card px-2 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
                        >
                        <option value="all">所有厂商</option>
                        {report?.vendor_summaries?.map((v: any) => (
                            <option key={v.vendor} value={v.vendor}>{getVendorName(v.vendor)}</option>
                        ))}
                        </select>

                        <select
                        value={selectedType}
                        onChange={(e) => setSelectedType(e.target.value)}
                        className="h-8 rounded-md border border-input bg-card px-2 py-1 text-xs shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring text-foreground"
                        >
                        <option value="all">所有类型</option>
                        {typeOptions?.map(t => (
                            <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                        </select>
                    </div>

                    <div className="rounded-xl border border-border/40 bg-card overflow-hidden shadow-sm">
                    <div className="divide-y divide-border/40">
                        {filteredUpdates?.map(({ vendor, update }) => {
                            const vendorColor = getVendorColor(vendor);
                            const typeMeta = getUpdateTypeMeta(update.update_type);
                            const TypeIcon = typeMeta.icon;

                            return (
                            <div
                                key={update.update_id}
                                className="group relative flex items-start gap-4 p-4 hover:bg-muted/30 transition-colors"
                            >
                                {/* Left: Date & Vendor */}
                                <div className="flex-shrink-0 w-24 flex flex-col items-start gap-2 pt-0.5">
                                    <span className="text-xs font-mono text-muted-foreground/60 tabular-nums">
                                    {update.publish_date?.slice(5, 10)}
                                    </span>
                                    <div
                                        className="px-1.5 py-0.5 rounded-[4px] text-[9px] font-bold uppercase tracking-wider border"
                                        style={{
                                        color: vendorColor,
                                        borderColor: `${vendorColor}30`,
                                        backgroundColor: `${vendorColor}08`
                                        }}
                                    >
                                        {getVendorName(vendor)}
                                    </div>
                                </div>

                                {/* Middle: Content */}
                                <div className="flex-1 min-w-0 space-y-1.5">
                                    <Link
                                        to={`/updates/${update.update_id}`}
                                        target="_blank"
                                        className="text-sm font-bold text-foreground group-hover:text-primary transition-colors block leading-snug"
                                    >
                                        {update.title}
                                    </Link>
                                    {update.content_summary && (
                                    <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed opacity-80 group-hover:opacity-100 transition-opacity">
                                        {stripMarkdown(update.content_summary)}
                                    </p>
                                    )}
                                </div>

                                {/* Right: Metadata */}
                                <div className="flex-shrink-0 flex flex-col items-end gap-2 pl-4">
                                    {update.update_type && (
                                        <span className={cn('flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded border font-medium whitespace-nowrap', getTypeTagClass(update.update_type))}>
                                            <TypeIcon className="w-2.5 h-2.5" />
                                            {UPDATE_TYPE_LABELS[update.update_type] || update.update_type}
                                        </span>
                                    )}
                                    {update.source_channel && (
                                        <span className={cn(
                                        'text-[9px] px-1.5 py-px rounded-full font-medium opacity-60 whitespace-nowrap',
                                        update.source_channel === 'whatsnew' ? 'text-blue-500 bg-blue-500/10' : 'text-purple-500 bg-purple-500/10'
                                        )}>
                                        {SOURCE_CHANNEL_LABELS[update.source_channel] || update.source_channel}
                                        </span>
                                    )}
                                </div>
                            </div>
                            );
                        })}
                    </div>
                    </div>

                    {filteredUpdates?.length === 0 && (
                    <div className="text-center py-12 text-muted-foreground bg-muted/10 rounded-xl border border-dashed border-border mt-4">
                        没有找到符合条件的更新
                    </div>
                    )}
                </div>
            )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}