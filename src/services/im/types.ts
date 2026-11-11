export interface ConversationRecord {
  id: number;
  buyer_id: number;
  seller_id: number;
  order_id?: number;
  status: string;
  buyer_unread_count: number;
  seller_unread_count: number;
}

export interface MessagePayload {
  attachment_id?: number;
  url?: string;
  mime_type?: string;
  size?: number;
}

export interface MessageRecord {
  id: number;
  conversation_id: number;
  sender_id: number;
  client_msg_id: string;
  seq: number;
  type: string;
  content: string;
  payload?: MessagePayload | null;
  status: string;
}

export interface ReadState {
  conversation_id: number;
  my_last_read_seq: number;
  peer_last_read_seq: number;
  buyer_unread_count: number;
  seller_unread_count: number;
}

export interface ImReportRecord {
  id: number;
  conversation_id: number;
  message_id: number;
  reporter_id: number;
  reason: string;
  status: string;
  note: string;
}
