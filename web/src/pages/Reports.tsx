/**
 * 竞争分析报告页面
 *
 * 核心原则：全站风格高度统一（微光标题、一致的卡片语言、轴向流布局）
 */

import { useState, useMemo } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  PieChart, Pie, Cell, Tooltip as RechartsTooltip, ResponsiveContainer, Legend
} from 'recharts';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { 
  Quote, 
  Sparkles,
  ChevronDown,
  BarChart,
  ArrowUpRight
} from 'lucide-react';
import { getISOWeek, getYear, subWeeks } from 'date-fns';

import { useAvailableMonths, useAvailableWeeks } from '@/hooks';
import { Select, Loading } from '@/components/ui';
import { PageHeader } from '@/components/ui/PageHeader';
import { reportsApi } from '@/api';
import { getVendorColor, getVendorName, cn } from '@/lib/utils';
import { SEO } from '@/components/SEO';

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
  vendor?: string;
  title: string;
  url?: string;
  reason?: string;
}

interface QuickScanItem {
  update_id: string;
  content: string;
  is_noteworthy?: boolean;
  reason?: string;
}

interface QuickScanGroup {
  vendor: string;
  items: QuickScanItem[];
}

interface LandmarkUpdate {
  update_id: string;
  vendor: string;
  title: string;
  product: string;
  pain_point: string;
  value: string;
  comment: string;
}

interface SolutionReference {
  update_id: string;
  title: string;
}

interface SolutionInsight {
  theme: string;
  summary: string;
  references: SolutionReference[];
}

interface AiInsight {
  insight_title: string;
  insight_summary: string;
  top_updates?: TopUpdate[];
  featured_blogs?: FeaturedBlog[];
  quick_scan?: QuickScanGroup[];
  landmark_updates?: LandmarkUpdate[];
  noteworthy_updates?: QuickScanGroup[];
  solution_analysis?: SolutionInsight[];
  top_trends?: TopTrend[];
}

function formatDateRange(from?: string, to?: string) {
    if (!from || !to) return '';
    return `${from} 至 ${to}`;
}

export function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [showAi, setShowAi] = useState(true);
  const [showStats, setShowStats] = useState(false);

  const reportType = (searchParams.get('type') as 'weekly' | 'monthly') || 'weekly';
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
      return { year: new Date().getFullYear(), month: new Date().getMonth() + 1 };
    } else {
      if (urlYear && urlWeek) return { year: urlYear, week: urlWeek };
      if (availableWeeks?.length > 0) {
        const latest = availableWeeks[0];
        return { year: latest.year, week: latest.week };
      }
      // Fallback: Default to last week to avoid showing empty future reports
      const lastWeek = subWeeks(new Date(), 1);
      return { year: getYear(lastWeek), week: getISOWeek(lastWeek) };
    }
  };

  const currentParams = getDefaultParams();

  const { data: reportData, isLoading, error } = useQuery({
    queryKey: ['report', reportType, currentParams],
    queryFn: () => reportsApi.getReport(reportType, currentParams),
    enabled: !!((reportType === 'monthly' && currentParams.month) || (reportType === 'weekly' && (currentParams as any).week))
  });

  const report = reportData?.data;

  const aiInsight = useMemo<AiInsight>(() => {
    const raw = report?.ai_summary;
    const defaultInsight = { insight_title: '', insight_summary: '' };
    if (!raw) return defaultInsight;

    let parsed: any = raw;
    if (typeof raw === 'string') {
      try { parsed = JSON.parse(raw); } 
      catch { return { ...defaultInsight, insight_title: '本期摘要', insight_summary: raw }; }
    }

    if (typeof parsed === 'object' && parsed !== null) {
        let title = parsed.insight_title || '';
        // Remove manual prefixing here, let UI handle the layout
        
        return {
            insight_title: title,
            insight_summary: typeof parsed.insight_summary === 'string' ? parsed.insight_summary : (JSON.stringify(parsed.insight_summary) || ''),
            top_updates: Array.isArray(parsed.top_updates) ? parsed.top_updates.filter((u: any) => u.product || u.title) : undefined,
            featured_blogs: Array.isArray(parsed.featured_blogs) ? parsed.featured_blogs.filter((b: any) => b.title) : undefined,
            quick_scan: Array.isArray(parsed.quick_scan) ? 
                parsed.quick_scan
                    .map((group: any) => ({
                        ...group,
                        items: Array.isArray(group.items) ? group.items.filter((item: any) => {
                            const content = typeof item === 'string' ? item : item.content;
                            return content && content.trim() !== '';
                        }) : []
                    }))
                    .filter((group: any) => group.items.length > 0) : undefined,
            landmark_updates: Array.isArray(parsed.landmark_updates) ? parsed.landmark_updates.filter((u: any) => u.title) : undefined,
            noteworthy_updates: Array.isArray(parsed.noteworthy_updates) ? 
                parsed.noteworthy_updates
                    .map((group: any) => ({
                        ...group,
                        items: Array.isArray(group.items) ? group.items.filter((item: any) => item.content && item.content.trim() !== '') : []
                    }))
                    .filter((group: any) => group.items.length > 0) : undefined,
            solution_analysis: Array.isArray(parsed.solution_analysis) ? parsed.solution_analysis.filter((s: any) => s.theme) : undefined,
            top_trends: Array.isArray(parsed.top_trends) ? parsed.top_trends : undefined,
        };
    }
    return defaultInsight;
  }, [report?.ai_summary, reportType]);

  const vendorPieData = useMemo(() => {
    if (!report?.vendor_summaries) return [];
    return report.vendor_summaries
      .filter(v => v.count > 0)
      .map(v => ({ name: getVendorName(v.vendor), value: v.count, color: getVendorColor(v.vendor) }))
      .sort((a, b) => b.value - a.value);
  }, [report?.vendor_summaries]);

  const categoryBarData = useMemo(() => {
    if (!report?.updates_by_vendor) return [];
    const categoryStats: Record<string, { total: number; vendors: Record<string, number> }> = {};
    Object.entries(report.updates_by_vendor).forEach(([vendor, updates]) => {
      (updates as any[]).forEach((u: any) => {
        const cat = u.product_subcategory || '其他';
        if (!categoryStats[cat]) categoryStats[cat] = { total: 0, vendors: {} };
        categoryStats[cat].total += 1;
        categoryStats[cat].vendors[vendor] = (categoryStats[cat].vendors[vendor] || 0) + 1;
      });
    });
    return Object.entries(categoryStats).sort((a, b) => b[1].total - a[1].total).slice(0, 5).map(([name, stats]) => {
        let dominantVendor = 'unknown';
        let maxCount = -1;
        Object.entries(stats.vendors).forEach(([v, count]) => { if (count > maxCount) { maxCount = count; dominantVendor = v; } });
        return { name: dominantVendor !== 'unknown' ? `${getVendorName(dominantVendor)} - ${name}` : name, count: stats.total, color: getVendorColor(dominantVendor) };
    });
  }, [report?.updates_by_vendor]);

  const handleTypeChange = (type: 'weekly' | 'monthly') => {
    const params = new URLSearchParams(searchParams);
    params.set('type', type);

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
  };

  const handleDateChange = (value: string) => {
    const params = new URLSearchParams(searchParams);
    const [y, mOrW] = value.split('-');
    params.set('year', y);
    if (reportType === 'monthly') { params.set('month', mOrW); params.delete('week'); } 
    else { params.set('week', mOrW); params.delete('month'); }
    setSearchParams(params);
  };

  // 辅助渲染发光标题
  const GlowingHeader = ({ title, subtitle }: { title: string, subtitle: string }) => (
    <h4 
        className="font-bold text-primary/90 text-xs uppercase tracking-[0.3em] mb-10"
        style={{ textShadow: '0 0 8px hsl(var(--primary) / 0.3)' }}
    >
        {title} // {subtitle}
    </h4>
  );

  const pageTitle = reportType === 'monthly' 
    ? `${currentParams.year}年${currentParams.month}月竞争情报月报`
    : `${currentParams.year}年第${(currentParams as any).week}周竞争情报周报`;

  const pageDesc = aiInsight.insight_summary 
    ? aiInsight.insight_summary.slice(0, 150).replace(/[#*`]/g, '') + '...'
    : `CloudNetSpy ${pageTitle}，汇集本期云厂商网络产品核心动态与战略洞察。`;

  return (
    <div className="space-y-6 animate-in fade-in duration-500 pb-12">
      <SEO title={pageTitle} description={pageDesc} />
      <PageHeader
        title={reportType === 'monthly' ? "月度竞争情报" : "周度竞争情报"}
        eyebrow="INTELLIGENCE // REPORT"
        description={<span>统计周期：{report ? formatDateRange(report.date_from, report.date_to) : '...'}</span>}
      >
        <div className="flex gap-2">
          <div className="flex rounded-md bg-muted p-1 border border-border/20">
            <button onClick={() => handleTypeChange('weekly')} className={cn("px-3 py-1 text-sm font-medium rounded-sm transition-all", reportType === 'weekly' ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>周报</button>
            <button onClick={() => handleTypeChange('monthly')} className={cn("px-3 py-1 text-sm font-medium rounded-sm transition-all", reportType === 'monthly' ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground")}>月报</button>
          </div>
          <Select value={reportType === 'monthly' ? `${currentParams.year}-${currentParams.month}` : `${currentParams.year}-${(currentParams as any).week}`} onChange={(e) => handleDateChange(e.target.value)} className="w-36">
            {reportType === 'monthly' ? 
              (availableMonths?.map(m => <option key={`${m.year}-${m.month}`} value={`${m.year}-${m.month}`}>{m.label}</option>)) : 
              (availableWeeks?.map(w => <option key={`${w.year}-${w.week}`} value={`${w.year}-${w.week}`}>{w.label}</option>))
            }
          </Select>
        </div>
      </PageHeader>

      {isLoading ? (
        <div className="flex items-center justify-center h-64"><Loading /></div>
      ) : error || !report ? (
        <div className="flex flex-col items-center justify-center h-64 text-muted-foreground gap-4">
          <p>{reportType === 'monthly' ? `${currentParams.year}年${currentParams.month}月的报告尚未生成` : `${currentParams.year}年第${(currentParams as any).week}周的报告尚未生成`}</p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* SECTION 1: AI Insight Panel */}
          <div className="rounded-xl border border-border/40 bg-card overflow-hidden shadow-sm transition-all duration-300 hover:shadow-md">
            <button onClick={() => setShowAi(!showAi)} className="w-full flex items-center justify-between p-8 group hover:bg-muted/5 transition-colors text-left">
                <div className="flex flex-col items-start gap-3">
                    <span 
                        className="font-bold text-primary/90 text-xs uppercase tracking-[0.3em]"
                        style={{ textShadow: '0 0 8px hsl(var(--primary) / 0.3)' }}
                    >
                        {reportType === 'weekly' ? '本周主题 // WEEKLY THEME' : '本月主题 // MONTHLY THEME'}
                    </span>
                    <h3 className="text-3xl font-black text-foreground tracking-tight group-hover:text-primary transition-colors leading-tight">
                        {aiInsight.insight_title}
                    </h3>
                </div>
                <ChevronDown className={cn("w-6 h-6 text-muted-foreground transition-transform duration-500", showAi && "rotate-180")} />
            </button>

            {showAi && (
                <div className="px-10 pb-16 pt-4 space-y-12 animate-in slide-in-from-top-4 duration-700">
                    {/* Executive Summary Area - Redesigned for Premium Typography */}
                    <div className="relative group">
                        {/* Huge Decorative Background Icon */}
                        <div className="absolute top-0 right-0 -mr-12 -mt-12 text-primary/[0.03] pointer-events-none select-none transition-transform duration-1000 group-hover:scale-110 group-hover:-rotate-12">
                            <Sparkles size={400} strokeWidth={1} />
                        </div>

                        <div className="relative z-10 flex gap-10">
                            {/* Large Opening Quote */}
                            <Quote className="w-12 h-12 text-primary/10 flex-shrink-0 -mt-2" />
                            
                            <div className="flex-1">
                                <div className="ai-summary-content prose prose-zinc dark:prose-invert max-w-4xl text-2xl font-medium text-foreground/80 leading-[1.8] tracking-tight">
                                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{aiInsight.insight_summary}</ReactMarkdown>
                                </div>
                                <div className="mt-10 w-24 h-1 bg-gradient-to-r from-primary/30 to-transparent rounded-full" />
                            </div>
                        </div>
                    </div>

                    {reportType === 'monthly' ? (
                        <div className="space-y-16">
                            {/* Landmarks */}
                            <div>
                                <GlowingHeader title="月度里程碑发布" subtitle="LANDMARKS" />
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {aiInsight.landmark_updates?.map((item, idx) => {
                                        const vendorColor = getVendorColor(item.vendor);
                                        const displayName = (item.title && item.product && item.title.toLowerCase().includes(item.product.toLowerCase())) ? item.title : `${item.product}: ${item.title}`;
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
                                                    <Link to={`/updates/${item.update_id}`} target="_blank" className="font-bold text-base text-foreground leading-snug group-hover:text-primary transition-colors hover:underline decoration-primary/30 underline-offset-4 block line-clamp-2 min-h-[3rem]">{displayName}</Link>
                                                </div>
                                                <div className="px-5 pb-5 flex-1 flex flex-col gap-4">
                                                    <div className="space-y-4">
                                                        <div className="relative pl-3 border-l-2 border-red-500/30">
                                                            <span className="text-[10px] font-bold text-muted-foreground/70 uppercase block mb-1">Pain Point</span>
                                                            <span className="text-sm text-foreground/80 leading-relaxed line-clamp-3 h-[4.5rem] overflow-hidden" title={item.pain_point}>{item.pain_point}</span>
                                                        </div>
                                                        <div className="relative pl-3 border-l-2 border-green-500/30">
                                                            <span className="text-[10px] font-bold text-muted-foreground/70 uppercase block mb-1">Value</span>
                                                            <span className="text-sm text-foreground leading-relaxed line-clamp-3 h-[4.5rem] overflow-hidden" title={item.value}>{item.value}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div className="h-20 bg-muted/30 border-t border-border/40 p-3 px-5 flex items-start gap-2">
                                                    <Quote className="w-3.5 h-3.5 text-primary/40 flex-shrink-0 mt-0.5" />
                                                    <p className="text-xs text-muted-foreground italic leading-relaxed line-clamp-3" title={item.comment}>{item.comment}</p>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* Solutions & Industry Analysis - Strategic Split Layout */}
                            {aiInsight.solution_analysis && aiInsight.solution_analysis.length > 0 && (
                                <div>
                                    <GlowingHeader title="解决方案与行业洞察" subtitle="SOLUTIONS" />
                                    <div className="divide-y divide-border/20 border-t border-border/20">
                                        {aiInsight.solution_analysis.map((sol, idx) => (
                                            <div key={idx} className="group flex flex-col md:flex-row gap-8 py-12 items-start transition-colors hover:bg-muted/5 px-4">
                                                {/* Left Column: Number & Theme */}
                                                <div className="md:w-1/3 flex flex-col gap-2 relative">
                                                    <span className="text-5xl font-black text-primary/5 absolute -top-6 -left-2 italic select-none">0{idx+1}</span>
                                                    <h5 className="text-lg font-black text-foreground uppercase tracking-tight relative z-10 group-hover:text-primary transition-colors leading-tight">
                                                        {sol.theme}
                                                    </h5>
                                                </div>

                                                {/* Right Column: Insight & References */}
                                                <div className="flex-1 space-y-6">
                                                    <p className="text-sm text-muted-foreground leading-relaxed italic border-l-2 border-primary/20 pl-6">
                                                        “{sol.summary}”
                                                    </p>
                                                    
                                                    {sol.references && sol.references.length > 0 && (
                                                        <div className="flex flex-wrap gap-x-6 gap-y-3 pl-6">
                                                            {sol.references.map((ref, i) => (
                                                                <Link 
                                                                    key={i} 
                                                                    to={`/updates/${ref.update_id}`} 
                                                                    target="_blank"
                                                                    className="flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground/60 hover:text-primary transition-all group/ref"
                                                                >
                                                                    <span className="opacity-40">#</span>
                                                                    <span className="border-b border-transparent group-hover/ref:border-primary/30 transition-all truncate max-w-[300px]">
                                                                        {ref.title}
                                                                    </span>
                                                                    <ArrowUpRight className="w-3 h-3 opacity-0 group-hover/ref:opacity-100 -translate-y-0.5 transition-all" />
                                                                </Link>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Noteworthy */}
                            <div>
                                <GlowingHeader title="其他重要更新汇总" subtitle="NOTEWORTHY" />
                                <div className="space-y-12">
                                    {aiInsight.noteworthy_updates?.map((group, idx) => (
                                        <div key={idx} className="flex flex-col md:flex-row gap-6 md:gap-12 group">
                                            <div className="md:w-32 flex-shrink-0">
                                                <div className="sticky top-4 flex items-center gap-2">
                                                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: getVendorColor(group.vendor) }}></div>
                                                    <span className="font-bold text-sm text-foreground/80 tracking-tight group-hover:text-primary transition-colors">{group.vendor}</span>
                                                </div>
                                            </div>
                                            <div className="flex-1">
                                                <ul className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-x-8 gap-y-6">
                                                    {group.items.map((item, i) => (
                                                        <li key={i} className="text-[13px] leading-relaxed transition-all flex flex-col gap-1.5 border-l-2 border-primary bg-primary/[0.03] pl-4 py-2 group/item rounded-r-xl hover:bg-primary/[0.06]">
                                                            <div className="flex items-start gap-2">
                                                                <Link to={`/updates/${item.update_id}`} target="_blank" className="text-foreground font-bold hover:text-primary transition-colors line-clamp-2 flex-1">{item.content}</Link>
                                                                <Sparkles className="w-3.5 h-3.5 text-primary flex-shrink-0 mt-0.5" />
                                                            </div>
                                                            <span className="text-[11px] text-muted-foreground/70 italic leading-snug">{item.reason}</span>
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="space-y-16">
                            {/* Weekly Sections */}
                            <div>
                                <GlowingHeader title="重点更新" subtitle="KEY UPDATES" />
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {aiInsight.top_updates?.map((item, idx) => {
                                        const vendorColor = getVendorColor(item.vendor);
                                        const displayName = item.title || item.product || '';
                                        return (
                                            <div key={idx} className="group flex flex-col h-full bg-card rounded-xl border border-border/50 hover:border-primary/40 hover:shadow-lg transition-all duration-300 overflow-hidden">
                                                <div className="p-4 pb-3 space-y-2.5">
                                                    <div className="flex items-center justify-between">
                                                        <div className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider border" style={{ color: vendorColor, borderColor: `${vendorColor}30`, backgroundColor: `${vendorColor}08` }}>{item.vendor}</div>
                                                    </div>
                                                    {item.update_id ? (
                                                        <Link to={`/updates/${item.update_id}`} target="_blank" className="font-bold text-base text-foreground leading-snug group-hover:text-primary transition-colors hover:underline decoration-primary/30 underline-offset-4 block line-clamp-2 min-h-[3rem]">{displayName}</Link>
                                                    ) : <h5 className="font-bold text-base text-foreground line-clamp-2 min-h-[3rem]">{displayName}</h5>}
                                                </div>
                                                <div className="px-5 pb-5 flex-1 flex flex-col gap-4">
                                                    <div className="space-y-4">
                                                        <div className="relative pl-3 border-l-2 border-red-500/30">
                                                            <span className="text-[10px] font-bold text-muted-foreground/70 uppercase block mb-1">Pain Point</span>
                                                            <span className="text-sm text-foreground/80 leading-relaxed line-clamp-3 h-[4.5rem] overflow-hidden" title={item.pain_point}>{item.pain_point}</span>
                                                        </div>
                                                        <div className="relative pl-3 border-l-2 border-green-500/30">
                                                            <span className="text-[10px] font-bold text-muted-foreground/70 uppercase block mb-1">Value</span>
                                                            <span className="text-sm text-foreground leading-relaxed line-clamp-3 h-[4.5rem] overflow-hidden" title={item.value}>{item.value}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                <div className="h-20 bg-muted/30 border-t border-border/40 p-3 px-5 flex items-start gap-2">
                                                    <Quote className="w-3.5 h-3.5 text-primary/40 flex-shrink-0 mt-0.5" />
                                                    <p className="text-xs text-muted-foreground italic leading-relaxed line-clamp-3" title={item.comment}>{item.comment}</p>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            <div>
                                <GlowingHeader title="其他更新" subtitle="OTHER UPDATES" />
                                <div className="space-y-12">
                                    {aiInsight.quick_scan?.map((group, idx) => (
                                        <div key={idx} className="flex flex-col md:flex-row gap-6 md:gap-12 group">
                                            <div className="md:w-32 flex-shrink-0">
                                                <div className="sticky top-4 flex items-center gap-2">
                                                    <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: getVendorColor(group.vendor) }}></div>
                                                    <span className="font-bold text-sm text-foreground/80 tracking-tight group-hover:text-primary transition-colors">{group.vendor}</span>
                                                </div>
                                            </div>
                                            <div className="flex-1">
                                                <ul className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-x-8 gap-y-4">
                                                    {group.items.map((item, i) => {
                                                        const content = typeof item === 'string' ? item : item.content;
                                                        const uid = typeof item === 'string' ? null : item.update_id;
                                                        const isNw = typeof item === 'string' ? false : item.is_noteworthy;
                                                        return (
                                                            <li key={i} className={cn("text-[13px] leading-relaxed transition-all flex gap-3 items-start pl-4 py-2 group/item rounded-r-xl", isNw ? "border-l-2 border-primary bg-primary/[0.03] font-bold hover:bg-primary/[0.06]" : "border-l border-border/30 text-muted-foreground hover:text-foreground hover:border-primary/30")}>
                                                                {uid ? (
                                                                    <Link to={`/updates/${uid}`} target="_blank" className="hover:text-primary transition-colors flex items-start gap-2 flex-1">
                                                                        <span>{content}</span>
                                                                    </Link>
                                                                ) : <span className="flex-1">{content}</span>}
                                                                {isNw && <Sparkles className="w-3.5 h-3.5 text-primary flex-shrink-0 mt-0.5" />}
                                                            </li>
                                                        );
                                                    })}
                                                </ul>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div>
                                <GlowingHeader title="必读好文" subtitle="SPOTLIGHT" />
                                <div className="grid grid-cols-1 gap-8">
                                    {aiInsight.featured_blogs?.map((blog, idx) => {
                                         const vendorColor = getVendorColor(blog.vendor || '');
                                         const title = (blog.title || '').replace(`[${blog.vendor}]`, '').trim();
                                         return (
                                            <div key={idx} className="group relative flex gap-8 items-start">
                                                <div className="w-1 self-stretch rounded-full bg-border group-hover:bg-primary/40 transition-colors" style={{ backgroundColor: `${vendorColor}20` }}>
                                                    <div className="w-full h-1/4 rounded-full" style={{ backgroundColor: vendorColor }}></div>
                                                </div>
                                                <div className="flex-1 min-w-0 py-1">
                                                    <div className="flex items-center gap-3 mb-2">
                                                        <span className="text-[10px] font-bold uppercase tracking-wider opacity-60" style={{ color: vendorColor }}>{blog.vendor}</span>
                                                    </div>
                                                    {blog.update_id || blog.url ? (
                                                        <Link to={blog.update_id ? `/updates/${blog.update_id}` : (blog.url || '#')} target="_blank" className="block text-xl font-bold text-foreground hover:text-primary transition-colors leading-tight mb-3">{title}</Link>
                                                    ) : <h5 className="text-xl font-bold text-foreground leading-tight mb-3">{title}</h5>}
                                                    <div className="relative">
                                                        <p className="text-sm text-muted-foreground leading-relaxed max-w-3xl">{blog.reason}</p>
                                                    </div>
                                                </div>
                                            </div>
                                         );
                                    })}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}
          </div>

          {/* SECTION 2: Statistics */}
          <div className="rounded-xl border border-border/40 bg-card overflow-hidden shadow-sm transition-all duration-300 hover:shadow-md">
                <button onClick={() => setShowStats(!showStats)} className="w-full flex items-center justify-between py-2.5 px-4 cursor-pointer group bg-transparent hover:bg-muted/30 transition-colors text-left">
                    <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-md bg-blue-500/10 text-blue-500 flex items-center justify-center transition-all duration-300 group-hover:scale-110 group-hover:bg-blue-500 group-hover:text-white shadow-sm">
                            <BarChart className="w-4 h-4" />
                        </div>
                        <div>
                            <h3 className="text-base font-bold text-foreground leading-tight group-hover:text-blue-500 transition-colors">数据概览</h3>
                            <div className="flex items-center gap-2 h-4 mt-0.5">
                                <p className="text-[10px] text-muted-foreground font-medium tracking-wide uppercase opacity-70">Statistics // Metrics</p>
                            </div>
                        </div>
                    </div>
                    <ChevronDown className={cn("w-5 h-5 text-muted-foreground transition-transform duration-300", showStats && "rotate-180 text-blue-500")} />
                </button>
                
                {showStats && (
                    <div className="px-6 pb-10 pt-2 animate-in slide-in-from-top-4 duration-500">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                            {/* Chart 1: Vendor Distribution */}
                            <div className="p-5 rounded-xl bg-muted/5 border border-border/20 flex flex-col h-full">
                                <div className="flex items-center justify-between mb-6">
                                    <span className="text-[10px] font-bold text-muted-foreground/60 uppercase tracking-widest">厂商分布 // Share</span>
                                    <span className="text-xs font-mono text-muted-foreground bg-background/50 px-2 py-0.5 rounded border border-border/50">{report?.total_count} Updates</span>
                                </div>
                                <div className="h-[280px] w-full relative -ml-2">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie 
                                                data={vendorPieData} 
                                                cx="50%" 
                                                cy="50%" 
                                                innerRadius={60} 
                                                outerRadius={90} 
                                                paddingAngle={4} 
                                                dataKey="value" 
                                                stroke="hsl(var(--card))" 
                                                strokeWidth={2}
                                                cornerRadius={4}
                                            >
                                                {vendorPieData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                                            </Pie>
                                            <RechartsTooltip 
                                                contentStyle={{ backgroundColor: 'hsl(var(--card))', borderRadius: '8px', border: '1px solid hsl(var(--border))', fontSize: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }} 
                                                itemStyle={{ color: 'hsl(var(--foreground))' }}
                                                cursor={false}
                                            />
                                            <Legend 
                                                verticalAlign="bottom" 
                                                height={36} 
                                                iconType="circle" 
                                                iconSize={8}
                                                formatter={(value) => <span className="text-xs text-muted-foreground ml-1">{value}</span>}
                                            />
                                        </PieChart>
                                    </ResponsiveContainer>
                                    {/* Center Text */}
                                    <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none pb-8">
                                        <span className="text-3xl font-black text-foreground tracking-tighter">{report?.total_count}</span>
                                        <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-medium">Total</span>
                                    </div>
                                </div>
                            </div>

                            {/* Chart 2: Top Categories */}
                            <div className="p-5 rounded-xl bg-muted/5 border border-border/20 flex flex-col h-full">
                                <div className="flex items-center justify-between mb-8">
                                    <span className="text-[10px] font-bold text-muted-foreground/60 uppercase tracking-widest">活跃领域 // Top 5 Categories</span>
                                </div>
                                <div className="space-y-6 flex-1">
                                    {categoryBarData.map((item, index) => {
                                        const max = Math.max(...categoryBarData.map(d => d.count));
                                        return (
                                            <div key={item.name} className="group">
                                                <div className="flex justify-between text-xs font-medium mb-2">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-xs font-mono text-muted-foreground/50 w-3">0{index + 1}</span>
                                                        <span className="text-foreground/80 group-hover:text-primary transition-colors">{item.name}</span>
                                                    </div>
                                                    <span className="font-mono text-foreground font-bold">{item.count}</span>
                                                </div>
                                                <div className="h-2.5 w-full bg-muted/40 rounded-full overflow-hidden">
                                                    <div 
                                                        className="h-full rounded-full transition-all duration-1000 ease-out group-hover:brightness-110" 
                                                        style={{ width: `${(item.count / max) * 100}%`, backgroundColor: item.color }} 
                                                    />
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
        </div>
      )}
    </div>
  );
}