/**
 * 落地页全局搜索的纯逻辑（不含 React，可直接单测）。
 *
 * 为什么用本地索引而不是后端检索：落地页内容是**可枚举**的（导航、能力、
 * 模块、文档入口），规模只有几十条，走网络反而增加延迟与失败面。
 * 后续内容变多时再把 searchEntries 换成异步接口即可，组件无需改动。
 */

export type SearchGroup = 'nav' | 'feature' | 'module' | 'doc';

export interface SearchEntry {
  id: string;
  group: SearchGroup;
  /** 展示标题（已国际化） */
  title: string;
  /** 副标题/说明（已国际化） */
  desc?: string;
  /** 跳转地址：站内路径或 http(s) 外链 */
  href: string;
  /** 额外匹配词（中英文别名、模块 key 等） */
  keywords?: string[];
}

/** 分数越高越靠前；0 表示不匹配 */
export function scoreEntry(entry: SearchEntry, rawQuery: string): number {
  const query = rawQuery.trim().toLowerCase();
  if (!query) return 0;

  const title = entry.title.toLowerCase();
  const desc = (entry.desc ?? '').toLowerCase();
  const keywords = (entry.keywords ?? []).map((k) => k.toLowerCase());

  let score = 0;
  if (title === query) score += 100;
  else if (title.startsWith(query)) score += 80;
  else if (title.includes(query)) score += 60;

  for (const keyword of keywords) {
    if (keyword === query) score += 50;
    else if (keyword.includes(query)) score += 40;
  }

  if (desc.includes(query)) score += 20;

  // 多词查询：所有词都命中标题才加分，避免「a b」只命中 a 就排到前面
  const tokens = query.split(/\s+/).filter(Boolean);
  if (
    tokens.length > 1 &&
    tokens.every((t) => title.includes(t) || desc.includes(t))
  ) {
    score += 30;
  }

  return score;
}

export function searchEntries(
  entries: SearchEntry[],
  query: string,
  limit = 12,
): SearchEntry[] {
  if (!query.trim()) return [];
  return entries
    .map((entry) => ({ entry, score: scoreEntry(entry, query) }))
    .filter((item) => item.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map((item) => item.entry);
}

/** 按分组归并，保持组内既有顺序（供 UI 分组展示） */
export function groupEntries(
  entries: SearchEntry[],
): Array<[SearchGroup, SearchEntry[]]> {
  const order: SearchGroup[] = ['nav', 'feature', 'module', 'doc'];
  const map = new Map<SearchGroup, SearchEntry[]>();
  for (const entry of entries) {
    const bucket = map.get(entry.group) ?? [];
    bucket.push(entry);
    map.set(entry.group, bucket);
  }
  return order
    .filter((g) => map.has(g))
    .map((g) => [g, map.get(g) as SearchEntry[]]);
}

/**
 * 校验跳转目标，只允许两类：
 *   - 页内锚点：#features
 *   - 同源绝对路径：/dashboard/analysis
 *
 * 其余（协议相对 //evil.com、javascript:、任意外部站点）一律拒绝。
 * 即使索引是代码内置的，也不让一个写错的 href 变成开放重定向。
 */
export function resolveSafeHref(href: string): string | null {
  if (!href) return null;
  if (href.startsWith('#')) return href.length > 1 ? href : null;
  // 「//host」是协议相对 URL，会被当成外部站点，必须先排除
  if (href.startsWith('//')) return null;
  if (href.startsWith('/')) return href;
  return null;
}
