import { describe, expect, it } from 'vitest';
import { advanceTypewriter, DEFAULT_TIMING, splitChars } from './typewriter';

describe('splitChars', () => {
  it('splits CJK text by code point', () => {
    expect(splitChars('赛霄玄思')).toEqual(['赛', '霄', '玄', '思']);
  });

  it('treats latin words and surrogate pairs safely', () => {
    expect(splitChars('AMap')).toEqual(['A', 'M', 'a', 'p']);
    expect(splitChars('🚀x')).toEqual(['🚀', 'x']);
  });
});

describe('advanceTypewriter', () => {
  const total = 4;

  it('types one character at a time until complete', () => {
    let state = { count: 0, phase: 'typing' as const };
    const counts: number[] = [];
    for (let i = 0; i < total; i += 1) {
      const step = advanceTypewriter(state, total);
      state = step.state as typeof state;
      counts.push(state.count);
    }
    expect(counts).toEqual([1, 2, 3, 4]);
  });

  it('holds for the configured pause after finishing', () => {
    const step = advanceTypewriter({ count: total, phase: 'typing' }, total);
    expect(step.state).toEqual({ count: total, phase: 'holding' });
    expect(step.delay).toBe(DEFAULT_TIMING.holdMs);
  });

  it('deletes back down to empty, then pauses before restarting', () => {
    const held = advanceTypewriter({ count: total, phase: 'holding' }, total);
    expect(held.state.phase).toBe('deleting');

    const deleting = advanceTypewriter({ count: 1, phase: 'deleting' }, total);
    expect(deleting.state).toEqual({ count: 0, phase: 'deleting' });

    const emptied = advanceTypewriter({ count: 0, phase: 'deleting' }, total);
    expect(emptied.state).toEqual({ count: 0, phase: 'pausing' });
    expect(emptied.delay).toBe(DEFAULT_TIMING.pauseMs);

    const restart = advanceTypewriter({ count: 0, phase: 'pausing' }, total);
    expect(restart.state).toEqual({ count: 0, phase: 'typing' });
  });

  it('clamps the count when the text gets shorter (language switch)', () => {
    const step = advanceTypewriter({ count: 10, phase: 'holding' }, 3);
    expect(step.state.count).toBe(3);
  });

  it('handles empty text without looping forever on typing', () => {
    const step = advanceTypewriter({ count: 0, phase: 'typing' }, 0);
    expect(step.state).toEqual({ count: 0, phase: 'holding' });
  });
});
