import { expect, type Page } from '@playwright/test';

export interface Credentials {
  username: string;
  password: string;
}

export const ADMIN: Credentials = { username: 'admin', password: 'ant.design' };
export const OPERATOR: Credentials = {
  username: 'lisi',
  password: 'Antd@123456',
};
export const CUSTOMER: Credentials = {
  username: 'e2e-shop@example.com',
  password: 'Buyer@123456',
};

/** Log in through the real /api/v1/auth/login endpoint. */
export async function loginAs(page: Page, credentials: Credentials) {
  await page.goto('/user/login');
  await page.locator('#username').fill(credentials.username);
  await page.locator('#password').fill(credentials.password);
  // antd inserts a space between two CJK characters ("登 录"), so match loosely
  // and fall back to the primary submit button.
  const submit = page.locator(
    'button.ant-btn-primary[type="submit"], button.ant-btn-primary',
  );
  await submit.first().click();

  // The app redirects away from the login page once the session is stored.
  await page.waitForURL((url) => !url.pathname.startsWith('/user/login'), {
    timeout: 45_000,
  });
  await expect(page.locator('#username')).toHaveCount(0);
}

/** Menu entries are asserted by href so the check is locale independent. */
export function menuLink(page: Page, href: string) {
  return page.locator(
    `.ant-menu a[href="${href}"], .ant-menu a[href$="${href}"]`,
  );
}

/**
 * Navigate to a guarded route that must be refused.
 *
 * A failing `access` guard redirects client-side, which makes `page.goto` reject
 * with `net::ERR_ABORTED`; the 403 page still renders, so the abort is expected.
 */
export async function gotoAndExpectForbidden(page: Page, path: string) {
  await page.goto(path, { waitUntil: 'commit' }).catch(() => undefined);
  await expect(page.getByText('403', { exact: true }).first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page
      .getByText(/抱歉，你无权访问该页面|not authorized to access this page/i)
      .first(),
  ).toBeVisible();
  // The login form must never be what we are looking at.
  await expect(page.locator('#username')).toHaveCount(0);
}
