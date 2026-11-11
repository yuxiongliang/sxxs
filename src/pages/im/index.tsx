import {
  MessageOutlined,
  PictureOutlined,
  SendOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useModel } from '@umijs/max';
import {
  App,
  Button,
  Card,
  Col,
  Empty,
  Image,
  Input,
  Modal,
  Row,
  Space,
  Tag,
  Typography,
  Upload,
} from 'antd';
import React, { useEffect, useState } from 'react';
import {
  getReadState,
  getWsTicket,
  listConversations,
  listMessages,
  markConversationRead,
  reportMessage,
  sendImageMessage,
  sendMessage,
} from '@/services/im/api';
import type { MessageRecord } from '@/services/im/types';
import { uploadAttachment } from '@/services/system/api';
import SettingPage from '../system/components/SettingPage';

const ImPage: React.FC = () => {
  const { message } = App.useApp();
  const { initialState } = useModel('@@initialState');
  const currentUserId = Number(initialState?.currentUser?.userid ?? 0);
  const [selectedId, setSelectedId] = useState<number>();
  const [input, setInput] = useState('');
  const [reportTarget, setReportTarget] = useState<MessageRecord>();
  const [reportReason, setReportReason] = useState('');

  const { data: conversations, refetch: refetchConversations } = useQuery({
    queryKey: ['im-conversations'],
    queryFn: listConversations,
    refetchInterval: 3000,
  });

  useEffect(() => {
    if (!selectedId && conversations?.length)
      setSelectedId(conversations[0].id);
  }, [conversations, selectedId]);

  const { data: messages, refetch: refetchMessages } = useQuery({
    queryKey: ['im-messages', selectedId],
    queryFn: () => listMessages(selectedId as number),
    enabled: !!selectedId,
    refetchInterval: 2000,
  });

  const { data: readState } = useQuery({
    queryKey: ['im-read-state', selectedId],
    queryFn: () => getReadState(selectedId as number),
    enabled: !!selectedId,
    refetchInterval: 4000,
  });

  // Report a read receipt for the newest message we can see, which clears the
  // unread badge and lets the peer display「已读」.
  useEffect(() => {
    if (!selectedId || !messages?.length) return;
    const lastSeq = messages[messages.length - 1].seq;
    if (lastSeq <= (readState?.my_last_read_seq ?? 0)) return;
    markConversationRead(selectedId, lastSeq)
      .then(() => refetchConversations())
      .catch(() => undefined);
  }, [selectedId, messages, readState?.my_last_read_seq, refetchConversations]);

  useEffect(() => {
    let socket: WebSocket | undefined;
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;

    const connect = async () => {
      try {
        const { ticket } = await getWsTicket();
        if (closed) return;
        const base = process.env.WS_BASE_URL || 'ws://127.0.0.1:9000';
        socket = new WebSocket(`${base}/api/v1/im/ws?ticket=${ticket}`);
        socket.onmessage = () => {
          refetchMessages();
          refetchConversations();
        };
        socket.onclose = () => {
          if (!closed) retryTimer = setTimeout(connect, 3000);
        };
      } catch {
        if (!closed) retryTimer = setTimeout(connect, 5000);
      }
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      socket?.close();
    };
  }, [refetchConversations, refetchMessages]);

  const handleSend = async () => {
    if (!selectedId || !input.trim()) return;
    try {
      await sendMessage(selectedId, input.trim(), `web-${Date.now()}`);
      setInput('');
      await refetchMessages();
      await refetchConversations();
    } catch (error: any) {
      message.error(error?.message || '发送失败');
    }
  };

  const handleSendImage = async (file: File) => {
    if (!selectedId) return;
    try {
      const attachment = await uploadAttachment(file, 'im');
      await sendImageMessage(selectedId, attachment.id, `img-${Date.now()}`);
      await refetchMessages();
      await refetchConversations();
    } catch (error: any) {
      message.error(error?.message || '图片发送失败');
    }
  };

  const submitReport = async () => {
    if (!reportTarget || !reportReason.trim()) {
      message.warning('请填写举报原因');
      return;
    }
    try {
      await reportMessage(reportTarget.id, reportReason.trim());
      message.success('举报已提交，等待运营审核');
      setReportTarget(undefined);
      setReportReason('');
    } catch (error: any) {
      message.error(error?.message || '举报失败');
    }
  };

  return (
    <SettingPage
      title="消息中心"
      subTitle="C2C 买卖家即时沟通"
      icon={<MessageOutlined />}
    >
      <Row gutter={16}>
        <Col span={7}>
          <Card title="会话" size="small" styles={{ body: { padding: 0 } }}>
            {conversations?.length ? (
              conversations.map((item) => (
                <div
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                  style={{
                    cursor: 'pointer',
                    padding: '12px 16px',
                    borderBottom: '1px solid #f0f0f0',
                    background: selectedId === item.id ? '#e6f4ff' : undefined,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>会话 #{item.id}</div>
                    <div style={{ color: '#8c8c8c', fontSize: 12 }}>
                      买家 {item.buyer_id} / 卖家 {item.seller_id}
                    </div>
                  </div>
                  {item.seller_unread_count > 0 ||
                  item.buyer_unread_count > 0 ? (
                    <Tag color="red">未读</Tag>
                  ) : null}
                </div>
              ))
            ) : (
              <Empty description="暂无会话" style={{ padding: 24 }} />
            )}
          </Card>
        </Col>
        <Col span={17}>
          <Card
            title={selectedId ? `会话 #${selectedId}` : '请选择会话'}
            size="small"
            styles={{
              body: {
                minHeight: 520,
                display: 'flex',
                flexDirection: 'column',
              },
            }}
          >
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                padding: 12,
                background: '#fafafa',
                borderRadius: 8,
              }}
            >
              {messages?.length ? (
                messages.map((item) => {
                  const mine = item.sender_id === currentUserId;
                  return (
                    <div
                      key={item.id}
                      style={{
                        display: 'flex',
                        justifyContent: mine ? 'flex-end' : 'flex-start',
                        marginBottom: 10,
                      }}
                    >
                      <div
                        style={{
                          maxWidth: '70%',
                          padding: '8px 12px',
                          borderRadius: 8,
                          background: mine ? '#1677ff' : '#fff',
                          color: mine ? '#fff' : '#000',
                          boxShadow: '0 1px 2px rgba(0,0,0,0.08)',
                        }}
                      >
                        <div
                          style={{
                            fontSize: 12,
                            opacity: 0.7,
                            marginBottom: 2,
                          }}
                        >
                          用户 {item.sender_id} · seq {item.seq}
                        </div>
                        {item.type === 'image' && item.payload?.url ? (
                          <Image
                            src={item.payload.url}
                            width={180}
                            style={{ borderRadius: 6 }}
                          />
                        ) : (
                          item.content
                        )}
                        {item.content && item.type === 'image' ? (
                          <div style={{ fontSize: 12, marginTop: 4 }}>
                            {item.content}
                          </div>
                        ) : null}
                        {!mine ? (
                          <div style={{ marginTop: 4 }}>
                            <Typography.Link
                              style={{
                                fontSize: 12,
                                color: mine ? '#fff' : undefined,
                              }}
                              onClick={() => {
                                setReportTarget(item);
                                setReportReason('');
                              }}
                            >
                              <WarningOutlined /> 举报
                            </Typography.Link>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })
              ) : (
                <Empty description="暂无消息" />
              )}
            </div>
            <Space.Compact style={{ marginTop: 12, width: '100%' }}>
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onPressEnter={handleSend}
                placeholder="输入消息，Enter 发送"
              />
              <Upload
                showUploadList={false}
                accept="image/*"
                beforeUpload={(file) => {
                  handleSendImage(file as File);
                  return false;
                }}
              >
                <Button icon={<PictureOutlined />}>图片</Button>
              </Upload>
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
              >
                发送
              </Button>
            </Space.Compact>
            <Typography.Text type="secondary" style={{ marginTop: 6 }}>
              WebSocket 实时推送中；断线时自动降级为 2 秒轮询。
              {readState
                ? ` 对方已读至 seq ${readState.peer_last_read_seq}。`
                : ''}
            </Typography.Text>
          </Card>
        </Col>
      </Row>
      <Modal
        title="举报违规消息"
        open={!!reportTarget}
        onCancel={() => setReportTarget(undefined)}
        onOk={submitReport}
        okText="提交举报"
      >
        <Typography.Paragraph type="secondary">
          举报后运营会在「消息审核」中处理，确认违规的消息将对普通用户隐藏。
        </Typography.Paragraph>
        <Input.TextArea
          rows={3}
          value={reportReason}
          onChange={(e) => setReportReason(e.target.value)}
          placeholder="请描述违规原因，例如：广告引流、辱骂、诈骗"
        />
      </Modal>
    </SettingPage>
  );
};

export default ImPage;
