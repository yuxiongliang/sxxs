/**
 * @see https://umijs.org/docs/max/access#access
 * */
export default function access(
  initialState:
    | {
        currentUser?: API.CurrentUser;
        permissions?: string[];
        roles?: string[];
        /** Plan feature keys from GET /api/v1/tenant/subscription. */
        features?: string[];
      }
    | undefined,
) {
  const permissions = new Set(initialState?.permissions ?? []);
  const roles = new Set(initialState?.roles ?? []);

  // Plan features come from the tenant's subscription. `undefined` means "not
  // loaded" (billing API down or still fetching) and fails **open**, so a
  // billing outage can never lock operators out of the console; an explicitly
  // empty list is authoritative and hides every gated module.
  const planFeatures = initialState?.features;
  const hasFeature = (key: string) =>
    planFeatures === undefined || planFeatures.includes(key);

  const canImRead = permissions.has('im:conversation:read');
  const canPayoutRead = permissions.has('payout:read');

  return {
    canAdmin:
      roles.has('admin') ||
      roles.has('platform_admin') ||
      roles.has('tenant_owner') ||
      permissions.has('role:manage'),
    canDashboard: permissions.has('dashboard:read'),
    canSellerRead: permissions.has('seller:read'),
    canProductRead: permissions.has('product:read'),
    canProductManage:
      permissions.has('product:manage') || permissions.has('product:moderate'),
    canOrderReadTenant: permissions.has('order:read:tenant'),
    canUserRead: permissions.has('user:read'),
    canUserWrite: permissions.has('user:write'),
    canDepartmentManage: permissions.has('department:manage'),
    canRoleManage: permissions.has('role:manage'),
    // Platform-scoped: never granted to a tenant role. Mirrors the backend
    // `platform:tenant:read` / `platform:tenant:manage` permission codes.
    canAuditRead: permissions.has('audit:read'),
    canPayoutRead,
    canPayoutManage: permissions.has('payout:manage'),
    canImRead,
    canImSend: permissions.has('im:message:send'),
    canAttachmentRead: permissions.has('attachment:read'),
    canAttachmentUpload: permissions.has('attachment:upload'),
    canAttachmentDelete: permissions.has('attachment:delete'),
    canNotificationRead: permissions.has('notification:read'),
    canNotificationSend: permissions.has('notification:send'),
    canSettings:
      permissions.has('setting:payment') ||
      permissions.has('setting:sms') ||
      permissions.has('setting:email') ||
      permissions.has('setting:storage'),
    canPaymentSetting: permissions.has('setting:payment'),
    canSmsSetting: permissions.has('setting:sms'),
    canEmailSetting: permissions.has('setting:email'),
    canStorageSetting: permissions.has('setting:storage'),
    canAmapSetting: permissions.has('setting:amap'),
    canAmapRead: permissions.has('amap:read'),
    canBrandManage: permissions.has('tenant:brand:manage'),
    // Plan feature gates: a module needs BOTH the permission above and the
    // feature key sold in the tenant's plan. Routes use these; the raw
    // permission flags stay for older call sites.
    canUsePortal: hasFeature('portal'),
    canUseIm: hasFeature('im') && canImRead,
    canUseFinance: hasFeature('finance') && canPayoutRead,
  };
}
