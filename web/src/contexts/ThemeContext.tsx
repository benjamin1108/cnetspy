import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';

type Theme = 'light' | 'dark' | 'system';
type EffectiveTheme = 'light' | 'dark';

interface ThemeContextValue {
  theme: Theme;
  effectiveTheme: EffectiveTheme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const STORAGE_KEY = 'cloudnetspy-theme';

/**
 * 获取系统主题偏好
 */
function getSystemTheme(): EffectiveTheme {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/**
 * 从 localStorage 读取保存的主题
 */
function getStoredTheme(): Theme {
  if (typeof window === 'undefined') return 'system';
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored;
    }
  } catch (error) {
    console.error('Failed to read theme from localStorage:', error);
  }
  return 'system';
}

/**
 * 计算实际生效的主题
 */
function getEffectiveTheme(theme: Theme): EffectiveTheme {
  if (theme === 'system') {
    return getSystemTheme();
  }
  return theme;
}

/**
 * 应用主题到 DOM
 */
function applyTheme(effectiveTheme: EffectiveTheme) {
  const root = document.documentElement;
  if (effectiveTheme === 'dark') {
    root.classList.add('dark');
  } else {
    root.classList.remove('dark');
  }
}

interface ThemeProviderProps {
  children: ReactNode;
}

/**
 * 主题提供者组件
 * 
 * 职责：
 * - 管理全局主题状态（light / dark / system）
 * - 提供主题切换方法
 * - 处理主题状态持久化
 * - 监听系统主题变化
 * - 控制 HTML 根元素的 dark 类名
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(getStoredTheme);
  const [effectiveTheme, setEffectiveTheme] = useState<EffectiveTheme>(() => 
    getEffectiveTheme(getStoredTheme())
  );

  // 监听系统主题变化
  useEffect(() => {
    if (theme !== 'system') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    const handleChange = (e: MediaQueryListEvent) => {
      const newEffectiveTheme = e.matches ? 'dark' : 'light';
      setEffectiveTheme(newEffectiveTheme);
      applyTheme(newEffectiveTheme);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [theme]);

  // 应用主题到 DOM
  useEffect(() => {
    applyTheme(effectiveTheme);
  }, [effectiveTheme]);

  const setTheme = (newTheme: Theme) => {
    try {
      localStorage.setItem(STORAGE_KEY, newTheme);
    } catch (error) {
      console.error('Failed to save theme to localStorage:', error);
    }

    setThemeState(newTheme);
    const newEffectiveTheme = getEffectiveTheme(newTheme);
    setEffectiveTheme(newEffectiveTheme);
    applyTheme(newEffectiveTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, effectiveTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

/**
 * 主题 Hook
 * 用于在组件中访问主题状态和切换函数
 */
export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
}
