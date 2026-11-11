/**
 * Hero 标题的打字机动效状态机。
 *
 * 循环：typing → holding（停留几秒）→ deleting（快速回删）→ pausing → typing…
 * 做成纯函数 + 独立 hook，是为了能脱离浏览器单测节奏与时序，
 * 避免把时间逻辑散落在组件里（改参数时最容易把边界写错）。
 */

export type TypewriterPhase = 'typing' | 'holding' | 'deleting' | 'pausing';

export interface TypewriterState {
  /** 当前已显示的字数 */
  count: number;
  phase: TypewriterPhase;
}

export interface TypewriterTiming {
  /** 每个字的打出间隔 ms */
  typeMs: number;
  /** 打完停留多久 ms */
  holdMs: number;
  /** 回删每个字的间隔 ms */
  deleteMs: number;
  /** 回删完到重新开始之间的停顿 ms */
  pauseMs: number;
}

export const DEFAULT_TIMING: TypewriterTiming = {
  typeMs: 150,
  holdMs: 3000,
  deleteMs: 55,
  pauseMs: 420,
};

export interface TypewriterStep {
  state: TypewriterState;
  /** 距离下一步要等多少毫秒 */
  delay: number;
}

/**
 * 推进一步。total 是完整文本的字数（按 code point 计，中文每字算 1）。
 */
export function advanceTypewriter(
  state: TypewriterState,
  total: number,
  timing: TypewriterTiming = DEFAULT_TIMING,
): TypewriterStep {
  if (total <= 0) {
    return { state: { count: 0, phase: 'holding' }, delay: timing.holdMs };
  }

  // 文本变短（例如切换语言）时，把进度夹回合法范围，避免越界
  const count = Math.min(state.count, total);

  switch (state.phase) {
    case 'typing':
      if (count < total) {
        return {
          state: { count: count + 1, phase: 'typing' },
          delay: timing.typeMs,
        };
      }
      return {
        state: { count: total, phase: 'holding' },
        delay: timing.holdMs,
      };
    case 'holding':
      return {
        state: { count: total, phase: 'deleting' },
        delay: timing.deleteMs,
      };
    case 'deleting':
      if (count > 0) {
        return {
          state: { count: count - 1, phase: 'deleting' },
          delay: timing.deleteMs,
        };
      }
      return { state: { count: 0, phase: 'pausing' }, delay: timing.pauseMs };
    default:
      return { state: { count: 0, phase: 'typing' }, delay: timing.typeMs };
  }
}

export function splitChars(text: string): string[] {
  // Array.from 按 code point 切分，避免把 emoji / 代理对拆坏
  return Array.from(text);
}
