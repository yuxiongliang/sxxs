import { request } from '@umijs/max';
import type { ApiResponse } from '@/services/system/types';
import type {
  ConversationRecord,
  ImReportRecord,
  MessageRecord,
  ReadState,
} from './types';

async function unwrap<T>(promise: Promise<ApiResponse<T>>): Promise<T> {
  const response = await promise;
  if (response.code !== 200) throw new Error(response.message || '请求失败');
  return response.data;
}

export async function getWsTicket() {
  return unwrap<{ ticket: string; expires_in: number }>(
    request('/api/v1/im/ws-ticket', { method: 'POST' }),
  );
}

export async function listConversations() {
  return unwrap<ConversationRecord[]>(
    request('/api/v1/im/conversations', { method: 'GET' }),
  );
}

export async function listMessages(conversationId: number, afterSeq = 0) {
  return unwrap<MessageRecord[]>(
    request(`/api/v1/im/conversations/${conversationId}/messages`, {
      method: 'GET',
      params: { after_seq: afterSeq },
    }),
  );
}

export async function sendMessage(
  conversationId: number,
  content: string,
  clientMsgId: string,
) {
  return unwrap<MessageRecord>(
    request(`/api/v1/im/conversations/${conversationId}/messages`, {
      method: 'POST',
      data: { content, client_msg_id: clientMsgId },
    }),
  );
}

export async function sendImageMessage(
  conversationId: number,
  attachmentId: number,
  clientMsgId: string,
  caption = '',
) {
  return unwrap<MessageRecord>(
    request(`/api/v1/im/conversations/${conversationId}/messages`, {
      method: 'POST',
      data: {
        type: 'image',
        attachment_id: attachmentId,
        content: caption,
        client_msg_id: clientMsgId,
      },
    }),
  );
}

export async function markConversationRead(conversationId: number, seq: number) {
  return unwrap<ReadState>(
    request(`/api/v1/im/conversations/${conversationId}/read`, {
      method: 'POST',
      data: { seq },
    }),
  );
}

export async function getReadState(conversationId: number) {
  return unwrap<ReadState>(
    request(`/api/v1/im/conversations/${conversationId}/read-state`, {
      method: 'GET',
    }),
  );
}

export async function reportMessage(messageId: number, reason: string) {
  return unwrap<ImReportRecord>(
    request(`/api/v1/im/messages/${messageId}/report`, {
      method: 'POST',
      data: { reason },
    }),
  );
}

export async function listImReports(status?: string) {
  return unwrap<ImReportRecord[]>(
    request('/api/v1/im/reports', { method: 'GET', params: { status } }),
  );
}

export async function handleImReport(
  reportId: number,
  action: 'accept' | 'reject',
  note = '',
) {
  return unwrap<ImReportRecord>(
    request(`/api/v1/im/reports/${reportId}/handle`, {
      method: 'POST',
      data: { action, note },
    }),
  );
}
