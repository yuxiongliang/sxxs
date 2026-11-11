import { expect, type Page, test } from '@playwright/test';
import { CUSTOMER, loginAs } from './helpers/auth';

/**
 * Pick a product card whose「加入购物车」action is actually enabled.
 *
 * Demo stock is finite and earlier runs consume it, so the specs must not assume
 * the first card is purchasable.
 */
async function pickInStockProduct(page: Page) {
  // Wait for the product grid to render before counting cards.
  await page
    .getByRole('button', { name: '加入购物车' })
    .first()
    .waitFor({ state: 'attached', timeout: 30_000 })
    .catch(() => undefined);

  const cards = page.locator('.ant-card');
  const total = await cards.count();
  for (let index = 0; index < total; index += 1) {
    const card = cards.nth(index);
    const button = card.getByRole('button', { name: '加入购物车' });
    if ((await button.count()) === 0) continue;
    if (await button.first().isEnabled()) {
      const name = await card
        .locator('.ant-card-meta-title')
        .first()
        .innerText()
        .catch(() => '');
      return { card, name };
    }
  }
  return null;
}

/**
 * Buyer journey against the real backend (plan §18 #1, #6, #15):
 * browse -> detail -> cart -> checkout -> payment result, plus the address book.
 */

test.describe('portal: buyer journey', () => {
  test('browses products and opens a product detail page', async ({ page }) => {
    await loginAs(page, CUSTOMER);
    await page.goto('/portal');

    await expect(page.getByText('C2C 商城').first()).toBeVisible({
      timeout: 30_000,
    });
    const detailLink = page.getByRole('button', { name: '查看详情' }).first();
    await expect(detailLink).toBeVisible({ timeout: 30_000 });
    await detailLink.click();

    await expect(page).toHaveURL(/\/portal\/products\/\d+/, {
      timeout: 30_000,
    });
    await expect(page.getByText('卖家：').first()).toBeVisible();
    await expect(
      page.getByRole('button', { name: '加入购物车' }).first(),
    ).toBeVisible();
  });

  test('adds a product to the cart and sees it listed', async ({ page }) => {
    await loginAs(page, CUSTOMER);
    await page.goto('/portal');

    const picked = await pickInStockProduct(page);
    test.skip(!picked, '演示商品均已售罄，跳过加购用例');
    const name = picked!.name;

    await picked!.card
      .getByRole('button', { name: '加入购物车' })
      .first()
      .click();
    await expect(page.getByText('已加入购物车').first()).toBeVisible({
      timeout: 20_000,
    });

    await page.goto('/portal/cart');
    await expect(
      page.getByText('购物车', { exact: false }).first(),
    ).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(name).first()).toBeVisible({ timeout: 30_000 });
  });

  test('checks out the cart and completes the mock payment', async ({
    page,
  }) => {
    await loginAs(page, CUSTOMER);

    // Make sure there is at least one line to settle.
    await page.goto('/portal');
    await page.getByRole('button', { name: '加入购物车' }).first().click();
    await expect(page.getByText('已加入购物车').first()).toBeVisible({
      timeout: 20_000,
    });

    await page.goto('/portal/cart');
    await page.getByRole('button', { name: '去结算' }).click();
    await expect(page.getByText('确认订单').first()).toBeVisible({
      timeout: 20_000,
    });

    await page.getByLabel('收货人').fill('E2E 收货人');
    await page.getByLabel('联系电话').fill('13900001111');
    await page.getByLabel('详细地址').fill('E2E 自动化路 1 号');
    await page.getByRole('button', { name: '提交订单' }).click();

    // Order created -> the app navigates to the payment result page.
    await expect(page).toHaveURL(/\/portal\/payment-result\?orderId=\d+/, {
      timeout: 40_000,
    });

    const payButton = page.getByRole('button', { name: '立即支付（模拟）' });
    if (await payButton.isVisible().catch(() => false)) {
      await payButton.click();
      await expect(page.getByText('支付成功').first()).toBeVisible({
        timeout: 30_000,
      });
    }
    await expect(page.getByText(/订单号/).first()).toBeVisible({
      timeout: 30_000,
    });
  });

  test('manages the address book', async ({ page }) => {
    await loginAs(page, CUSTOMER);
    await page.goto('/portal/addresses');

    await expect(page.getByText('我的收货地址').first()).toBeVisible({
      timeout: 30_000,
    });

    const unique = `E2E 地址 ${Date.now()}`;
    await page.getByRole('button', { name: '新增地址' }).first().click();
    await page.getByLabel('收货人').fill('地址测试');
    await page.getByLabel('联系电话').fill('13800002222');
    await page.getByLabel('省').fill('广东省');
    await page.getByLabel('市').fill('深圳市');
    await page.getByLabel('区').fill('南山区');
    await page.getByLabel('详细地址').fill(unique);
    await page.getByRole('button', { name: /保\s*存/ }).click();

    await expect(page.getByText(unique).first()).toBeVisible({
      timeout: 30_000,
    });
  });
});
