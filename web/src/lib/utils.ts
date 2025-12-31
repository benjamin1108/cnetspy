import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format as dateFnsFormat } from 'date-fns';
import { zhCN } from 'date-fns/locale';

/**
 * 合并 Tailwind CSS 类名
 * 使用 clsx 处理条件类名，使用 tailwind-merge 解决类名冲突
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * 格式化数字，添加千分位分隔符
 */
export function formatNumber(num: number): string {
  return num.toLocaleString('zh-CN');
}

/**
 * 格式化百分比
 */
export function formatPercent(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`;
}

/**
 * 获取厂商颜色
 * 为了图表区分度，对部分厂商颜色进行了调整（非严格品牌色，而是视觉区分色）
 */
export function getVendorColor(vendor: string): string {
  const v = vendor.toLowerCase();
  const colorMap: Record<string, string> = {
    aws: '#FF9900',          // AWS Orange
    azure: '#0078D4',        // Azure Blue
    gcp: '#34A853',          // Google Green (为了区分 Azure)
    huawei: '#D7000F',       // Huawei Red
    tencentcloud: '#0052D9', // Tencent Blue (Darker)
    volcengine: '#8B5CF6',   // Violet (为了区分其他蓝色)
    aliyun: '#FF6A00',       // Aliyun Orange
  };
  return colorMap[v] || '#6B7280'; // Default Gray
}

/**
 * 获取厂商显示名称
 */
export function getVendorName(vendor: string): string {
  const v = vendor.toLowerCase();
  const nameMap: Record<string, string> = {
    aws: 'AWS',
    azure: 'Azure',
    gcp: 'GCP',
    huawei: '华为云',
    tencentcloud: '腾讯云',
    volcengine: '火山引擎',
    aliyun: '阿里云',
  };
  return nameMap[v] || vendor;
}

/**
 * 格式化日期
 */
export function formatDate(dateString: string, formatType: 'short' | 'long' = 'short'): string {
  try {
    const date = new Date(dateString);
    if (formatType === 'long') {
      return dateFnsFormat(date, 'yyyy年MM月dd日', { locale: zhCN });
    }
    return dateFnsFormat(date, 'yyyy-MM-dd');
  } catch (error) {
    return dateString;
  }
}

/**
 * 格式化日期时间
 */
export function formatDateTime(dateTimeString: string): string {
  try {
    const date = new Date(dateTimeString);
    return dateFnsFormat(date, 'yyyy-MM-dd HH:mm:ss');
  } catch (error) {
    return dateTimeString;
  }
}

/**
 * 截断文本
 */
export function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + '...';
}

/**
 * 复制到剪贴板
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (error) {
    console.error('Failed to copy to clipboard:', error);
    return false;
  }
}

/**
 * 获取图表主题色 - 科技感蓝色主题
 * 用于 recharts 等图表库
 */
export function getChartThemeColors(isDark: boolean) {
  return {
    // 主色 - 电光蓝/霓虹青
    primary: isDark ? 'hsl(199, 89%, 55%)' : 'hsl(217, 91%, 60%)',
    primaryFill: isDark ? 'hsl(192, 91%, 50%)' : 'hsl(199, 89%, 48%)',
    // 文字色
    text: isDark ? 'hsl(199, 89%, 94%)' : 'hsl(217, 33%, 17%)',
    textMuted: isDark ? 'hsl(199, 20%, 65%)' : 'hsl(215, 20%, 45%)',
    // 背景色
    background: isDark ? 'hsl(222, 47%, 8%)' : 'hsl(210, 50%, 99%)',
    // 边框色
    border: isDark ? 'hsl(217, 33%, 20%)' : 'hsl(214, 32%, 85%)',
    // 网格线
    grid: isDark ? 'hsl(217, 33%, 15%)' : 'hsl(214, 32%, 90%)',
  };
}

/**
 * 获取 AI 分析图标渐变色 - 科技青蓝渐变
 */
export function getAiGradientColors(isDark: boolean) {
  return {
    start: isDark ? 'hsl(192, 91%, 60%)' : 'hsl(192, 91%, 50%)',
    middle: isDark ? 'hsl(199, 89%, 55%)' : 'hsl(199, 89%, 48%)',
    end: isDark ? 'hsl(217, 91%, 60%)' : 'hsl(217, 91%, 55%)',
  };
}
