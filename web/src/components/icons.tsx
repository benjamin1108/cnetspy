import { 
  Package, Sparkles, TrendingUp, Archive, DollarSign, 
  Globe, Shield, Wrench, Gauge, FileCheck, Zap, Puzzle
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export interface UpdateTypeMeta {
  icon: LucideIcon;
  colorClass: string;
  label: string;
}

export const UPDATE_TYPE_CONFIG: Record<string, UpdateTypeMeta> = {
  new_product: { icon: Package, colorClass: 'text-emerald-500', label: '新产品' },
  new_feature: { icon: Sparkles, colorClass: 'text-amber-500', label: '新功能' },
  enhancement: { icon: TrendingUp, colorClass: 'text-blue-500', label: '功能增强' },
  deprecation: { icon: Archive, colorClass: 'text-slate-500', label: '停用/下线' },
  pricing: { icon: DollarSign, colorClass: 'text-green-500', label: '价格调整' },
  region: { icon: Globe, colorClass: 'text-cyan-500', label: '区域可用性' },
  security: { icon: Shield, colorClass: 'text-red-500', label: '安全更新' },
  fix: { icon: Wrench, colorClass: 'text-orange-500', label: '问题修复' },
  performance: { icon: Gauge, colorClass: 'text-purple-500', label: '性能优化' },
  compliance: { icon: FileCheck, colorClass: 'text-indigo-500', label: '合规性' },
  integration: { icon: Puzzle, colorClass: 'text-pink-500', label: '集成能力' },
};

export const DEFAULT_TYPE_CONFIG: UpdateTypeMeta = { 
  icon: Zap, 
  colorClass: 'text-primary',
  label: '其他更新'
};

export function getUpdateTypeMeta(type: string | null | undefined): UpdateTypeMeta {
  if (!type) return DEFAULT_TYPE_CONFIG;
  return UPDATE_TYPE_CONFIG[type] || DEFAULT_TYPE_CONFIG;
}