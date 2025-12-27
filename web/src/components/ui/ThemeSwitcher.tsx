/**
 * 主题切换器组件
 * 位置：Header 右侧
 * 功能：提供浅色/深色/跟随系统三种主题切换
 */

import { useState, useEffect, useRef } from 'react';
import { Sun, Moon, Monitor, Check } from 'lucide-react';
import { useTheme } from '@/contexts/ThemeContext';
import { cn } from '@/lib/utils';

const themeOptions = [
  { value: 'light' as const, label: '浅色模式', icon: Sun },
  { value: 'dark' as const, label: '深色模式', icon: Moon },
  { value: 'system' as const, label: '跟随系统', icon: Monitor },
];

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 点击外部关闭下拉菜单
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  // 获取当前主题图标
  const currentOption = themeOptions.find(opt => opt.value === theme) || themeOptions[2];
  const CurrentIcon = currentOption.icon;

  const handleThemeChange = (newTheme: 'light' | 'dark' | 'system') => {
    setTheme(newTheme);
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* 主题按钮 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'flex items-center justify-center',
          'w-9 h-9 rounded-md',
          'text-muted-foreground hover:text-foreground',
          'hover:bg-accent transition-colors',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary'
        )}
        aria-label="切换主题"
        aria-expanded={isOpen}
      >
        <CurrentIcon className="h-5 w-5" />
      </button>

      {/* 下拉菜单 */}
      {isOpen && (
        <div
          className={cn(
            'absolute right-0 top-full mt-2',
            'w-40 py-2 rounded-lg',
            'bg-card border border-border shadow-lg',
            'animate-in fade-in slide-in-from-top-2 duration-200',
            'z-50'
          )}
        >
          {themeOptions.map((option) => {
            const Icon = option.icon;
            const isSelected = theme === option.value;

            return (
              <button
                key={option.value}
                onClick={() => handleThemeChange(option.value)}
                className={cn(
                  'w-full flex items-center gap-3 px-3 py-2',
                  'text-sm text-left',
                  'hover:bg-accent transition-colors',
                  isSelected ? 'text-foreground' : 'text-muted-foreground'
                )}
              >
                <Icon className="h-4 w-4" />
                <span className="flex-1">{option.label}</span>
                {isSelected && <Check className="h-4 w-4" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
