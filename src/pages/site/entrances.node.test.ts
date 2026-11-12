import { describe, expect, it } from 'vitest';
import { ENTRANCES, visibleEntrances } from './entrances';

describe('ENTRANCES', () => {
  it('只有平台级入口，不含页面级菜单', () => {
    expect(ENTRANCES).toHaveLength(2);
    expect(ENTRANCES.map((e) => e.key)).toEqual(['admin', 'mall']);
  });

  it('每个入口都有 i18n key 与站内路径', () => {
    for (const entry of ENTRANCES) {
      expect(entry.labelId.startsWith('site.entrance.')).toBe(true);
      expect(entry.path.startsWith('/')).toBe(true);
    }
  });
});

describe('visibleEntrances', () => {
  it('管理员：后台管理 + 买卖中心', () => {
    const admin = { canDashboard: true, canUsePortal: true };
    expect(visibleEntrances(admin).map((e) => e.key)).toEqual([
      'admin',
      'mall',
    ]);
  });

  it('纯买家：只有买卖中心', () => {
    const buyer = { canDashboard: false, canUsePortal: true };
    expect(visibleEntrances(buyer).map((e) => e.key)).toEqual(['mall']);
  });

  it('套餐不含 portal 时不显示买卖中心', () => {
    const staff = { canDashboard: true, canUsePortal: false };
    expect(visibleEntrances(staff).map((e) => e.key)).toEqual(['admin']);
  });

  it('没有任何入口时返回空数组', () => {
    expect(visibleEntrances({})).toEqual([]);
  });
});
