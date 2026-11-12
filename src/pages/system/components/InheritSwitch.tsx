import { Alert, Segmented, Space, Tag } from 'antd';

export type SettingSource = 'inherit' | 'override';

interface InheritSwitchProps {
  source: SettingSource;
  effectiveSource?: string;
  inheritAllowed?: boolean;
  platformActive?: boolean;
  policyLocked?: boolean;
  maskedFields?: string[];
  disabled?: boolean;
  onChange: (source: SettingSource) => void;
}

/**
 * 「跟随系统 / 自定义」开关。
 *
 * 三个状态必须说清楚，否则用户无法理解「我选了跟随系统，怎么用的是自己的配置」：
 *   1. 平台已启用       → 真的在用平台配置，密钥已脱敏
 *   2. 平台未启用       → 回落到你自己的历史配置（兜底，不是 bug）
 *   3. 平台锁定         → 只能跟随，不可自定义
 */
export default function InheritSwitch({
  source,
  effectiveSource,
  inheritAllowed = true,
  platformActive = false,
  policyLocked = false,
  maskedFields,
  disabled = false,
  onChange,
}: InheritSwitchProps) {
  return (
    <Space
      direction="vertical"
      size={8}
      style={{ width: '100%', marginBottom: 16 }}
    >
      <Segmented
        value={source}
        disabled={disabled}
        onChange={(value) => onChange(value as SettingSource)}
        options={[
          {
            value: 'inherit',
            label: '跟随系统',
            disabled: !inheritAllowed,
          },
          { value: 'override', label: '自定义', disabled: policyLocked },
        ]}
      />

      {policyLocked ? (
        <Alert
          type="info"
          showIcon
          title="平台已锁定该配置"
          description="为保证全站合规，这类配置只能跟随平台，不能自定义。"
        />
      ) : null}

      {!policyLocked && !inheritAllowed ? (
        <Alert
          type="warning"
          showIcon
          title="该配置不支持跟随系统"
          description="平台不代收业务款，支付账号必须由你自己填写。"
        />
      ) : null}

      {source === 'inherit' && policyLocked ? null : source === 'inherit' &&
        !platformActive ? (
        <Alert
          type="warning"
          showIcon
          title="平台尚未启用该类统一配置"
          description="当前实际使用的是你自己保存过的配置（兜底）。填好并保存你的配置即可正常使用。"
        />
      ) : null}

      {source === 'inherit' && !policyLocked && platformActive ? (
        <Alert
          type="success"
          showIcon
          title="已跟随平台统一配置"
          description={
            maskedFields && maskedFields.length
              ? `平台密钥（${maskedFields.join('、')}）不会下发给租户。`
              : undefined
          }
        />
      ) : null}

      {effectiveSource === 'tenant_fallback' ? (
        <Tag color="orange">当前生效来源：你的历史配置</Tag>
      ) : null}
    </Space>
  );
}
