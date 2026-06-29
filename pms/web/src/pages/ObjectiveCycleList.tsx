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
  Tag,
  message,
} from "antd";
import dayjs from "dayjs";
import { api } from "@/services/api";

interface ObjectiveCycle {
  id: number;
  name: string;
  status: string;
  start_date: string;
  end_date: string;
  created_by: string;
  created_at: string;
}

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  draft: { text: "制定中", color: "default" },
  active: { text: "执行中", color: "blue" },
  completed: { text: "已结束", color: "green" },
};

export default function ObjectiveCycleList() {
  const navigate = useNavigate();
  const [cycles, setCycles] = useState<ObjectiveCycle[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();

  async function load() {
    const r = await api.get<ObjectiveCycle[]>("/v1/objective-cycles");
    setCycles(r.data);
  }

  useEffect(() => { load(); }, []);

  async function onCreate(values: any) {
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
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "创建失败");
    }
  }

  async function onStart(c: ObjectiveCycle) {
    try {
      await api.post(`/v1/objective-cycles/${c.id}/start`);
      message.success("目标周期已启动");
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "启动失败");
    }
  }

  async function onComplete(c: ObjectiveCycle) {
    try {
      await api.post(`/v1/objective-cycles/${c.id}/complete`);
      message.success("目标周期已标记完成");
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "操作失败");
    }
  }

  async function onDelete(c: ObjectiveCycle) {
    try {
      await api.delete(`/v1/objective-cycles/${c.id}`);
      message.success("目标周期已删除");
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "删除失败");
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="目标周期管理" extra={
        <Button type="primary" onClick={() => setCreateOpen(true)}>新建目标周期</Button>
      }>
        <List
          dataSource={cycles}
          renderItem={(c) => (
            <List.Item actions={[
              <a key="detail" onClick={() => navigate(`/objective-cycles/${c.id}`)}>详情</a>,
              c.status === "draft" && (
                <Popconfirm key="start" title="启动后员工可开始执行目标，确认？" onConfirm={() => onStart(c)}>
                  <a>启动</a>
                </Popconfirm>
              ),
              c.status === "active" && (
                <Popconfirm key="complete" title="完成后员工不能再调整目标，确认？" onConfirm={() => onComplete(c)}>
                  <a style={{ color: "#52c41a" }}>完成</a>
                </Popconfirm>
              ),
              c.status === "draft" && (
                <Popconfirm key="del" title="删除后不可恢复，确认？" onConfirm={() => onDelete(c)}>
                  <a style={{ color: "#ff4d4f" }}>删除</a>
                </Popconfirm>
              ),
            ].filter(Boolean) as any}>
              <List.Item.Meta
                title={
                  <Space>
                    {c.name}
                    <Tag color={STATUS_LABEL[c.status]?.color}>{STATUS_LABEL[c.status]?.text}</Tag>
                  </Space>
                }
                description={`${c.start_date} ~ ${c.end_date}`}
              />
            </List.Item>
          )}
        />
      </Card>

      <Modal title="新建目标周期" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => form.submit()}>
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
