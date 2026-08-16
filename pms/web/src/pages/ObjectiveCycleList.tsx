// HR 目标周期管理页：列表、创建、启动、完成、删除
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Space,
  message,
} from "antd";
import dayjs from "dayjs";
import { api, formatError } from "@/services/api";
import StatusTag from "@/components/ui/StatusTag";
import type { StatusType } from "@/components/ui/StatusTag";


interface ObjectiveCycleCreateForm {
  name: string;
  range: [dayjs.Dayjs, dayjs.Dayjs];
}

interface ObjectiveCycle {
  id: number;
  name: string;
  status: string;
  start_date: string;
  end_date: string;
  created_by: string;
  created_at: string;
}

const STATUS_LABEL: Record<string, { text: string; type: StatusType }> = {
  draft: { text: "制定中", type: "default" },
  active: { text: "执行中", type: "primary" },
  completed: { text: "已结束", type: "success" },
};

export default function ObjectiveCycleList() {
  const navigate = useNavigate();
  const [cycles, setCycles] = useState<ObjectiveCycle[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  // 启动/完成/删除在途保护：记录正在操作的周期 id，防止 Popconfirm 确认按钮重复点击
  const [actingId, setActingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  // 内部自捕获：成功后各操作的刷新直接裸调用 load() 不会产生 unhandled rejection
  async function load() {
    setLoading(true);
    try {
      const r = await api.get<ObjectiveCycle[]>("/v1/objective-cycles");
      setCycles(r.data);
    } catch (e) {
      message.error(formatError(e, "加载失败"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function onCreate(values: ObjectiveCycleCreateForm) {
    setCreating(true);
    try {
      await api.post("/v1/objective-cycles", {
        name: values.name,
        start_date: values.range[0].format("YYYY-MM-DD"),
        end_date: values.range[1].format("YYYY-MM-DD"),
      });
      message.success("目标周期已创建");
      setCreateOpen(false);
      form.resetFields();
      load();
    } catch (e) {
      message.error(formatError(e, "创建失败"));
    } finally {
      setCreating(false);
    }
  }

  async function onStart(c: ObjectiveCycle) {
    setActingId(c.id);
    try {
      await api.post(`/v1/objective-cycles/${c.id}/start`);
      message.success("目标周期已启动");
      load();
    } catch (e) {
      message.error(formatError(e, "启动失败"));
    } finally {
      setActingId(null);
    }
  }

  async function onComplete(c: ObjectiveCycle) {
    setActingId(c.id);
    try {
      await api.post(`/v1/objective-cycles/${c.id}/complete`);
      message.success("目标周期已标记完成");
      load();
    } catch (e) {
      message.error(formatError(e, "操作失败"));
    } finally {
      setActingId(null);
    }
  }

  async function onDelete(c: ObjectiveCycle) {
    setActingId(c.id);
    try {
      await api.delete(`/v1/objective-cycles/${c.id}`);
      message.success("目标周期已删除");
      load();
    } catch (e) {
      message.error(formatError(e, "删除失败"));
    } finally {
      setActingId(null);
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="目标周期管理" extra={
        <Button type="primary" onClick={() => setCreateOpen(true)}>新建目标周期</Button>
      }>
        <List
          loading={loading}
          dataSource={cycles}
          renderItem={(c) => (
            <List.Item actions={[
              <a key="detail" onClick={() => navigate(`/objective-cycles/${c.id}`)}>详情</a>,
              c.status === "draft" && (
                <Popconfirm key="start" title="启动后员工可开始执行目标，确认？" onConfirm={() => onStart(c)} okButtonProps={{ loading: actingId === c.id }}>
                  <a>启动</a>
                </Popconfirm>
              ),
              c.status === "active" && (
                <Popconfirm key="complete" title="完成后员工不能再调整目标，确认？" onConfirm={() => onComplete(c)} okButtonProps={{ loading: actingId === c.id }}>
                  <a style={{ color: "var(--color-success)" }}>完成</a>
                </Popconfirm>
              ),
              c.status === "draft" && (
                <Popconfirm key="del" title="删除后不可恢复，确认？" onConfirm={() => onDelete(c)} okButtonProps={{ loading: actingId === c.id }}>
                  <a style={{ color: "var(--color-danger)" }}>删除</a>
                </Popconfirm>
              ),
            ].filter(Boolean) as React.ReactNode[]}>
              <List.Item.Meta
                title={
                  <Space>
                    {c.name}
                    <StatusTag type={STATUS_LABEL[c.status]?.type}>{STATUS_LABEL[c.status]?.text}</StatusTag>
                  </Space>
                }
                description={`${c.start_date} ~ ${c.end_date}`}
              />
            </List.Item>
          )}
        />
      </Card>

      <Modal title="新建目标周期" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => form.submit()} confirmLoading={creating}>
        <Form form={form} layout="vertical" onFinish={onCreate}>
          <Form.Item name="name" label="周期名" initialValue="2025 下半年目标" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="range" label="目标周期" initialValue={[dayjs("2025-07-01"), dayjs("2025-12-31")]} rules={[{ required: true }]}>
            <DatePicker.RangePicker />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
