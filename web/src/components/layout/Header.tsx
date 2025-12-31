/**
 * 页面头部组件
 */

import { Link, useLocation } from 'react-router-dom';
import { Cloud, Menu, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { ThemeSwitcher } from '@/components/ui';
import { useStatsOverview } from '@/hooks';
import { format } from 'date-fns';

const navItems = [
  { path: '/', label: '时间线' },
  { path: '/updates', label: '更新汇总' },
  { path: '/reports', label: '周月报' },
  { path: '/dashboard', label: '仪表盘' },
];

export function Header() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { data: overviewData } = useStatsOverview();
  
  // 优先使用每日任务时间，如果没有则回退到最后爬取时间
  const lastUpdate = overviewData?.data?.last_daily_task_time || overviewData?.data?.last_crawl_time;

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border glass-effect">
      <div className="container mx-auto h-16 px-4 grid grid-cols-[auto_1fr_auto] md:grid-cols-3 items-center">
        {/* Left: Logo */}
        <div className="flex justify-start">
          <Link to="/" className="flex items-center gap-2">
            <Cloud className="h-8 w-8 text-primary" />
            <span className="text-xl font-bold text-foreground hidden sm:inline-block">CloudNetSpy</span>
            <span className="text-xl font-bold text-foreground sm:hidden">CNS</span>
          </Link>
        </div>

        {/* Center: Desktop Navigation */}
        <nav className="hidden md:flex justify-center items-center gap-1 bg-muted/40 p-1 rounded-full border border-border/50 backdrop-blur-sm self-center justify-self-center">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'px-4 py-1.5 text-sm font-medium rounded-full transition-all duration-200',
                location.pathname === item.path
                  ? 'bg-background text-primary shadow-sm'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        {/* Right: Controls */}
        <div className="flex justify-end items-center gap-3">
          {/* Last Update Badge - Desktop Only */}
          {lastUpdate && (
            <div className="hidden md:flex flex-col items-end leading-none mr-2">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold mb-0.5">
                Last Updated
              </span>
              <div className="flex items-center gap-1.5 font-mono text-xs text-foreground/80">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-500 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
                </span>
                {format(new Date(lastUpdate), 'MM-dd HH:mm')}
              </div>
            </div>
          )}

          <div className="h-4 w-[1px] bg-border hidden md:block"></div>

          <ThemeSwitcher />

          {/* Mobile Menu Button */}
          <button
            className="md:hidden p-2 text-muted-foreground hover:text-foreground transition-colors ml-2"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? (
              <X className="h-6 w-6" />
            ) : (
              <Menu className="h-6 w-6" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile Navigation */}
      {mobileMenuOpen && (
        <nav className="md:hidden border-t border-border bg-card px-4 py-4 space-y-4">
          <div className="space-y-2">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'block py-2 text-sm font-medium transition-colors hover:text-primary',
                  location.pathname === item.path
                    ? 'text-primary'
                    : 'text-muted-foreground'
                )}
                onClick={() => setMobileMenuOpen(false)}
              >
                {item.label}
              </Link>
            ))}
          </div>
          
          {/* Mobile Last Update */}
          {lastUpdate && (
            <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-muted/50 text-xs text-muted-foreground">
              <span className="relative flex h-2 w-2">
                <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
              </span>
              <span>Updated: {format(new Date(lastUpdate), 'MM-dd HH:mm')}</span>
            </div>
          )}
        </nav>
      )}
    </header>
  );
}
