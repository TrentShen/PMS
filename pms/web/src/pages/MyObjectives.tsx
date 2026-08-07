// 员工目标制定页：填写/提交目标到指定目标周期
// 移动端优先：查看态为目标卡片列表，编辑态每目标一卡 + 底部固定操作栏
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Empty,
  Input,
  InputNumber,
  Popconfirm,
  Space,
  Spin,
  Typography,
  message,
} from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import type { ObjectiveView } from "@/services/api.types";
import BottomActions from "@/components/ui/BottomActions";
import ResponsiveShow from "@/components/ui/ResponsiveShow";
import StatusTag, { type StatusType } from "@/components/ui/StatusTag";

interface ObjItem {
  title: string;
  description: string;
  measure_criteria: string;
  weight: number;
}

// 每个周期最多 10 条目标
const MAX_OBJECTIVES = 10;

const STATUS_LABEL: Record<string, { text: string; type: StatusType }> = {
  draft: { text: "草稿", type: "default" },
  pending_review: { text: "待上级审批", type: "warning" },
  approved: { text: "已确认", type: "success" },
  locked: { text: "已锁定", type: "primary" },
};

// 编辑态字段的小标签样式（跟随 tokens.css 文本层级色）
const FIELD_LABEL_STYLE: React.CSSProperties = {
  color: "var(--color-text-secondary)",
  fontSize: 13,
  marginBottom: 4,
};

export default function MyObjectives() {
  const { objectiveCycleId } = useParams();
  const user = useAuth((s) => s.user)!;
  const [objectives, setObjectives] = useState<ObjectiveView[]>([]);
  const [editing, setEditing] = useState(false);
  const [items, setItems] = useState<ObjItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  async function load() {
    const r = await api.get<ObjectiveView[]>(`/v1/objective-cycles/${objectiveCycleId}/objectives`);
    setObjectives(r.data);
  }

  useEffect(() => {
    setPageLoading(true);
    load()
      .catch((e) => message.error(formatError(e, "加载目标失败")))
      .finally(() => setPageLoading(false));
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
    if (items.length >= MAX_OBJECTIVES) {
      message.warning(`最多添加 ${MAX_OBJECTIVES} 条目标`);
      return;
    }
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

  // 编辑中的 items 与已保存 objectives 是否有差异（用于取消编辑时的防误丢确认）
  function isDirty() {
    if (items.length !== objectives.length) return true;
    return items.some((item, idx) => {
      const o = objectives[idx];
      return (
        !o ||
        item.title !== o.title ||
        item.description !== o.description ||
        item.measure_criteria !== o.measure_criteria ||
        item.weight !== o.weight
      );
    });
  }

  async function onSave() {
    const total = items.reduce((s, i) => s + (i.weight || 0), 0);
    if (total !== 100) {
      message.error(`权重总和必须为 100，当前为 ${total}`);
      return;
    }
    const emptyTitleIdx = items.findIndex((i) => !i.title.trim());
    if (emptyTitleIdx >= 0) {
      message.error(`目标 ${emptyTitleIdx + 1} 的重点工作不能为空`);
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
    const reachedMax = items.length >= MAX_OBJECTIVES;
    return (
      <div className="has-bottom-actions">
        <Card
          title="录入/修改绩效目标"
          extra={
            <StatusTag type={totalWeight === 100 ? "success" : "warning"}>
              权重合计 {totalWeight}%（需等于 100%）
            </StatusTag>
          }
        >
          <Space direction="vertical" size="middle" style={{ width: "100%" }}>
            {items.map((item, idx) => (
              <Card
                key={idx}
                size="small"
                type="inner"
                title={`目标 ${idx + 1}`}
                extra={
                  <Popconfirm
                    title="确定删除该目标？"
                    okText="删除"
                    cancelText="取消"
                    onConfirm={() => removeRow(idx)}
                  >
                    <Button type="text" danger size="small" icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                }
              >
                <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                  <div>
                    <div style={FIELD_LABEL_STYLE}>重点工作</div>
                    <Input
                      placeholder="例：独立完成 XX 模块的开发与上线"
                      value={item.title}
                      onChange={(e) => updateRow(idx, "title", e.target.value)}
                    />
                  </div>
                  <div>
                    <div style={FIELD_LABEL_STYLE}>权重</div>
                    <InputNumber
                      min={1}
                      max={100}
                      addonAfter="%"
                      inputMode="decimal"
                      style={{ width: 140 }}
                      placeholder="权重"
                      value={item.weight || undefined}
                      onChange={(v) => updateRow(idx, "weight", v ?? 0)}
                    />
                  </div>
                  <div>
                    <div style={FIELD_LABEL_STYLE}>关键成果</div>
                    <Input.TextArea
                      rows={2}
                      placeholder="本目标要交付的关键成果/交付物，可逐条列出"
                      value={item.description}
                      onChange={(e) => updateRow(idx, "description", e.target.value)}
                    />
                  </div>
                  <div>
                    <div style={FIELD_LABEL_STYLE}>衡量标准</div>
                    <Input.TextArea
                      rows={2}
                      placeholder="如何算达成（4分及5分需写出分项考核标准）"
                      value={item.measure_criteria}
                      onChange={(e) => updateRow(idx, "measure_criteria", e.target.value)}
                    />
                  </div>
                </Space>
              </Card>
            ))}
            <Button
              type="dashed"
              block
              icon={<PlusOutlined />}
              onClick={addRow}
              disabled={reachedMax}
            >
              添加目标
            </Button>
            {reachedMax && (
              <Typography.Text type="secondary">最多添加 {MAX_OBJECTIVES} 条目标</Typography.Text>
            )}
          </Space>
        </Card>
        <BottomActions>
          {isDirty() ? (
            <Popconfirm
              title="修改未保存，确定放弃？"
              okText="放弃修改"
              cancelText="继续编辑"
              onConfirm={() => setEditing(false)}
            >
              <Button>取消</Button>
            </Popconfirm>
          ) : (
            <Button onClick={() => setEditing(false)}>取消</Button>
          )}
          <Button type="primary" onClick={onSave} loading={loading}>
            保存草稿
          </Button>
        </BottomActions>
      </div>
    );
  }

  const actionButtons = (
    <>
      {hasDraft && (
        <Button type="primary" block onClick={onSubmit} loading={loading}>
          提交上级审批
        </Button>
      )}
      {!allApproved && (
        <Button
          block
          onClick={() => {
            setEditing(true);
            if (items.length === 0) addRow();
          }}
        >
          {objectives.length > 0 ? "修改目标" : "录入目标"}
        </Button>
      )}
    </>
  );

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card
        title={
          <Space size={8} wrap>
            {`${user.name} 的绩效目标`}
            {objectives.length > 0 && (
              <StatusTag type={STATUS_LABEL[overallStatus]?.type ?? "default"}>
                {STATUS_LABEL[overallStatus]?.text ?? overallStatus}
              </StatusTag>
            )}
          </Space>
        }
        extra={<ResponsiveShow on="desktop"><Space>{actionButtons}</Space></ResponsiveShow>}
      >
        {/* 移动端：操作按钮在卡片顶部全宽展示 */}
        <ResponsiveShow on="mobile">
          <Space direction="vertical" size={8} style={{ width: "100%", marginBottom: 16 }}>
            {actionButtons}
          </Space>
        </ResponsiveShow>

        {pageLoading ? (
          <div style={{ textAlign: "center", padding: "48px 0" }}>
            <Spin />
          </div>
        ) : objectives.length === 0 ? (
          <Empty description="点击「录入目标」开始制定本周期目标" />
        ) : (
          <>
            {rejected && (
              <Alert
                type="error"
                showIcon
                style={{ marginBottom: 16 }}
                message="上级已驳回，请修改后重新提交"
                description={rejected.reject_reason}
              />
            )}
            {objectives.map((o, idx) => (
              <Card key={o.id} size="small" style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                  <Typography.Text strong style={{ fontSize: 15 }}>
                    {idx + 1}. {o.title}
                  </Typography.Text>
                  <Typography.Text strong style={{ fontSize: 18, color: "var(--color-primary)", flexShrink: 0 }}>
                    {o.weight}%
                  </Typography.Text>
                </div>
                <div style={{ marginTop: 8 }}>
                  <div style={FIELD_LABEL_STYLE}>关键成果</div>
                  <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 8 }}>
                    {o.description || "-"}
                  </Typography.Paragraph>
                  <div style={FIELD_LABEL_STYLE}>衡量标准</div>
                  <Typography.Paragraph style={{ whiteSpace: "pre-wrap", marginBottom: 8 }}>
                    {o.measure_criteria || "-"}
                  </Typography.Paragraph>
                </div>
                <StatusTag type={STATUS_LABEL[o.status]?.type ?? "default"}>
                  {STATUS_LABEL[o.status]?.text ?? o.status}
                </StatusTag>
              </Card>
            ))}
          </>
        )}
      </Card>
    </Space>
  );
}
