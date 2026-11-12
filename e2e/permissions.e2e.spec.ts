import { expect, test } from '@playwright/test';
import {
  ADMIN,
  CUSTOMER,
  gotoAndExpectForbidden,
  loginAs,
  menuLink,
  OPERATOR,
} from './helpers/auth';

/**
 * RBAC regression against the real backend (plan §18 #4, #5).
 *
 * Menu visibility is asserted through `.ant-menu a[href=...]` so the checks do not
 * depend on the active locale, and direct URL access is asserted through the 403
 * page — hiding a menu is only UX, the API and the route guard are the real gate.
 */

test.describe('permissions: admin', () => {
  test('can open every guarded page', async ({ page }) => {
    await loginAs(page, ADMIN);

    // Nested menu entries only exist in the DOM once their submenu is expanded,
    // so route access — not menu markup — is what we assert for the superuser.
    const guardedPages: Array<[string, RegExp]> = [
      ['/users/list', /用户|账号/],
      ['/users/departments', /部门/],
      ['/users/roles', /角色/],
      ['/system/settings/payment', /支付/],
      ['/system/audit', /审计日志/],
      ['/finance', /财务|结算/],
    ];

    for (const [path, expected] of guardedPages) {
      await page.goto(path, { waitUntil: 'commit' }).catch(() => undefined);
      await expect(page)
        .not.toHaveURL(/exception\/403/, { timeout: 10_000 })
        .catch(() => undefined);
      await expect(page.getByText('403', { exact: true })).toHaveCount(0, {
        timeout: 20_000,
      });
      await expect(page.getByText(expected).first()).toBeVisible({
        timeout: 30_000,
      });
    }

    // 平台端已拆成独立系统（apps/platform），控制台里不应再有该菜单。
    await expect(menuLink(page, '/system/audit').first()).toBeVisible();
    await expect(page.locator('a[href="/platform/tenants"]')).toHaveCount(0);
  });
});

test.describe('permissions: operator', () => {
  test('does not get admin-only top-level menu entries', async ({ page }) => {
    await loginAs(page, OPERATOR);

    // A page the operator *is* entitled to is rendered...
    await expect(menuLink(page, '/welcome').first()).toBeVisible({
      timeout: 30_000,
    });

    // ...while platform and audit entries are absent from the sider entirely.
    for (const href of ['/system/audit', '/platform/tenants']) {
      await expect(menuLink(page, href)).toHaveCount(0);
    }
  });

  test('direct URL access to role management shows 403', async ({ page }) => {
    await loginAs(page, OPERATOR);
    await gotoAndExpectForbidden(page, '/users/roles');
  });

  test('department management URL is blocked', async ({ page }) => {
    await loginAs(page, OPERATOR);
    await gotoAndExpectForbidden(page, '/users/departments');
  });

  test('payment settings URL is blocked', async ({ page }) => {
    await loginAs(page, OPERATOR);
    await gotoAndExpectForbidden(page, '/system/settings/payment');
  });

  test('audit trail URL is blocked', async ({ page }) => {
    await loginAs(page, OPERATOR);
    await gotoAndExpectForbidden(page, '/system/audit');
  });
});

test.describe('permissions: customer', () => {
  test('cannot open the back office', async ({ page }) => {
    await loginAs(page, CUSTOMER);

    await gotoAndExpectForbidden(page, '/users/list');
  });

  test('cannot open the audit trail', async ({ page }) => {
    await loginAs(page, CUSTOMER);
    await gotoAndExpectForbidden(page, '/system/audit');
  });

  test('can browse the buyer portal', async ({ page }) => {
    await loginAs(page, CUSTOMER);
    await page.goto('/portal');
    await expect(page.getByText('C2C 商城').first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText('我的订单').first()).toBeVisible();
  });
});

test.describe('permissions: anonymous', () => {
  test('is redirected to the login page', async ({ page }) => {
    await page.goto('/users/list');
    await page.waitForURL(/\/user\/login/, { timeout: 45_000 });
    await expect(page.locator('#username')).toBeVisible();
  });
});
