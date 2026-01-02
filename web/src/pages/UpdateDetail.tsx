/**
 * 更新详情页面
 */

import { useParams, Link, useNavigate } from 'react-router-dom';
import { useUpdateDetail, useAnalyzeSingle, useTranslateContent } from '@/hooks';
import {
  Card,
  CardContent,
  Loading,
  EmptyState,
  Badge,
  Button,
} from '@/components/ui';
import { getUpdateTypeMeta } from '@/components/icons';
import { formatDate, formatDateTime, getVendorColor, cn, copyToClipboard, getAiGradientColors } from '@/lib/utils';
import { VENDOR_DISPLAY_NAMES, UPDATE_TYPE_LABELS, SOURCE_CHANNEL_LABELS } from '@/types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  ArrowLeft,
  ExternalLink,
  Calendar,
  Tag,
  Folder,
  Clock,
  CheckCircle,
  Circle,
  Copy,
  Check,
  //Sparkles,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useState, useMemo } from 'react';
import { useTheme } from '@/contexts/ThemeContext';
import { SEO } from '@/components/SEO';

// 检测内容是否主要是中文（中文字符占比超过30%）
function isChineseContent(content: string): boolean {
  if (!content) return false;
  const chineseChars = content.match(/[\u4e00-\u9fff]/g) || [];
  const totalChars = content.replace(/\s/g, '').length;
  return totalChars > 0 && chineseChars.length / totalChars > 0.3;
}

// 过滤元数据（保留标题，移除元信息 + 分隔线）
function stripMetadataHeader(content: string): string {
  // 匹配英文格式: **发布时间:** xxx ... ---
  const metadataRegexEn = /\n+(?:\*\*[^*]+\*\*.*\n+)+---\n+/;
  
  // 匹配中文格式: 发布时间: xxx\n\n厂商: xxx\n\n...描述\n\n正文
  const metadataRegexZh = new RegExp('^(?:(?:发布时间|厂商|产品|类型|原始链接|描述)[:：][^\n]*\n*)+', 'm');
  
  let result = content.replace(metadataRegexEn, '\n\n');
  result = result.replace(metadataRegexZh, '');
  return result.trim();
}

export function UpdateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);
  const [summaryExpanded, setSummaryExpanded] = useState(false);  // AI摘要默认收起
  const [contentExpanded, setContentExpanded] = useState(true);   // 文章内容默认展开
  const [showTranslated, setShowTranslated] = useState(true);     // 默认显示中文
  
  // 主题色
  const { effectiveTheme } = useTheme();
  const aiGradient = getAiGradientColors(effectiveTheme === 'dark');

  // 获取更新详情
  const { data, isLoading, error } = useUpdateDetail(id || '');

  // AI 分析 mutation
  const analyzeMutation = useAnalyzeSingle();

  // 翻译 mutation
  const translateMutation = useTranslateContent();

  const update = data?.data;

  // 检查是否同时有中文和英文内容
  const hasBothLanguages = !!(update?.content_translated && update?.content);

  // 检查是否可以翻译（有原文但没有翻译，且原文不是中文）
  const canTranslate = !!(update?.content && !update?.content_translated && !isChineseContent(update.content));

  // 展示内容：根据切换状态显示
  const displayContent = useMemo(() => {
    if (hasBothLanguages && update?.content_translated && update?.content) {
      // 有两种语言时，根据切换状态显示
      if (showTranslated) {
        return stripMetadataHeader(update.content_translated);
      } else {
        return stripMetadataHeader(update.content);
      }
    }
    // 只有一种语言时，优先显示翻译内容
    if (update?.content_translated) {
      return stripMetadataHeader(update.content_translated);
    }
    if (!update?.content) return '';
    return stripMetadataHeader(update.content);
  }, [update?.content_translated, update?.content, showTranslated, hasBothLanguages]);

  // 当前显示的是翻译内容
  //const isShowingTranslated = hasBothLanguages ? showTranslated : !!update?.content_translated;
  
  // 处理复制链接
  const handleCopyLink = async () => {
    const url = window.location.href;
    const success = await copyToClipboard(url);
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // 处理 AI 分析
  const handleAnalyze = async () => {
    if (!id) return;
    try {
      await analyzeMutation.mutateAsync(id);
    } catch (error) {
      console.error('Analysis failed:', error);
    }
  };

  if (isLoading) {
    return <Loading message="加载更新详情..." />;
  }

  if (error || !update) {
    return (
      <EmptyState
        title="更新不存在"
        description="未找到该更新记录，可能已被删除"
        action={
          <Button onClick={() => navigate('/updates')}>返回列表</Button>
        }
      />
    );
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      <SEO 
        title={update.title_translated || update.title} 
        description={update.content_summary || update.title}
      />
      {/* 返回按钮 */}
      <div className="flex items-center justify-between">
        <Link
          to="/updates"
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          返回列表
        </Link>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleCopyLink}>
            {copied ? (
              <>
                <Check className="h-4 w-4 mr-1" />
                已复制
              </>
            ) : (
              <>
                <Copy className="h-4 w-4 mr-1" />
                复制链接
              </>
            )}
          </Button>
          <a
            href={update.source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Button variant="outline" size="sm">
              <ExternalLink className="h-4 w-4 mr-1" />
              原文链接
            </Button>
          </a>
        </div>
      </div>

      {/* 主标题区域 */}
      <Card>
        <CardContent className="pt-6">
          {/* 厂商和来源标签 */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <Badge
              variant="outline"
              style={{ borderColor: getVendorColor(update.vendor) }}
            >
              <span
                className="w-2 h-2 rounded-full mr-1"
                style={{ backgroundColor: getVendorColor(update.vendor) }}
              />
              {VENDOR_DISPLAY_NAMES[update.vendor] || update.vendor}
            </Badge>
            <Badge 
              variant="outline" 
              className={update.source_channel === 'whatsnew' ? 'channel-whatsnew' : 'channel-blog'}
            >
              {SOURCE_CHANNEL_LABELS[update.source_channel] || update.source_channel}
            </Badge>
            {update.update_type && (() => {
              const typeMeta = getUpdateTypeMeta(update.update_type);
              const TypeIcon = typeMeta.icon;
              return (
                <Badge variant="outline" className={cn("gap-1 pl-1.5 border-primary/20 bg-primary/5", typeMeta.colorClass)}>
                  <TypeIcon className="h-3 w-3" />
                  {UPDATE_TYPE_LABELS[update.update_type] || update.update_type}
                </Badge>
              );
            })()}
            <span className={cn(
              'flex items-center gap-1 text-sm',
              update.has_analysis ? 'status-analyzed' : 'status-unanalyzed'
            )}>
              {update.has_analysis ? (
                <>
                  <CheckCircle className="h-4 w-4" />
                  已分析
                </>
              ) : (
                <>
                  <Circle className="h-4 w-4" />
                  未分析
                </>
              )}
            </span>
          </div>

          {/* 标题 */}
          <h1 className="text-2xl font-bold text-foreground leading-tight tracking-tight">
            {update.title_translated || update.title}
          </h1>
          {update.title_translated && (
            <p className="text-muted-foreground mt-0.5 text-sm leading-tight tracking-normal">{update.title}</p>
          )}

          {/* 元信息 */}
          <div className="flex flex-wrap gap-4 mt-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              发布于 {formatDate(update.publish_date, 'long')}
            </div>
            {update.crawl_time && (
              <div className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                采集于 {formatDateTime(update.crawl_time)}
              </div>
            )}
            {update.product_name && (
              <div className="flex items-center gap-1">
                <Folder className="h-4 w-4" />
                {update.product_category && `${update.product_category} / `}
                {update.product_name}
                {update.product_subcategory && ` / ${update.product_subcategory}`}
              </div>
            )}
          </div>

          {/* 标签 */}
          {update.tags && update.tags.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 mt-4">
              <Tag className="h-4 w-4 text-muted-foreground" />
              {update.tags.map((tag, index) => (
                <span
                  key={index}
                  className="px-2 py-1 text-sm rounded tag-badge"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* AI 分析结果 - 可折叠 */}
      {update.has_analysis && update.content_summary ? (
        <Card className="ai-analysis-card overflow-hidden">
          <button
            onClick={() => setSummaryExpanded(!summaryExpanded)}
            className="w-full"
          >
            <div className="flex items-center justify-between px-6 py-4 cursor-pointer ai-analysis-header:hover transition-colors">
              <div className="flex items-center gap-2 font-semibold">
                <div className="relative">
                  {/* 图标使用SVG渐变 - 蓝绿科技色 */}
                  <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="url(#ai-gradient)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <defs>
                      <linearGradient id="ai-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor={aiGradient.start} />
                        <stop offset="50%" stopColor={aiGradient.middle} />
                        <stop offset="100%" stopColor={aiGradient.end} />
                      </linearGradient>
                    </defs>
                    <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>
                    <path d="M20 3v4"/>
                    <path d="M22 5h-4"/>
                    <path d="M4 17v2"/>
                    <path d="M5 18H3"/>
                  </svg>
                </div>
                <span className="ai-gradient-text font-semibold">
                  AI 分析摘要
                </span>
              </div>
              <div className="flex items-center gap-2 ai-analysis-header">
                <span className="text-sm font-normal">
                  {summaryExpanded ? '收起' : '展开查看'}
                </span>
                {summaryExpanded ? (
                  <ChevronUp className="h-5 w-5" />
                ) : (
                  <ChevronDown className="h-5 w-5" />
                )}
              </div>
            </div>
          </button>
          <div
            className={`transition-all duration-300 ease-in-out overflow-hidden ${
              summaryExpanded ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'
            }`}
          >
            <div className="px-6 pb-6">
              <div className="ai-summary-content">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    a: ({ href, children }) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {children}
                      </a>
                    ),
                  }}
                >
                  {update.content_summary}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        </Card>
      ) : (
        <Card className="border-border bg-gradient-to-br from-accent/50 to-accent/30">
          <CardContent className="py-8 text-center">
            <div className="relative inline-block mb-3">
              <svg className="h-8 w-8 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/>
                <path d="M20 3v4"/>
                <path d="M22 5h-4"/>
                <path d="M4 17v2"/>
                <path d="M5 18H3"/>
              </svg>
            </div>
            <p className="text-muted-foreground mb-4">该更新尚未进行 AI 分析</p>
            <Button
              onClick={handleAnalyze}
              loading={analyzeMutation.isPending}
              disabled={analyzeMutation.isPending}
            >
              {analyzeMutation.isPending ? '分析中...' : '立即分析'}
            </Button>
            {analyzeMutation.isError && (
              <p className="text-destructive text-sm mt-2">分析失败，请稍后重试</p>
            )}
            {analyzeMutation.isSuccess && (
              <p className="status-analyzed text-sm mt-2">分析完成！页面将自动刷新</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* 正文内容 - 可折叠 */}
      <Card className="overflow-hidden">
        <div
          onClick={() => setContentExpanded(!contentExpanded)}
          className="w-full cursor-pointer"
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && setContentExpanded(!contentExpanded)}
        >
          <div className="flex items-center justify-between px-6 py-4 cursor-pointer content-header-hover transition-colors">
            <div className="flex items-center gap-3">
              <span className="text-lg font-semibold text-foreground">
                更新内容
              </span>
              {/* 语言切换按钮 - 仅当两种语言都存在时显示 */}
              {hasBothLanguages && (
                <div 
                  className="flex items-center lang-switcher rounded-lg p-0.5"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowTranslated(true);
                      setContentExpanded(true); // 自动展开
                    }}
                    className={`px-2.5 py-1 text-xs rounded-md transition-all ${
                      showTranslated
                        ? 'lang-switcher-active'
                        : 'lang-switcher-inactive'
                    }`}
                  >
                    中文
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowTranslated(false);
                      setContentExpanded(true); // 自动展开
                    }}
                    className={`px-2.5 py-1 text-xs rounded-md transition-all ${
                      !showTranslated
                        ? 'lang-switcher-active'
                        : 'lang-switcher-inactive'
                    }`}
                  >
                    EN
                  </button>
                </div>
              )}
              {/* 翻译按钮 - 仅当没有翻译内容时显示 */}
              {canTranslate && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (id != null) {
                      translateMutation.mutate(id);
                    }
                  }}
                  disabled={translateMutation.isPending}
                  className="translate-btn flex items-center gap-1.5 px-3 py-1 text-xs rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {translateMutation.isPending ? (
                    <>
                      <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      翻译中...
                    </>
                  ) : (
                    <>
                      <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="m5 8 6 6M4 14l6-6 2-3M2 5h12M7 2h1M22 22l-5-10-5 10M14 18h6" />
                      </svg>
                      翻译全文
                    </>
                  )}
                </button>
              )}
              {translateMutation.isError && (
                <span className="text-xs text-destructive">翻译失败</span>
              )}
            </div>
            <div className="flex items-center gap-2 text-muted-foreground">
              <span className="text-sm">
                {contentExpanded ? '收起' : '展开查看'}
              </span>
              {contentExpanded ? (
                <ChevronUp className="h-5 w-5" />
              ) : (
                <ChevronDown className="h-5 w-5" />
              )}
            </div>
          </div>
        </div>
        <div
          className={`transition-all duration-300 ease-in-out overflow-hidden ${
            contentExpanded ? 'max-h-[50000px] opacity-100' : 'max-h-0 opacity-0'
          }`}
        >
          <CardContent className="pt-6">
            <div className="article-content">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // 链接在新窗口打开
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {children}
                    </a>
                  ),
                  // 表格响应式包装
                  table: ({ children }) => (
                    <div className="overflow-x-auto">
                      <table>{children}</table>
                    </div>
                  ),
                }}
              >
                {displayContent}
              </ReactMarkdown>
            </div>
          </CardContent>
        </div>
      </Card>

      {/* 底部操作 */}
      <div className="flex items-center justify-between pb-8">
        <Link
          to="/updates"
          className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          返回列表
        </Link>
        <a
          href={update.source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Button>
            <ExternalLink className="h-4 w-4 mr-2" />
            查看原文
          </Button>
        </a>
      </div>
    </div>
  );
}
