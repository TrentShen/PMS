// 员工目标制定页：填写/提交目标到指定目标周期
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Button, Card, Input, InputNumber, Space, Table, Tag, Typography, message } from "antd";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import type { ObjectiveView } from "@/services/api.types";


interface ObjItem {
  title: string;
  description: string;
  measure_criteria: string;
  weight: number;
}

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  draft: { text: "草稿", color: "default" },
  pending_review: { text: "待上级审批", color: "orange" },
  approved: { text: "已确认", color: "green" },
  locked: { text: "已锁定", color: "blue" },
};

export default function MyObjectives() {
  const { objectiveCycleId } = useParams();
  const user = useAuth((s) => s.user)!;
  const [objectives, setObjectives] = useState<ObjectiveView[]>([]);
  const [editing, setEditing] = useState(false);
  const [items, setItems] = useState<ObjItem[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    const r = await api.get<ObjectiveView[]>(`/v1/objective-cycles/${objectiveCycleId}/objectives`);
    setObjectives(r.data);
  }

  useEffect(() => {
    load();
  }, [objectiveCycleId]);

  useEffect(() => {
    if (objectives.length > 0) {
      setItems(
        objectives.map((o) => ({
          title: o.title,
          description: o.description,
          measure_criteria: o.measure_criteria,
          weight: o.weight,
        }))
      );
    } else {
      setItems([]);
    }
  }, [objectives]);

  function addRow() {
    setItems([...items, { title: "", description: "", measure_criteria: "", weight: 0 }]);
  }
  function removeRow(idx: number) {
    setItems(items.filter((_, i) => i !== idx));
  }
  function updateRow(idx: number, field: keyof ObjItem, value: string | number) {
    const next = [...items];
    next[idx] = { ...next[idx], [field]: value };
    setItems(next);
  }

  async function onSave() {
    const total = items.reduce((s, i) => s + (i.weight || 0), 0);
    if (total !== 100) {
      message.error(`权重总和必须为 100，当前为 ${total}`);
      return;
    }
    if (items.some((i) => !i.title.trim())) {
      message.error("目标标题不能为空");
      return;
    }
    setLoading(true);
    try {
      await api.put(`/v1/objective-cycles/${objectiveCycleId}/objectives`, { items });
      message.success("目标草稿已保存");
      setEditing(false);
      await load();
    } catch (e) {
      message.error(formatError(e, "保存失败"));
    } finally {
      setLoading(false);
    }
  }

  async function onSubmit() {
    setLoading(true);
    try {
      await api.post(`/v1/objective-cycles/${objectiveCycleId}/objectives/submit`);
      message.success("目标已提交上级审批");
      await load();
    } catch (e) {
      message.error(formatError(e, "提交失败"));
    } finally {
      setLoading(false);
    }
  }

  const overallStatus = objectives.length > 0
    ? objectives.some((o) => o.status === "pending_review")
      ? "pending_review"
      : objectives.some((o) => o.status === "draft")
      ? "draft"
      : objectives[0]?.status ?? "draft"
    : "draft";

  const hasDraft = objectives.some((o) => o.status === "draft");
  const allApproved = objectives.length > 0 && objectives.every((o) => o.status === "approved" || o.status === "locked");
  const rejected = objectives.find((o) => o.reject_reason);

  if (editing) {
    const totalWeight = items.reduce((s, i) => s + (i.weight || 0), 0);
    return (
      <Card
        title="录入/修改绩效目标"
        extra={
          <Space>
            <Tag color={totalWeight === 100 ? "green" : "red"}>权重合计 {totalWeight}%</Tag>
            <Button onClick={() => setEditing(false)}>取消</Button>
            <Button type="primary" onClick={onSave} loading={loading}>
              保存草稿
            </Button>
          </Space>
        }
      >
        <Space direction="vertical" style={{ width: "100%" }}>
          {items.map((item, idx) => (
            <Card key={idx} size="small" type="inner" title={`目标 ${idx + 1}`} extra={<a onClick={() => removeRow(idx)} style={{ color: "red" }}>删除</a>}>
              <Space direction="vertical" style={{ width: "100%" }}>
                <Input placeholder="目标标题" value={item.title} onChange={(e) => updateRow(idx, "title", e.target.value)} />
                <Input.TextArea placeholder="目标描述" rows={2} value={item.description} onChange={(e) => updateRow(idx, "description", e.target.value)} />
                <Input placeholder="衡量标准（如何算达成）" value={item.measure_criteria} onChange={(e) => updateRow(idx, "measure_criteria", e.target.value)} />
                <InputNumber placeholder="权重%" min={1} max={100} value={item.weight || undefined} onChange={(v) => updateRow(idx, "weight", v ?? 0)} addonAfter="%" />
              </Space>
            </Card>
          ))}
          <Button type="dashed" block onClick={addRow}>+ 添加目标</Button>
        </Space>
      </Card>
    );
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title={`${user.name} 的绩效目标`}>
        <Typography.Paragraph type="secondary">目标周期 ID：{objectiveCycleId}</Typography.Paragraph>
      </Card>

      <Card
        title={
          <Space>
            绩效目标
            <Tag color={STATUS_LABEL[overallStatus]?.color}>{STATUS_LABEL[overallStatus]?.text}</Tag>
          </Space>
        }
        extra={
          <Space>
            {hasDraft && (
              <Button type="primary" onClick={onSubmit} loading={loading}>
                提交上级审批
              </Button>
            )}
            {!allApproved && (
              <Button onClick={() => { setEditing(true); if (items.length === 0) addRow(); }}>
                {objectives.length > 0 ? "修改目标" : "录入目标"}
              </Button>
            )}
          </Space>
        }
      >
        {objectives.length === 0 ? (
          <Typography.Paragraph type="warning">你还没有绩效目标，请点击「录入目标」开始填写。</Typography.Paragraph>
        ) : (
          <>
            {rejected && (
              <Typography.Paragraph type="danger" style={{ marginBottom: 12 }}>
                上级驳回原因：{rejected.reject_reason}
              </Typography.Paragraph>
            )}
            <Table
              rowKey="id"
              size="small"
              pagination={false}
              dataSource={objectives}
              columns={[
                { title: "目标", dataIndex: "title" },
                { title: "描述", dataIndex: "description", ellipsis: true },
                { title: "衡量标准", dataIndex: "measure_criteria", ellipsis: true },
                { title: "权重", dataIndex: "weight", render: (v) => `${v}%` },
                { title: "状态", dataIndex: "status", render: (v) => <Tag color={STATUS_LABEL[v]?.color}>{STATUS_LABEL[v]?.text}</Tag> },
              ]}
            />
          </>
        )}
      </Card>
    </Space>
  );
}
