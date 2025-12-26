/**
 * 仪表盘页面
 */

import { useStatsOverview, useStatsTimeline, useVendorStats, useUpdateTypeStats } from '@/hooks';
import { Card, CardContent, CardHeader, CardTitle, Loading } from '@/components/ui';
import { formatNumber, formatPercent, getVendorColor } from '@/lib/utils';
import { VENDOR_DISPLAY_NAMES, UPDATE_TYPE_LABELS } from '@/types';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
} from 'recharts';
import { format, subDays } from 'date-fns';
import { TrendingUp, Database, CheckCircle, Clock, Filter } from 'lucide-react';
import { useState } from 'react';
import { Select } from '@/components/ui';

export function DashboardPage() {
  // 过滤器状态
  const [dateRange, setDateRange] = useState('30'); // 默认30天
  const [selectedVendor, setSelectedVendor] = useState('');

  // 计算日期范围
  const dateFrom = dateRange ? format(subDays(new Date(), parseInt(dateRange)), 'yyyy-MM-dd') : undefined;

  // 获取统计概览
  const { data: overviewData, isLoading: overviewLoading } = useStatsOverview();

  // 获取时间线数据
  const { data: timelineData, isLoading: timelineLoading } = useStatsTimeline({
    granularity: 'day',
    date_from: dateFrom,
    vendor: selectedVendor || undefined,
  });

  // 获取厂商统计（根据日期过滤）
  const { data: vendorData, isLoading: vendorLoading } = useVendorStats({
    date_from: dateFrom,
  });

  // 获取更新类型统计（根据过滤器联动）
  const { data: updateTypeStatsData, isLoading: updateTypeLoading } = useUpdateTypeStats({
    date_from: dateFrom,
    vendor: selectedVendor || undefined,
  });

  if (overviewLoading) {
    return <Loading message="加载仪表盘数据..." />;
  }

  const overview = overviewData?.data;
  const timeline = timelineData?.data || [];
  const vendors = vendorData?.data || [];

  // 准备厂商饼图数据
  const vendorPieData = vendors.map((v) => ({
    name: VENDOR_DISPLAY_NAMES[v.vendor] || v.vendor,
    value: v.count,
    color: getVendorColor(v.vendor),
  }));

  // 准备更新类型柱状图数据
  const updateTypes = updateTypeStatsData?.data || {};
  const updateTypeChartData = Object.entries(updateTypes)
    .map(([type, count]) => ({
      type: UPDATE_TYPE_LABELS[type] || type,
      count,
    }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  // 准备时间线图表数据
  const timelineChartData = timeline.map((item) => ({
    date: format(new Date(item.date), 'MM-dd'),
    count: item.count,
    ...item.vendors,
  }));

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">仪表盘</h1>
        <p className="text-gray-500 mt-1">云计算竞争情报概览</p>
      </div>

      {/* 过滤器 */}
      <Card>
        <CardContent className="py-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-gray-500" />
              <span className="text-sm font-medium text-gray-700">筛选</span>
            </div>
            <Select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="w-40"
            >
              <option value="7">近 7 天</option>
              <option value="30">近 30 天</option>
              <option value="90">近 90 天</option>
              <option value="180">近 180 天</option>
              <option value="365">近 1 年</option>
              <option value="">全部时间</option>
            </Select>
            <Select
              value={selectedVendor}
              onChange={(e) => setSelectedVendor(e.target.value)}
              className="w-40"
            >
              <option value="">全部厂商</option>
              {vendors.map((v) => (
                <option key={v.vendor} value={v.vendor}>
                  {VENDOR_DISPLAY_NAMES[v.vendor] || v.vendor}
                </option>
              ))}
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="更新总数"
          value={formatNumber(overview?.total_updates || 0)}
          icon={<Database className="h-5 w-5" />}
          description="所有厂商更新记录"
        />
        <StatCard
          title="已分析"
          value={formatPercent(overview?.analysis_coverage || 0)}
          icon={<CheckCircle className="h-5 w-5" />}
          description="AI分析覆盖率"
        />
        <StatCard
          title="厂商数量"
          value={Object.keys(overview?.vendors || {}).length.toString()}
          icon={<TrendingUp className="h-5 w-5" />}
          description="监控的云厂商"
        />
        <StatCard
          title="最后更新"
          value={overview?.last_crawl_time ? format(new Date(overview.last_crawl_time), 'MM-dd HH:mm') : '-'}
          icon={<Clock className="h-5 w-5" />}
          description="最后爬取时间"
        />
      </div>

      {/* 图表区域 */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* 时间趋势图 */}
        <Card>
          <CardHeader>
            <CardTitle>更新趋势{dateRange ? `（近${dateRange}天）` : '（全部）'}</CardTitle>
          </CardHeader>
          <CardContent>
            {timelineLoading ? (
              <div className="h-[300px] flex items-center justify-center">
                <Loading />
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={timelineChartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={12} />
                  <YAxis fontSize={12} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke="#3B82F6"
                    fill="#93C5FD"
                    fillOpacity={0.6}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* 厂商分布饼图 */}
        <Card>
          <CardHeader>
            <CardTitle>厂商分布</CardTitle>
          </CardHeader>
          <CardContent>
            {vendorLoading ? (
              <div className="h-[300px] flex items-center justify-center">
                <Loading />
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={vendorPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, percent }) =>
                      `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
                    }
                    labelLine={false}
                  >
                    {vendorPieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 更新类型分布 */}
      <Card>
        <CardHeader>
          <CardTitle>更新类型分布</CardTitle>
        </CardHeader>
        <CardContent>
          {updateTypeLoading ? (
            <div className="h-[300px] flex items-center justify-center">
              <Loading />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={updateTypeChartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" fontSize={12} />
                <YAxis type="category" dataKey="type" fontSize={12} width={100} />
                <Tooltip />
                <Bar dataKey="count" fill="#3B82F6" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* 厂商详情表格 */}
      <Card>
        <CardHeader>
          <CardTitle>厂商统计详情</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-3 px-4 text-left font-medium text-gray-500">厂商</th>
                  <th className="py-3 px-4 text-right font-medium text-gray-500">更新总数</th>
                  <th className="py-3 px-4 text-right font-medium text-gray-500">已分析</th>
                  <th className="py-3 px-4 text-right font-medium text-gray-500">覆盖率</th>
                </tr>
              </thead>
              <tbody>
                {vendors.map((vendor) => (
                  <tr key={vendor.vendor} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: getVendorColor(vendor.vendor) }}
                        />
                        {VENDOR_DISPLAY_NAMES[vendor.vendor] || vendor.vendor}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right">{formatNumber(vendor.count)}</td>
                    <td className="py-3 px-4 text-right">{formatNumber(vendor.analyzed)}</td>
                    <td className="py-3 px-4 text-right">
                      {formatPercent(vendor.count > 0 ? vendor.analyzed / vendor.count : 0)}
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

// 统计卡片组件
interface StatCardProps {
  title: string;
  value: string;
  icon: React.ReactNode;
  description: string;
}

function StatCard({ title, value, icon, description }: StatCardProps) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-500">{title}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
            <p className="text-xs text-gray-400 mt-1">{description}</p>
          </div>
          <div className="text-blue-600">{icon}</div>
        </div>
      </CardContent>
    </Card>
  );
}
