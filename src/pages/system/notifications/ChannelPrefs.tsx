import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { App, Card, Space, Switch, Table, Tag, Typography } from 'antd';
import type { NotificationTemplateBrief } from '@/services/system/api';
import {
  getNotificationPrefs,
  listNotificationTemplates,
  saveNotificationPref,
} from '@/services/system/api';

const CHANNEL_LABEL: Record<string, string> = {
  inbox: '站内信',
  sms: '短信',
  email: '邮件',
};

/**
 * 渠道开关 + 可用模板说明。
 *
 * 站内信由后端标 mandatory，这里置灰不可关 —— 欠费/安全/合规通知必须送达，
 * 不是租户可以选择的。模板本身由平台统一维护，租户只读。
 */
export default function ChannelPrefs() {
  const { message } = App.useApp();
  const queryClient = useQueryClient();

  const prefs = useQuery({
    queryKey: ['notification-prefs'],
    queryFn: getNotificationPrefs,
  });
  const templates = useQuery({
    queryKey: ['notification-templates-brief'],
    queryFn: listNotificationTemplates,
  });

  const save = useMutation({
    mutationFn: (input: { channel: string; enabled: boolean }) =>
      saveNotificationPref(input.channel, input.enabled),
    onSuccess: () => {
      message.success('渠道设置已保存');
      queryClient.invalidateQueries({ queryKey: ['notification-prefs'] });
    },
    onError: (error: Error) => message.error(error.message),
  });

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card size="small" title="通知渠道">
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {(prefs.data?.channels ?? []).map((item) => (
            <Space key={item.channel} align="center">
              <Typography.Text style={{ width: 72 }}>
                {CHANNEL_LABEL[item.channel] ?? item.channel}
              </Typography.Text>
              <Switch
                checked={item.mandatory ? true : item.enabled}
                disabled={item.mandatory || save.isPending}
                onChange={(checked) =>
                  save.mutate({ channel: item.channel, enabled: checked })
                }
              />
              {item.mandatory ? <Tag color="red">强制送达</Tag> : null}
            </Space>
          ))}
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            站内信承载欠费、安全与合规通知，不能关闭；短信与邮件可按需关闭。
          </Typography.Text>
        </Space>
      </Card>

      <Card size="small" title="会发给买家的通知（模板由平台维护）">
        <Table<NotificationTemplateBrief>
          rowKey="code"
          size="small"
          loading={templates.isLoading}
          dataSource={templates.data ?? []}
          pagination={false}
          columns={[
            { title: '编码', dataIndex: 'code', width: 180 },
            { title: '名称', dataIndex: 'name', width: 180 },
            {
              title: '渠道',
              dataIndex: 'channel',
              width: 90,
              render: (value: string) => <Tag>{CHANNEL_LABEL[value] ?? value}</Tag>,
            },
            {
              title: '变量',
              dataIndex: 'variables',
              render: (value: string[]) =>
                (value ?? []).map((name) => <Tag key={name}>{name}</Tag>),
            },
          ]}
        />
      </Card>
    </Space>
  );
}
