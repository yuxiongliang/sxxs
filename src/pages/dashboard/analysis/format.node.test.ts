import { describe, expect, it } from 'vitest';
import {
  centsToYuan,
  formatCents,
  percentChange,
  shortDay,
  statusLabel,
} from './format';

describe('centsToYuan', () => {
  it('formats cents with two decimals', () => {
    expect(centsToYuan(0)).toBe('0.00');
    expect(centsToYuan(19900)).toBe('199.00');
    expect(centsToYuan(5)).toBe('0.05');
  });

  it('thousands-separates large amounts', () => {
    expect(centsToYuan(123456789)).toBe('1,234,567.89');
  });

  it('never renders NaN', () => {
    expect(centsToYuan(Number.NaN)).toBe('0.00');
  });
});

describe('formatCents', () => {
  it('adds the currency symbol by default', () => {
    expect(formatCents(99000)).toBe('¥990.00');
    expect(formatCents(99000, false)).toBe('990.00');
  });
});

describe('percentChange', () => {
  it('computes up and down swings', () => {
    expect(percentChange(120, 100)).toBe(20);
    expect(percentChange(80, 100)).toBe(-20);
    expect(percentChange(150, 200)).toBe(-25);
  });

  it('returns null when there is no baseline to compare against', () => {
    expect(percentChange(10, 0)).toBeNull();
  });

  it('rounds to one decimal', () => {
    expect(percentChange(101, 100)).toBe(1);
    expect(percentChange(1, 3)).toBe(-66.7);
  });
});

describe('statusLabel', () => {
  it('maps known order statuses to Chinese labels', () => {
    expect(statusLabel('pending_payment')).toBe('待支付');
    expect(statusLabel('completed')).toBe('已完成');
  });

  it('falls back to the raw status so new states are never blank', () => {
    expect(statusLabel('some_future_state')).toBe('some_future_state');
  });
});

describe('shortDay', () => {
  it('strips the year', () => {
    expect(shortDay('2026-11-11')).toBe('11-11');
  });

  it('passes through malformed input untouched', () => {
    expect(shortDay('oops')).toBe('oops');
  });
});
