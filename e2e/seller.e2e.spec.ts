import { expect, test } from '@playwright/test';
import { CUSTOMER, loginAs, OPERATOR } from './helpers/auth';

/**
 * Seller centre regression (plan §18 #3): the shop owner sees their own shop,
 * while a C-end buyer cannot use the seller endpoints behind the page.
 */

test.describe('seller centre', () => {
  test('shop owner sees their shop and products', async ({ page }) => {
    await loginAs(page, OPERATOR);
    await page.goto('/seller');

    // The seller centre is a standalone page (layout:false) with a header.
    await expect(page.getByText(/卖家中心/).first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/我的店铺|店铺/).first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByRole('button', { name: /发布商品|新增商品/ }).first(),
    ).toBeVisible();
  });

  test('buyer opening the seller centre gets no shop data', async ({
    page,
  }) => {
    await loginAs(page, CUSTOMER);

    const failures: string[] = [];
    page.on('response', (response) => {
      if (
        response.url().includes('/api/v1/portal/seller/') &&
        response.status() === 403
      ) {
        failures.push(response.url());
      }
    });

    await page.goto('/seller', { waitUntil: 'commit' }).catch(() => undefined);
    await page.waitForTimeout(4000);

    // The backend must refuse the seller APIs for a C-end customer.
    expect(failures.length).toBeGreaterThan(0);
  });

  test('admin can open the seller management page', async ({ page }) => {
    await loginAs(page, { username: 'admin', password: 'ant.design' });
    await page.goto('/sellers');
    await expect(page.getByText('403', { exact: true })).toHaveCount(0, {
      timeout: 20_000,
    });
    await expect(page.getByText(/卖家/).first()).toBeVisible({
      timeout: 30_000,
    });
  });
});
