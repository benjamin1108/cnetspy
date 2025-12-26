/**
 * 更新详情页面
 */

import { useParams, Link, useNavigate } from 'react-router-dom';
import { useUpdateDetail, useAnalyzeSingle } from '@/hooks';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Loading,
  EmptyState,
  Badge,
  Button,
} from '@/components/ui';
import { formatDate, formatDateTime, getVendorColor, cn, copyToClipboard } from '@/lib/utils';
import { VENDOR_DISPLAY_NAMES, UPDATE_TYPE_LABELS, SOURCE_CHANNEL_LABELS } from '@/types';
import ReactMarkdown from 'react-markdown';
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
  Sparkles,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { useState, useMemo } from 'react';

// 过滤元数据（保留标题，移除元信息 + 分隔线）
function stripMetadataHeader(content: string): string {
  // 匹配格式：
  // # 标题              <- 保留
  // **发布时间:** xxx  <- 移除
  // **厂商:** xxx       <- 移除
  // ...                  <- 移除
  // ---                  <- 移除
  // 实际内容
  const metadataRegex = /\n+(?:\*\*[^*]+\*\*.*\n+)+---\n+/;
  return content.replace(metadataRegex, '\n\n').trim();
}

export function UpdateDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);
  const [summaryExpanded, setSummaryExpanded] = useState(true);

  // 获取更新详情
  const { data, isLoading, error } = useUpdateDetail(id || '');

  // AI 分析 mutation
  const analyzeMutation = useAnalyzeSingle();

  const update = data?.data;

  // 过滤后的原始内容（移除元数据头部）
  const cleanContent = useMemo(() => {
    if (!update?.content) return '';
    return stripMetadataHeader(update.content);
  }, [update?.content]);

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
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* 返回按钮 */}
      <div className="flex items-center justify-between">
        <Link
          to="/updates"
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
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
            <Badge variant="secondary">
              {SOURCE_CHANNEL_LABELS[update.source_channel] || update.source_channel}
            </Badge>
            {update.update_type && (
              <Badge variant="default">
                {UPDATE_TYPE_LABELS[update.update_type] || update.update_type}
              </Badge>
            )}
            <span className={cn(
              'flex items-center gap-1 text-sm',
              update.has_analysis ? 'text-green-600' : 'text-gray-400'
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
          <h1 className="text-2xl font-bold text-gray-900">
            {update.title_translated || update.title}
          </h1>
          {update.title_translated && (
            <p className="text-gray-500 mt-2">{update.title}</p>
          )}

          {/* 元信息 */}
          <div className="flex flex-wrap gap-4 mt-4 text-sm text-gray-500">
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
              <Tag className="h-4 w-4 text-gray-400" />
              {update.tags.map((tag, index) => (
                <span
                  key={index}
                  className="px-2 py-1 bg-gray-100 text-gray-600 text-sm rounded"
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
        <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-indigo-50/50 overflow-hidden">
          <button
            onClick={() => setSummaryExpanded(!summaryExpanded)}
            className="w-full"
          >
            <div className="flex items-center justify-between px-6 py-4 cursor-pointer hover:bg-blue-100/50 transition-colors">
              <div className="flex items-center gap-2 text-blue-800 font-semibold">
                <Sparkles className="h-5 w-5" />
                AI 分析摘要
              </div>
              <div className="flex items-center gap-2 text-blue-600">
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
              <div className="prose prose-sm max-w-none prose-blue">
                <ReactMarkdown>{update.content_summary}</ReactMarkdown>
              </div>
            </div>
          </div>
        </Card>
      ) : (
        <Card className="border-gray-200 bg-gray-50/50">
          <CardContent className="py-8 text-center">
            <Sparkles className="h-8 w-8 text-gray-400 mx-auto mb-3" />
            <p className="text-gray-600 mb-4">该更新尚未进行 AI 分析</p>
            <Button
              onClick={handleAnalyze}
              loading={analyzeMutation.isPending}
              disabled={analyzeMutation.isPending}
            >
              {analyzeMutation.isPending ? '分析中...' : '立即分析'}
            </Button>
            {analyzeMutation.isError && (
              <p className="text-red-500 text-sm mt-2">分析失败，请稍后重试</p>
            )}
            {analyzeMutation.isSuccess && (
              <p className="text-green-500 text-sm mt-2">分析完成！页面将自动刷新</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* 原始内容 */}
      <Card>
        <CardHeader>
          <CardTitle>原始内容</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="prose prose-sm max-w-none prose-gray">
            <ReactMarkdown
              components={{
                // 自定义链接在新窗口打开
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800"
                  >
                    {children}
                  </a>
                ),
                // 自定义图片样式
                img: ({ src, alt }) => (
                  <img
                    src={src}
                    alt={alt}
                    className="max-w-full h-auto rounded-lg shadow-md"
                  />
                ),
                // 自定义代码块样式
                pre: ({ children }) => (
                  <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 overflow-x-auto">
                    {children}
                  </pre>
                ),
                code: ({ children, className }) => {
                  const isInline = !className;
                  return isInline ? (
                    <code className="bg-gray-100 text-gray-800 px-1.5 py-0.5 rounded text-sm">
                      {children}
                    </code>
                  ) : (
                    <code className={className}>{children}</code>
                  );
                },
              }}
            >
              {cleanContent}
            </ReactMarkdown>
          </div>
        </CardContent>
      </Card>

      {/* 底部操作 */}
      <div className="flex items-center justify-between pb-8">
        <Link
          to="/updates"
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 transition-colors"
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
