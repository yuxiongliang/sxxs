import {
  AppstoreOutlined,
  CloudUploadOutlined,
  CopyOutlined,
  DeleteOutlined,
  FileImageOutlined,
  FileOutlined,
  FileTextOutlined,
  PaperClipOutlined,
  ReloadOutlined,
  UnorderedListOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  App,
  Button,
  Card,
  Col,
  Empty,
  Image,
  Input,
  Modal,
  Pagination,
  Popconfirm,
  Row,
  Segmented,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import React, { useMemo, useState } from 'react';
import AttachmentUpload from '@/components/AttachmentUpload';
import {
  deleteAttachment,
  restoreAttachment,
  getAttachmentStats,
  listAttachments,
} from '@/services/system/api';
import type { AttachmentRecord } from '@/services/system/types';
import SettingPage from '../components/SettingPage';
import {
  ATTACHMENT_CATEGORY_OPTIONS,
  formatBytes,
  formatDateTime,
  optionLabel,
} from '../utils';

const SOURCE_MODULES = [
  { label: '手工上传', value: 'manual' },
  { label: '品牌中心', value: 'brand' },
  { label: '商品管理', value: 'product' },
  { label: '用户管理', value: 'user' },
  { label: '本体管理', value: 'ontology' },
  { label: '开放平台', value: 'open-platform' },
  { label: '内容运营', value: 'content' },
];

const categoryIcon = (category: string) => {
  if (category === 'image') return <FileImageOutlined />;
  if (category === 'video') return <VideoCameraOutlined />;
  if (category === 'document') return <FileTextOutlined />;
  return <FileOutlined />;
};

const categoryColor = (category: string) => {
  if (category === 'image') return 'blue';
  if (category === 'video') return 'purple';
  if (category === 'document') return 'green';
  return 'default';
};

const REVIEW_LABEL: Record<string, string> = {
  pending: '审核中',
  approved: '已通过',
  rejected: '未通过',
  manual: '待人工',
  failed: '审核异常',
};

const REVIEW_COLOR: Record<string, string> = {
  pending: 'gold',
  approved: 'green',
  rejected: 'red',
  manual: 'blue',
  failed: 'volcano',
};

const ROLE_LABEL: Record<string, string> = {
  admin: '管理员',
  seller: '卖家',
  buyer: '买家',
};

const AttachmentManagement: React.FC = () => {
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [category, setCategory] = useState('all');
  const [keyword, setKeyword] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(18);
  const [view, setView] = useState<'grid' | 'list'>('grid');
  const [uploadOpen, setUploadOpen] = useState(false);
  const [sourceModule, setSourceModule] = useState('manual');
  const [sourceRole, setSourceRole] = useState<string>();
  const [reviewStatus, setReviewStatus] = useState<string>();
  const [recycle, setRecycle] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: [
      'attachments',
      page,
      pageSize,
      category,
      keyword,
      sourceRole,
      reviewStatus,
      recycle,
    ],
    queryFn: () =>
      listAttachments({
        current: page,
        pageSize,
        category,
        keyword,
        source_role: sourceRole,
        review_status: reviewStatus,
        recycle,
      }),
  });
  const { data: stats } = useQuery({
    queryKey: ['attachment-stats'],
    queryFn: getAttachmentStats,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['attachments'] });
    queryClient.invalidateQueries({ queryKey: ['attachment-stats'] });
  };

  const handleDelete = async (record: AttachmentRecord) => {
    try {
      await deleteAttachment(record.id);
      message.success('已移入回收站');
      refresh();
    } catch (error: any) {
      message.error(error?.message || '删除失败');
    }
  };

  const handleRestore = async (record: AttachmentRecord) => {
    try {
      await restoreAttachment(record.id);
      message.success('附件已恢复');
      refresh();
    } catch (error: any) {
      message.error(error?.message || '恢复失败');
    }
  };

  const handleCopy = async (record: AttachmentRecord) => {
    try {
      await navigator.clipboard.writeText(record.url);
      message.success('链接已复制');
    } catch {
      message.info(record.url);
    }
  };

  const columns: ColumnsType<AttachmentRecord> = useMemo(
    () => [
      {
        title: '附件',
        dataIndex: 'name',
        render: (_, record) => (
          <Space>
            <span style={{ fontSize: 20 }}>
              {categoryIcon(record.category)}
            </span>
            <div>
              <div style={{ fontWeight: 600 }}>{record.name}</div>
              <div style={{ color: '#8c8c8c', fontSize: 12 }}>
                {record.mime_type}
              </div>
            </div>
          </Space>
        ),
      },
      {
        title: '类型',
        dataIndex: 'category',
        width: 100,
        render: (value: string) => (
          <Tag color={categoryColor(value)}>
            {optionLabel(ATTACHMENT_CATEGORY_OPTIONS, value)}
          </Tag>
        ),
      },
      {
        title: '大小',
        dataIndex: 'size',
        width: 110,
        render: (value: number) => formatBytes(value),
      },
      { title: '来源模块', dataIndex: 'source_module', width: 120 },
      {
        title: '来源',
        dataIndex: 'uploader_role',
        width: 90,
        render: (value: string) => (
          <Tag color={value === 'seller' ? 'purple' : value === 'buyer' ? 'blue' : 'default'}>
            {ROLE_LABEL[value] ?? value}
          </Tag>
        ),
      },
      {
        title: '审核',
        dataIndex: 'review_status',
        width: 120,
        render: (value: string, record) => (
          <Space direction="vertical" size={0}>
            <Tag color={REVIEW_COLOR[value] ?? 'default'}>
              {REVIEW_LABEL[value] ?? value}
            </Tag>
            {record.reject_reason ? (
              <span style={{ color: '#cf1322', fontSize: 12 }}>
                {record.reject_reason}
              </span>
            ) : null}
          </Space>
        ),
      },
      { title: '上传人', dataIndex: 'uploader', width: 100 },
      {
        title: '上传时间',
        dataIndex: 'created_at',
        width: 170,
        render: (value: string) => formatDateTime(value),
      },
      {
        title: '操作',
        key: 'action',
        width: 150,
        render: (_, record) => (
          <Space>
            <Tooltip title="复制链接">
              <Button
                type="link"
                size="small"
                icon={<CopyOutlined />}
                onClick={() => handleCopy(record)}
              />
            </Tooltip>
            <Popconfirm
              title="移入回收站后仍可恢复，确定？"
              onConfirm={() => handleDelete(record)}
            >
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
              />
            </Popconfirm>
            {recycle ? (
              <Button
                type="link"
                size="small"
                onClick={() => handleRestore(record)}
              >
                恢复
              </Button>
            ) : null}
          </Space>
        ),
      },
    ],
    [recycle],
  );

  const renderCard = (record: AttachmentRecord) => {
    let cover: React.ReactNode;
    if (record.category === 'image') {
      cover = (
        <div style={{ height: 128, background: '#f5f5f5', overflow: 'hidden' }}>
          <Image
            src={record.url}
            alt={record.name}
            height={128}
            width="100%"
            style={{ objectFit: 'cover' }}
          />
        </div>
      );
    } else if (record.category === 'video') {
      cover = (
        <div
          style={{
            height: 128,
            background: '#000',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <video
            src={record.url}
            controls
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          >
            <track
              kind="captions"
              src="data:text/vtt;charset=utf-8,WEBVTT%0A%0A"
            />
          </video>
        </div>
      );
    } else {
      cover = (
        <div
          style={{
            height: 128,
            background: 'linear-gradient(135deg,#f0f5ff,#e6f4ff)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#1677ff',
            fontSize: 32,
            gap: 8,
          }}
        >
          {categoryIcon(record.category)}
          <span style={{ fontSize: 12, color: '#8c8c8c' }}>
            {record.extension || 'FILE'}
          </span>
        </div>
      );
    }

    return (
      <Card
        key={record.id}
        hoverable
        cover={cover}
        actions={[
          <Tooltip key="copy" title="复制链接">
            <CopyOutlined onClick={() => handleCopy(record)} />
          </Tooltip>,
          <Popconfirm
            key="delete"
            title="确定删除该附件？"
            onConfirm={() => handleDelete(record)}
          >
            <DeleteOutlined style={{ color: '#ff4d4f' }} />
          </Popconfirm>,
        ]}
      >
        <Card.Meta
          title={
            <Tooltip title={record.name}>
              <div
                style={{
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {record.name}
              </div>
            </Tooltip>
          }
          description={
            <Space orientation="vertical" size={2} style={{ width: '100%' }}>
              <Space>
                <Tag color={categoryColor(record.category)}>
                  {optionLabel(ATTACHMENT_CATEGORY_OPTIONS, record.category)}
                </Tag>
                <span style={{ fontSize: 12, color: '#8c8c8c' }}>
                  {formatBytes(record.size)}
                </span>
              </Space>
              <span style={{ fontSize: 12, color: '#8c8c8c' }}>
                {record.source_module} · {record.uploader} ·{' '}
                {formatDateTime(record.created_at)}
              </span>
            </Space>
          }
        />
      </Card>
    );
  };

  return (
    <SettingPage
      title="附件管理"
      subTitle="全局附件库：图片、视频、文档统一归档"
      icon={<PaperClipOutlined />}
      extra={
        <Space>
          <Button icon={<ReloadOutlined />} onClick={refresh}>
            刷新
          </Button>
          <Button
            type="primary"
            icon={<CloudUploadOutlined />}
            onClick={() => setUploadOpen(true)}
          >
            上传附件
          </Button>
        </Space>
      }
    >
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="附件总数"
              value={stats?.total ?? 0}
              suffix="个"
              prefix={<PaperClipOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="图片"
              value={stats?.images ?? 0}
              suffix="张"
              prefix={<FileImageOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="视频 / 文档"
              value={(stats?.videos ?? 0) + (stats?.documents ?? 0)}
              suffix="个"
              prefix={<VideoCameraOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card>
            <Statistic
              title="占用空间"
              value={formatBytes(stats?.totalSize ?? 0)}
              prefix={<CloudUploadOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 12,
            justifyContent: 'space-between',
            marginBottom: 16,
          }}
        >
          <Space wrap>
            <Segmented
              value={category}
              options={ATTACHMENT_CATEGORY_OPTIONS}
              onChange={(value) => {
                setCategory(value as string);
                setPage(1);
              }}
            />
            <Input.Search
              allowClear
              placeholder="搜索文件名 / 来源模块"
              style={{ width: 260 }}
              onSearch={(value) => {
                setKeyword(value);
                setPage(1);
              }}
            />
            <Select
              allowClear
              placeholder="上传者"
              style={{ width: 120 }}
              options={[
                { value: 'admin', label: '管理员' },
                { value: 'seller', label: '卖家' },
                { value: 'buyer', label: '买家' },
              ]}
              onChange={(value) => {
                setSourceRole(value);
                setPage(1);
              }}
            />
            <Select
              allowClear
              placeholder="审核状态"
              style={{ width: 130 }}
              options={[
                { value: 'pending', label: '审核中' },
                { value: 'approved', label: '已通过' },
                { value: 'rejected', label: '未通过' },
                { value: 'manual', label: '待人工' },
                { value: 'failed', label: '审核异常' },
              ]}
              onChange={(value) => {
                setReviewStatus(value);
                setPage(1);
              }}
            />
            <Button
              type={recycle ? 'primary' : 'default'}
              onClick={() => {
                setRecycle(!recycle);
                setPage(1);
              }}
            >
              回收站
            </Button>
          </Space>
          <Segmented
            value={view}
            onChange={(value) => setView(value as 'grid' | 'list')}
            options={[
              { value: 'grid', icon: <AppstoreOutlined />, label: '网格' },
              { value: 'list', icon: <UnorderedListOutlined />, label: '列表' },
            ]}
          />
        </div>

        {!isLoading && !data?.list.length ? (
          <Empty description="暂无附件" />
        ) : view === 'grid' ? (
          <>
            <Row gutter={[16, 16]}>
              {data?.list.map((record) => (
                <Col
                  key={record.id}
                  xs={24}
                  sm={12}
                  md={6}
                  lg={4}
                  xl={4}
                  xxl={4}
                >
                  {renderCard(record)}
                </Col>
              ))}
            </Row>
            <div
              style={{
                display: 'flex',
                justifyContent: 'flex-end',
                marginTop: 16,
              }}
            >
              <Pagination
                current={page}
                pageSize={pageSize}
                total={data?.total ?? 0}
                showSizeChanger
                pageSizeOptions={[18, 36, 54]}
                onChange={(nextPage, nextPageSize) => {
                  setPage(nextPage);
                  setPageSize(nextPageSize);
                }}
              />
            </div>
          </>
        ) : (
          <Table
            rowKey="id"
            loading={isLoading}
            columns={columns}
            dataSource={data?.list ?? []}
            pagination={{
              current: page,
              pageSize,
              total: data?.total ?? 0,
              showSizeChanger: true,
              pageSizeOptions: [18, 36, 54],
              onChange: (nextPage, nextPageSize) => {
                setPage(nextPage);
                setPageSize(nextPageSize);
              },
            }}
          />
        )}
      </Card>

      <Modal
        title="上传附件"
        open={uploadOpen}
        footer={null}
        onCancel={() => setUploadOpen(false)}
        destroyOnHidden
        width={620}
      >
        <Space orientation="vertical" size={16} style={{ display: 'flex' }}>
          <Space>
            <span>来源模块</span>
            <Select
              value={sourceModule}
              options={SOURCE_MODULES}
              onChange={setSourceModule}
              style={{ width: 240 }}
            />
          </Space>
          <AttachmentUpload
            dragger
            sourceModule={sourceModule}
            onUploaded={() => {
              setPage(1);
              refresh();
            }}
          />
          <span style={{ color: '#8c8c8c', fontSize: 12 }}>
            所有后续模块的图片、视频、文档上传都建议复用 `AttachmentUpload`
            组件，上传后会统一出现在本附件库。
          </span>
        </Space>
      </Modal>
    </SettingPage>
  );
};

export default AttachmentManagement;
