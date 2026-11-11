import { describe, expect, it } from 'vitest';
import { parseStoredMode, resolveMode } from './index';

describe('resolveMode', () => {
  it('returns the explicit choice regardless of the system preference', () => {
    expect(resolveMode('light', true)).toBe('light');
    expect(resolveMode('dark', false)).toBe('dark');
  });

  it('follows the system preference in system mode', () => {
    expect(resolveMode('system', true)).toBe('dark');
    expect(resolveMode('system', false)).toBe('light');
  });
});

describe('parseStoredMode', () => {
  it('accepts the three valid modes', () => {
    expect(parseStoredMode('light')).toBe('light');
    expect(parseStoredMode('dark')).toBe('dark');
    expect(parseStoredMode('system')).toBe('system');
  });

  it('falls back to system for missing or unknown values', () => {
    expect(parseStoredMode(null)).toBe('system');
    expect(parseStoredMode(undefined)).toBe('system');
    expect(parseStoredMode('')).toBe('system');
    expect(parseStoredMode('token')).toBe('system');
  });
});
