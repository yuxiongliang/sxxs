import { useEffect, useMemo, useState } from 'react';
import type { TypewriterState } from './typewriter';
import { advanceTypewriter, splitChars } from './typewriter';

/**
 * 打字机 hook。
 *
 * reducedMotion 为 true 时直接返回完整文本并停止计时器 —— 用户在系统里
 * 关掉了动效，就不该再让文字反复闪现。
 */
export function useTypewriter(text: string, reducedMotion: boolean) {
  const chars = useMemo(() => splitChars(text), [text]);
  const [state, setState] = useState<TypewriterState>({
    count: 0,
    phase: 'typing',
  });

  useEffect(() => {
    if (reducedMotion) return;
    const total = chars.length;
    const { state: next, delay } = advanceTypewriter(state, total);
    const timer = window.setTimeout(() => setState(next), delay);
    return () => window.clearTimeout(timer);
  }, [state, chars.length, reducedMotion]);

  // 文本变化（切语言）时回到起点，从头打
  useEffect(() => {
    setState({ count: 0, phase: 'typing' });
  }, []);

  const visible = reducedMotion ? text : chars.slice(0, state.count).join('');
  return {
    visible,
    done: visible.length === chars.length,
    blinking: !reducedMotion,
  };
}
