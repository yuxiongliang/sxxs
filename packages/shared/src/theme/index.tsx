/**
 * 全局主题（亮色 / 暗色 / 跟随系统）。
 *
 * 为什么要提到应用根：
 *   - 只包页面 <div> 时，antd 的弹窗/下拉/消息走 portal 到 body，拿不到主题；
 *   - <html> 的 color-scheme 不设，原生滚动条、表单控件仍是亮色；
 *   - body 背景不由 antd 管，页面留白处会露出亮色。
 * 因此在 rootContainer 里包一层 ConfigProvider，并同步 <html data-theme>、
 * color-scheme 与 body 背景（用 antd 的 token 反推算，不硬编码颜色）。
 */
import { theme as antdTheme, ConfigProvider } from 'antd';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

export const THEME_STORAGE_KEY = 'app-theme';
export const THEME_MODES: ThemeMode[] = ['light', 'dark', 'system'];

/** 纯函数：便于脱离浏览器单测 */
export function resolveMode(
  mode: ThemeMode,
  systemPrefersDark: boolean,
): ResolvedTheme {
  if (mode === 'system') return systemPrefersDark ? 'dark' : 'light';
  return mode;
}

export function parseStoredMode(raw: string | null | undefined): ThemeMode {
  if (raw === 'light' || raw === 'dark' || raw === 'system') return raw;
  // 未选择过时默认跟随系统 —— 这是现在的主流预期
  return 'system';
}

const SYSTEM_DARK_QUERY = '(prefers-color-scheme: dark)';

function readSystemPrefersDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia(SYSTEM_DARK_QUERY).matches;
}

export interface AppThemeValue {
  /** 用户的选择：light / dark / system */
  mode: ThemeMode;
  /** 实际生效的主题（system 会被解析成 light 或 dark） */
  resolved: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
}

const AppThemeContext = createContext<AppThemeValue | null>(null);

export function useAppTheme(): AppThemeValue {
  const value = useContext(AppThemeContext);
  if (!value) {
    throw new Error('useAppTheme 必须在 AppThemeProvider 内使用');
  }
  return value;
}

export function AppThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    if (typeof window === 'undefined') return 'system';
    try {
      return parseStoredMode(window.localStorage.getItem(THEME_STORAGE_KEY));
    } catch {
      return 'system';
    }
  });
  const [systemPrefersDark, setSystemPrefersDark] = useState<boolean>(
    readSystemPrefersDark,
  );

  // system 模式下要跟随系统实时变化（用户中途切换系统主题）
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const media = window.matchMedia(SYSTEM_DARK_QUERY);
    const onChange = (event: MediaQueryListEvent) =>
      setSystemPrefersDark(event.matches);
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, []);

  const resolved = resolveMode(mode, systemPrefersDark);

  const setMode = useCallback((next: ThemeMode) => {
    setModeState(next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      /* 隐私模式写不进 localStorage，忽略 */
    }
  }, []);

  const algorithm =
    resolved === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm;

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = resolved;
    // 让原生滚动条、表单控件、下拉框跟随主题
    root.style.colorScheme = resolved;
    // body 背景 antd 不管，用 token 反推，避免硬编码色值
    const token = antdTheme.getDesignToken({ algorithm });
    document.body.style.backgroundColor = token.colorBgLayout;
    document.body.style.color = token.colorText;
  }, [resolved, algorithm]);

  const value = useMemo<AppThemeValue>(
    () => ({ mode, resolved, setMode }),
    [mode, resolved, setMode],
  );

  return (
    <AppThemeContext.Provider value={value}>
      <ConfigProvider theme={{ algorithm }}>{children}</ConfigProvider>
    </AppThemeContext.Provider>
  );
}
