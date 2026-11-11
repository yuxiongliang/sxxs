import { describe, expect, it } from 'vitest';
import type { SearchEntry } from './search';
import {
  groupEntries,
  resolveSafeHref,
  scoreEntry,
  searchEntries,
} from './search';

const ENTRIES: SearchEntry[] = [
  { id: 'nav-features', group: 'nav', title: '平台能力', href: '#features' },
  { id: 'nav-modules', group: 'nav', title: '功能模块', href: '#modules' },
  {
    id: 'feature-finance',
    group: 'feature',
    title: '佣金与结算',
    desc: '佣金规则可按卖家/分类配置，提现审核与结算批次',
    href: '/finance',
    keywords: ['commission', 'payout', '结算'],
  },
  {
    id: 'module-im',
    group: 'module',
    title: '即时通讯',
    href: '/messages',
    keywords: ['im', 'chat'],
  },
  { id: 'doc-readme', group: 'doc', title: '项目自述', href: 'README.md' },
];

describe('scoreEntry', () => {
  it('returns 0 for an empty query so nothing matches by default', () => {
    expect(scoreEntry(ENTRIES[0], '   ')).toBe(0);
  });

  it('ranks an exact title match above a substring match', () => {
    const exact = scoreEntry(ENTRIES[1], '功能模块');
    const partial = scoreEntry(ENTRIES[2], '功能');
    expect(exact).toBeGreaterThan(partial);
  });

  it('matches keywords and description as a fallback', () => {
    expect(scoreEntry(ENTRIES[2], 'commission')).toBeGreaterThan(0);
    expect(scoreEntry(ENTRIES[2], '提现审核')).toBeGreaterThan(0);
    expect(scoreEntry(ENTRIES[4], '自述')).toBeGreaterThan(0);
  });

  it('is case insensitive for latin queries', () => {
    expect(scoreEntry(ENTRIES[3], 'CHAT')).toBeGreaterThan(0);
  });

  it('returns 0 when nothing matches', () => {
    expect(scoreEntry(ENTRIES[0], 'zzzz-not-exist')).toBe(0);
  });
});

describe('searchEntries', () => {
  it('returns an empty list for a blank query (no accidental full dump)', () => {
    expect(searchEntries(ENTRIES, '')).toEqual([]);
    expect(searchEntries(ENTRIES, '   ')).toEqual([]);
  });

  it('sorts by score and respects the limit', () => {
    const results = searchEntries(ENTRIES, '模块');
    expect(results[0].id).toBe('nav-modules');
    expect(searchEntries(ENTRIES, '模块', 1)).toHaveLength(1);
  });

  it('finds entries across different groups', () => {
    const ids = searchEntries(ENTRIES, '结算').map((e) => e.id);
    expect(ids).toContain('feature-finance');
  });
});

describe('groupEntries', () => {
  it('groups by the fixed order nav > feature > module > doc', () => {
    const grouped = groupEntries(ENTRIES);
    expect(grouped.map(([g]) => g)).toEqual([
      'nav',
      'feature',
      'module',
      'doc',
    ]);
  });

  it('drops empty groups', () => {
    const grouped = groupEntries([ENTRIES[3]]);
    expect(grouped).toHaveLength(1);
    expect(grouped[0][0]).toBe('module');
  });
});

describe('resolveSafeHref（防止开放重定向）', () => {
  it('allows in-page anchors and same-origin paths', () => {
    expect(resolveSafeHref('#features')).toBe('#features');
    expect(resolveSafeHref('/dashboard/analysis')).toBe('/dashboard/analysis');
  });

  it('rejects protocol-relative and absolute external URLs', () => {
    expect(resolveSafeHref('//evil.example.com')).toBeNull();
    expect(resolveSafeHref('https://evil.example.com')).toBeNull();
    expect(resolveSafeHref('http://evil.example.com')).toBeNull();
  });

  it('rejects script-ish and empty targets', () => {
    expect(resolveSafeHref('javascript:alert(1)')).toBeNull();
    expect(resolveSafeHref('data:text/html,x')).toBeNull();
    expect(resolveSafeHref('')).toBeNull();
    expect(resolveSafeHref('#')).toBeNull();
  });
});
