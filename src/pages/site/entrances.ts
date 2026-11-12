/**
 * 「进入控制台」悬停菜单：只列**平台级领域入口**，不列页面级菜单。
 *
 * 为什么只留两级：权限清单（用户/商品/订单/财务…）属于控制台内部导航，
 * 放在落地页的悬停菜单里既长又容易点到 403；访客在这里只需要知道
 * 「我能去哪个域」。
 *
 * 抽成纯配置 + 纯函数，组件只负责渲染，且可脱离浏览器单测。
 */

export interface AccessFlags {
  [key: string]: boolean | undefined;
}

export interface Entrance {
  key: string;
  labelId: string;
  path: string;
  /** 对应 src/access.ts 中的权限标志名 */
  accessKey: string;
}

export const ENTRANCES: Entrance[] = [
  {
    key: 'admin',
    labelId: 'site.entrance.admin',
    path: '/dashboard/analysis',
    accessKey: 'canDashboard',
  },
  {
    key: 'mall',
    labelId: 'site.entrance.mall',
    path: '/portal',
    accessKey: 'canUsePortal',
  },
];

/** 只返回当前账号真正有权进入的领域 */
export function visibleEntrances(access: AccessFlags): Entrance[] {
  return ENTRANCES.filter((entry) => Boolean(access[entry.accessKey]));
}
