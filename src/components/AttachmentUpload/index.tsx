import { InboxOutlined } from '@ant-design/icons';
import { App, Button, Upload } from 'antd';
import type { UploadProps } from 'antd';
import React from 'react';
import { uploadAttachment } from '@/services/system/api';
import type { AttachmentRecord } from '@/services/system/types';

interface AttachmentUploadProps {
  sourceModule?: string;
  accept?: string;
  multiple?: boolean;
  dragger?: boolean;
  buttonText?: string;
  onUploaded?: (record: AttachmentRecord) => void;
  children?: React.ReactNode;
}

export default function AttachmentUpload({
  sourceModule = 'manual',
  accept,
  multiple = true,
  dragger = false,
  buttonText = '上传附件',
  onUploaded,
  children,
}: AttachmentUploadProps) {
  const { message } = App.useApp();

  const customRequest: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;
    try {
      const record = await uploadAttachment(file as File, sourceModule);
      message.success(`${record.name} 上传成功`);
      onUploaded?.(record);
      onSuccess?.(record);
    } catch (error: any) {
      message.error(error?.message || '上传失败');
      onError?.(error);
    }
  };

  if (dragger) {
    return (
      <Upload.Dragger
        name="file"
        multiple={multiple}
        accept={accept}
        customRequest={customRequest}
        showUploadList={false}
      >
        {children ?? (
          <>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">
              支持图片、视频、文档等附件，单个文件不超过 50MB
            </p>
          </>
        )}
      </Upload.Dragger>
    );
  }

  return (
    <Upload
      name="file"
      multiple={multiple}
      accept={accept}
      customRequest={customRequest}
      showUploadList={false}
    >
      {children ?? <Button>{buttonText}</Button>}
    </Upload>
  );
}
