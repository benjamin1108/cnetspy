/**
 * 竞争分析报告页面
 * 
 * 展示周报/月报数据，包含：
 * - 报告头部（科技感标题 + 时间范围）
 * - 厂商动态统计（进度条）
 * - 详细更新列表（按厂商分组，可折叠）
 */

import { useState, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useReportData, useAvailableMonths } from '@/hooks';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Loading,
  EmptyState,
  Select,
} from '@/components/ui';
import { formatDate, getVendorColor, formatNumber } from '@/lib/utils';
import {
  VENDOR_DISPLAY_NAMES,
  UPDATE_TYPE_LABELS,
} from '@/types';
import type { ReportUpdateItem, VendorSummary } from '@/types';
import {
  Zap,
  Activity,
  Layers,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  Calendar,
  FileText,
  Sparkles,
  Package,
  TrendingUp,
  Archive,
  Globe,
  Shield,
  Wrench,
} from 'lucide-react';

// 更新类型图标配置
const UPDATE_TYPE_ICONS: Record<string, React.ReactNode> = {
  new_product: <Package className="h-4 w-4" />,
  new_feature: <Sparkles className="h-4 w-4" />,
  enhancement: <TrendingUp className="h-4 w-4" />,
  deprecation: <Archive className="h-4 w-4" />,
  region: <Globe className="h-4 w-4" />,
  security: <Shield className="h-4 w-4" />,
  fix: <Wrench className="h-4 w-4" />,
};

// 进度条组件
interface ProgressBarProps {
  value: number;
  max: number;
  color: string;
  label: string;
  count: number;
  delay?: number;
}

function ProgressBar({ value, max, color, label, count, delay = 0 }: ProgressBarProps) {
  const percent = max > 0 ? (value / max) * 100 : 0;
  
  return (
    <div className="group py-2">
      <div className="flex justify-between text-sm mb-1.5">
        <span className="font-medium text-foreground">{label}</span>
        <span className="text-muted-foreground group-hover:text-foreground transition-colors">
          {formatNumber(count)} ({percent.toFixed(0)}%)
        </span>
      </div>
      <div className="progress-track h-3 rounded-full">
        <div
          className="h-full rounded-full progress-bar-animated"
          style={{
            '--progress-width': `${percent}%`,
            '--progress-delay': `${delay}ms`,
            backgroundColor: color,
          } as React.CSSProperties}
        />
      </div>
    </div>
  );
}

// 厂商分组组件
interface VendorSectionProps {
  vendor: string;
  updates: ReportUpdateItem[];
  defaultExpanded?: boolean;
}

function VendorSection({ vendor, updates, defaultExpanded = false }: VendorSectionProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const displayName = VENDOR_DISPLAY_NAMES[vendor] || vendor;
  
  return (
    <div className="border-b border-border last:border-b-0">
      <button
        className="flex justify-between items-center w-full p-4 hover:bg-muted/50 transition-colors text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          {expanded ? (
            <ChevronDown className="h-5 w-5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-5 w-5 text-muted-foreground" />
          )}
          <span className="font-semibold text-foreground">{displayName}</span>
        </div>
        <span className="px-3 py-1 rounded-full bg-primary/10 text-primary text-sm font-medium">
          {updates.length} 条
        </span>
      </button>
      
      {expanded && (
        <div className="space-y-2 px-4 pb-4 pl-12">
          {updates.map((update) => (
            <UpdateCard key={update.update_id} update={update} />
          ))}
        </div>
      )}
    </div>
  );
}

// 单条更新卡片
interface UpdateCardProps {
  update: ReportUpdateItem;
}

function UpdateCard({ update }: UpdateCardProps) {
  const typeLabel = UPDATE_TYPE_LABELS[update.update_type || ''] || update.update_type || '其他';
  const typeIcon = UPDATE_TYPE_ICONS[update.update_type || ''] || <FileText className="h-4 w-4" />;
  const title = update.title_translated || update.title;
  
  return (
    <Link
      to={`/updates/${update.update_id}`}
      className="block p-4 rounded-lg border border-border hover:border-primary/50 hover:bg-muted/30 transition-all group"
    >
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-muted text-muted-foreground group-hover:text-primary transition-colors">
          {typeIcon}
        </div>
        
        <div className="flex-1 min-w-0">
          <h4 className="font-medium text-foreground group-hover:text-primary transition-colors line-clamp-2">
            {title}
          </h4>
          <div className="flex items-center gap-2 mt-1.5 text-sm text-muted-foreground">
            <span className="px-2 py-0.5 rounded bg-muted text-xs">{typeLabel}</span>
            <span>•</span>
            <span>{formatDate(update.publish_date)}</span>
          </div>
        </div>
        
        <ExternalLink className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 mt-1" />
      </div>
    </Link>
  );
}

// 主页面组件
export function ReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  
  // 从 URL 获取报告类型和时间参数
  const reportType = (searchParams.get('type') as 'weekly' | 'monthly') || 'monthly';
  const year = searchParams.get('year') ? parseInt(searchParams.get('year')!) : undefined;
  const month = searchParams.get('month') ? parseInt(searchParams.get('month')!) : undefined;
  
  // 获取报告数据
  const { data: reportData, isLoading, error } = useReportData(reportType, { year, month });
  const { data: monthsData } = useAvailableMonths();
  
  const report = reportData?.data;
  const apiError = reportData?.success === false ? reportData.error : null;
  const availableMonths = monthsData?.data || [];
  
  // 计算最大更新数（用于进度条）
  const maxCount = useMemo(() => {
    if (!report?.vendor_summaries) return 0;
    return Math.max(...report.vendor_summaries.map((v: VendorSummary) => v.count), 1);
  }, [report?.vendor_summaries]);
  
  // 切换报告类型
  const handleTypeChange = (type: string) => {
    const params = new URLSearchParams(searchParams);
    params.set('type', type);
    if (type === 'weekly') {
      params.delete('year');
      params.delete('month');
    }
    setSearchParams(params);
  };
  
  // 切换月份
  const handleMonthChange = (value: string) => {
    const [y, m] = value.split('-');
    const params = new URLSearchParams(searchParams);
    params.set('year', y);
    params.set('month', m);
    setSearchParams(params);
  };
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loading />
      </div>
    );
  }
  
  if (error || apiError || !report) {
    return (
      <div className="max-w-4xl mx-auto">
        <EmptyState
          icon={<FileText className="h-12 w-12" />}
          title="暂无报告"
          description="该时段的报告尚未生成"
          action={
            <button
              onClick={() => window.history.back()}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              返回
            </button>
          }
        />
      </div>
    );
  }
  
  return (
    <div className="max-w-4xl mx-auto space-y-6 fade-in-up">
      {/* 页面头部 - 科技感标题 */}
      <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-primary/10 via-ai-bg/50 to-accent/10 border border-ai-border/30 p-6 md:p-8">
        {/* 背景网格 */}
        <div className="absolute inset-0 grid-bg opacity-30" />
        
        {/* 发光圆点装饰 */}
        <div className="absolute top-4 right-4 w-2 h-2 rounded-full bg-ai-accent pulse-dot" />
        
        <div className="relative flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Zap className="h-7 w-7 text-ai-accent" />
              <h1 className="text-2xl md:text-3xl font-bold ai-gradient-text">竞争分析报告</h1>
            </div>
            <p className="text-muted-foreground">实时洞察云计算竞争格局</p>
          </div>
          
          {/* 筛选器 */}
          <div className="flex items-center gap-3">
            <Select
              value={reportType}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="w-24"
            >
              <option value="weekly">周报</option>
              <option value="monthly">月报</option>
            </Select>
            
            {reportType === 'monthly' && availableMonths.length > 0 && (
              <Select
                value={year && month ? `${year}-${month}` : ''}
                onChange={(e) => handleMonthChange(e.target.value)}
                className="w-36"
              >
                <option value="">选择月份</option>
                {availableMonths.map((m) => (
                  <option key={`${m.year}-${m.month}`} value={`${m.year}-${m.month}`}>
                    {m.label}
                  </option>
                ))}
              </Select>
            )}
          </div>
        </div>
        
        {/* 时间范围标签 */}
        <div className="relative mt-4 flex items-center gap-2 text-sm text-muted-foreground">
          <Calendar className="h-4 w-4" />
          <span>
            {formatDate(report.date_from, 'long')} - {formatDate(report.date_to, 'long')}
          </span>
        </div>
      </div>
      
      {/* AI 趋势分析 */}
      {report.ai_summary && (
        <Card className="glass-card glow-border fade-in-up-delay-1">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-ai-accent" />
              月度趋势分析
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="ai-summary-content">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      {children}
                    </a>
                  ),
                }}
              >
                {report.ai_summary}
              </ReactMarkdown>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* 厂商动态统计 */}
      <Card className="glass-card glow-border fade-in-up-delay-2">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary" />
            厂商动态总览
          </CardTitle>
        </CardHeader>
        <CardContent>
          {report.vendor_summaries.length > 0 ? (
            <>
              <div className="space-y-1">
                {report.vendor_summaries.map((vendor: VendorSummary, index: number) => (
                  <ProgressBar
                    key={vendor.vendor}
                    label={VENDOR_DISPLAY_NAMES[vendor.vendor] || vendor.vendor}
                    value={vendor.count}
                    max={maxCount}
                    color={getVendorColor(vendor.vendor)}
                    count={vendor.count}
                    delay={index * 100}
                  />
                ))}
              </div>
              
              {/* 总计 */}
              <div className="mt-6 pt-4 border-t border-border flex justify-between items-center">
                <span className="text-lg font-semibold text-foreground">总计</span>
                <span className="text-2xl font-bold text-primary">{formatNumber(report.total_count)} 条更新</span>
              </div>
            </>
          ) : (
            <p className="text-muted-foreground text-center py-8">暂无数据</p>
          )}
        </CardContent>
      </Card>
      
      {/* 详细更新列表 */}
      <Card className="tech-card fade-in-up-delay-3">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-primary" />
            详细更新列表
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {report.vendor_summaries.length > 0 ? (
            <div className="divide-y divide-border">
              {report.vendor_summaries.map((vendor: VendorSummary, index: number) => (
                <VendorSection
                  key={vendor.vendor}
                  vendor={vendor.vendor}
                  updates={report.updates_by_vendor[vendor.vendor] || []}
                  defaultExpanded={index === 0}
                />
              ))}
            </div>
          ) : (
            <p className="text-muted-foreground text-center py-8">暂无数据</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
