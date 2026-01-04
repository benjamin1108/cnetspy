import { 
  Package, Sparkles, TrendingUp, Archive, DollarSign, 
  Globe, Shield, Wrench, Gauge, FileCheck, Zap,
  AlertTriangle, Bug, BookOpen, Users, FileText
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface UpdateTypeMeta {
  icon: LucideIcon;
  colorClass: string;
  bgClass: string;
  borderClass: string;
  label: string;
}

export const UPDATE_TYPE_CONFIG: Record<string, UpdateTypeMeta> = {
  new_product: { 
    icon: Package, 
    colorClass: 'text-emerald-600 dark:text-emerald-400', 
    bgClass: 'bg-emerald-500/10',
    borderClass: 'border border-emerald-500/20',
    label: '新产品' 
  },
  new_feature: { 
    icon: Sparkles, 
    colorClass: 'text-amber-600 dark:text-amber-400', 
    bgClass: 'bg-amber-500/10',
    borderClass: 'border border-amber-500/20',
    label: '新功能' 
  },
  enhancement: { 
    icon: TrendingUp, 
    colorClass: 'text-blue-600 dark:text-blue-400', 
    bgClass: 'bg-blue-500/10',
    borderClass: 'border border-blue-500/20',
    label: '功能增强' 
  },
  breaking_change: { 
    icon: AlertTriangle, 
    colorClass: 'text-rose-600 dark:text-rose-400', 
    bgClass: 'bg-rose-500/10',
    borderClass: 'border border-rose-500/20',
    label: '破坏性变更' 
  },
  known_issue: { 
    icon: Bug, 
    colorClass: 'text-amber-700 dark:text-amber-500', 
    bgClass: 'bg-amber-500/10',
    borderClass: 'border border-amber-500/20',
    label: '已知问题' 
  },
  best_practice: { 
    icon: BookOpen, 
    colorClass: 'text-violet-600 dark:text-violet-400', 
    bgClass: 'bg-violet-500/10',
    borderClass: 'border border-violet-500/20',
    label: '最佳实践' 
  },
  case_study: { 
    icon: Users, 
    colorClass: 'text-fuchsia-600 dark:text-fuchsia-400', 
    bgClass: 'bg-fuchsia-500/10',
    borderClass: 'border border-fuchsia-500/20',
    label: '客户案例' 
  },
  documentation: { 
    icon: FileText, 
    colorClass: 'text-slate-600 dark:text-slate-400', 
    bgClass: 'bg-slate-500/10',
    borderClass: 'border border-slate-500/20',
    label: '文档更新' 
  },
  deprecation: { 
    icon: Archive, 
    colorClass: 'text-slate-600 dark:text-slate-400', 
    bgClass: 'bg-slate-500/10',
    borderClass: 'border border-slate-500/20',
    label: '停用下线' 
  },
  pricing: { 
    icon: DollarSign, 
    colorClass: 'text-green-600 dark:text-green-400', 
    bgClass: 'bg-green-500/10',
    borderClass: 'border border-green-500/20',
    label: '价格调整' 
  },
  region: { 
    icon: Globe, 
    colorClass: 'text-cyan-600 dark:text-cyan-400', 
    bgClass: 'bg-cyan-500/10',
    borderClass: 'border border-cyan-500/20',
    label: '区域可用性' 
  },
  security: { 
    icon: Shield, 
    colorClass: 'text-red-600 dark:text-red-400', 
    bgClass: 'bg-red-500/10',
    borderClass: 'border border-red-500/20',
    label: '安全更新' 
  },
  fix: { 
    icon: Wrench, 
    colorClass: 'text-orange-600 dark:text-orange-400', 
    bgClass: 'bg-orange-500/10',
    borderClass: 'border border-orange-500/20',
    label: '问题修复' 
  },
  performance: { 
    icon: Gauge, 
    colorClass: 'text-purple-600 dark:text-purple-400', 
    bgClass: 'bg-purple-500/10',
    borderClass: 'border border-purple-500/20',
    label: '性能优化' 
  },
  compliance: { 
    icon: FileCheck, 
    colorClass: 'text-indigo-600 dark:text-indigo-400', 
    bgClass: 'bg-indigo-500/10',
    borderClass: 'border border-indigo-500/20',
    label: '合规性' 
  },
  integration: { 
    icon: Zap, 
    colorClass: 'text-pink-600 dark:text-pink-400', 
    bgClass: 'bg-pink-500/10',
    borderClass: 'border border-pink-500/20',
    label: '集成能力' 
  },
  other: { 
    icon: Zap, 
    colorClass: 'text-zinc-600 dark:text-zinc-400', 
    bgClass: 'bg-zinc-500/10',
    borderClass: 'border border-zinc-500/20',
    label: '其他更新' 
  },
};

export const DEFAULT_TYPE_CONFIG: UpdateTypeMeta = { 
  icon: Zap, 
  colorClass: 'text-zinc-600 dark:text-zinc-400',
  bgClass: 'bg-zinc-500/10',
  borderClass: 'border border-zinc-500/20',
  label: '其他更新'
};

export function getUpdateTypeMeta(type: string | null | undefined): UpdateTypeMeta {
  if (!type) return DEFAULT_TYPE_CONFIG;
  return UPDATE_TYPE_CONFIG[type] || DEFAULT_TYPE_CONFIG;
}