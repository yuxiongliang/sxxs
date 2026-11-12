import { ShoppingCartOutlined, ShoppingOutlined } from '@ant-design/icons';
import { useModel } from '@umijs/max';
import { App, Button, Card, Tag, Typography } from 'antd';
import { addCartItem } from '@/services/commerce/api';
import type { PublicProduct } from '@/services/commerce/api';

const { Text } = Typography;

function yuan(cents: number) {
  return (cents / 100).toFixed(2);
}

/**
 * 商品卡片：站点前台的统一展示单元。
 *
 * 三个动作的登录策略（需求：按钮可见 + 未登录引导登录）：
 *   - 查看详情：公开页，直接跳；
 *   - 加入购物车 / 立即购买：需要 cart:manage / order:create，
 *     未登录时跳登录并带 redirect 回到该商品，登录后自动续上。
 */
export default function ProductCard({ product }: { product: PublicProduct }) {
  const { message } = App.useApp();
  const { initialState } = useModel('@@initialState');
  const signedIn = Boolean(initialState?.currentUser);

  const detailPath = `/products/${product.id}`;
  const sku = product.sku;
  const stock = sku?.stock ?? 0;
  const soldOut = !sku || stock <= 0;

  /** 未登录就带去登录页，登录后回到该商品详情 */
  const ensureSignedIn = () => {
    if (signedIn) return true;
    window.location.assign(
      `/user/login?redirect=${encodeURIComponent(detailPath)}`,
    );
    return false;
  };

  const handleAddCart = async () => {
    if (!ensureSignedIn() || !sku) return;
    try {
      await addCartItem({ sku_id: sku.id, quantity: 1 });
      message.success('已加入购物车');
    } catch (error) {
      message.error((error as Error)?.message || '加入购物车失败');
    }
  };

  const handleBuyNow = () => {
    if (!ensureSignedIn()) return;
    // 立即购买要填收货信息，交给详情页处理（?buy=1 自动滚到购买区）
    window.location.assign(`${detailPath}?buy=1`);
  };

  return (
    <Card
      hoverable
      styles={{ body: { padding: 16 } }}
      cover={
        product.main_image ? (
          <img
            src={product.main_image}
            alt={product.name}
            style={{ height: 160, width: '100%', objectFit: 'cover' }}
          />
        ) : (
          <div
            style={{
              height: 160,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 40,
              color: 'var(--ant-color-primary)',
              background:
                'linear-gradient(135deg, var(--ant-color-primary-bg), var(--ant-color-fill-secondary))',
            }}
          >
            <ShoppingOutlined />
          </div>
        )
      }
    >
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{product.name}</div>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {product.subtitle || '—'}
      </Text>
      <div
        style={{
          marginTop: 10,
          display: 'flex',
          alignItems: 'baseline',
          gap: 8,
        }}
      >
        <span
          style={{
            color: 'var(--ant-color-error)',
            fontSize: 18,
            fontWeight: 700,
          }}
        >
          ¥{yuan(sku?.price_cents ?? 0)}
        </span>
        <Tag
          color={stock > 0 ? 'green' : 'default'}
          style={{ marginInlineEnd: 0 }}
        >
          {stock > 0 ? `库存 ${stock}` : '已售罄'}
        </Tag>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, opacity: 0.65 }}>
        {product.shop_name ? `${product.shop_name} · ` : ''}
        {product.seller_name || ''}
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <Button size="small" onClick={() => window.location.assign(detailPath)}>
          查看详情
        </Button>
        <Button
          size="small"
          icon={<ShoppingCartOutlined />}
          disabled={soldOut}
          onClick={handleAddCart}
        >
          加入购物车
        </Button>
        <Button
          size="small"
          type="primary"
          disabled={soldOut}
          onClick={handleBuyNow}
        >
          立即购买
        </Button>
      </div>
    </Card>
  );
}
