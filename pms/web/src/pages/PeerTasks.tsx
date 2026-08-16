// 我的互评任务：列表 + 填评价（被评人不可见自己的互评内容）
// 移动端：评价表单用全屏底部抽屉 + BottomActions 固定提交，避免键盘遮挡；
// 提交成功后自动打开下一条待评价任务；桌面端保持 Modal
import { useEffect, useRef, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  List,
  Modal,
  Progress,
  Spin,
  Typography,
  message,
} from "antd";
import { api, formatError } from "@/services/api";
import ValueGradeForm, { expandValueGrades } from "@/components/ValueGradeForm";
import { useMobile } from "@/hooks/useMobile";
import BottomActions from "@/components/ui/BottomActions";
import StatusTag from "@/components/ui/StatusTag";


// 被评人目标（只读），评价时"有据可依"
interface PeerObjective {
  title: string;
  description: string;
  measure_criteria: string;
  weight: number;
  progress: number;
}

interface PeerTask {
  id: number;
  cycle_id: number;
  cycle_name: string;
  target_user_id: number;
  target_name: string;
  target_position: string | null;
  status: "pending" | "submitted" | "declined";
  decline_reason: string | null;
  submitted_at: string | null;
  objectives: PeerObjective[];
}

// 互评表单值（界面只采集 belief 一组，提交时 expandValueGrades 展开为后端三维度契约）
interface PeerEvalFormValues {
  perf_score: number;
  value_belief_grade: string;
  value_belief_example?: string;
  comment?: string;
}

export default function PeerTasks() {
  const [tasks, setTasks] = useState<PeerTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<PeerTask | null>(null);
  const [declining, setDeclining] = useState<PeerTask | null>(null);
  const [declineReason, setDeclineReason] = useState("");
  const [declineSaving, setDeclineSaving] = useState(false);
  const [form] = Form.useForm<PeerEvalFormValues>();
  const [saving, setSaving] = useState(false);
  const isMobile = useMobile();

  // 互评草稿：localStorage 按任务隔离（与自评草稿同款模式），打开抽屉时恢复一次
  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api.get<PeerTask[]>(`/v1/peer/my-tasks`);
      setTasks(r.data);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load().catch((e) => message.error(formatError(e, "加载互评任务失败")));
  }, []);

  // 组件卸载时清掉未触发的防抖计时器
  useEffect(() => {
    return () => {
      if (draftTimer.current) clearTimeout(draftTimer.current);
    };
  }, []);

  // 进度：已提交 / 已拒绝都计为已处理
  const processedCount = tasks.filter((t) => t.status !== "pending").length;
  const progressPercent = tasks.length > 0 ? Math.round((processedCount / tasks.length) * 100) : 0;

  function openEdit(t: PeerTask) {
    setEditing(t);
    form.resetFields();
    const key = `pms_peer_draft_${t.id}`;
    // 隐私模式下 localStorage 抛 SecurityError，兜底跳过草稿恢复（同 stores/auth.ts safeGet）
    let raw: string | null = null;
    try {
      raw = localStorage.getItem(key);
    } catch {
      raw = null;
    }
    if (raw) {
      try {
        form.setFieldsValue(JSON.parse(raw) as Partial<PeerEvalFormValues>);
        message.info("已恢复上次未提交的草稿");
      } catch {
        localStorage.removeItem(key);
      }
    }
  }

  // 表单值变化时防抖 500ms 写入草稿
  function onValuesChange() {
    if (!editing) return;
    if (draftTimer.current) clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => {
      try {
        localStorage.setItem(`pms_peer_draft_${editing.id}`, JSON.stringify(form.getFieldsValue()));
      } catch {
        // localStorage 不可用（隐私模式/超限）时静默跳过草稿
      }
    }, 500);
  }

  async function onSubmit() {
    if (!editing) return;
    let v: PeerEvalFormValues;
    try {
      v = await form.validateFields();
    } catch (err) {
      // 校验失败：滚动定位到第一个错误字段（全屏抽屉里错误可能在视口外），阻止提交
      const errorFields = (err as { errorFields?: { name: (string | number)[] }[] }).errorFields;
      if (errorFields && errorFields.length > 0) {
        form.scrollToField(errorFields[0].name);
      }
      return;
    }
    setSaving(true);
    try {
      await api.post(`/v1/peer/tasks/${editing.id}/submit`, expandValueGrades(v));
      localStorage.removeItem(`pms_peer_draft_${editing.id}`);
      form.resetFields();
      const r = await api.get<PeerTask[]>(`/v1/peer/my-tasks`);
      setTasks(r.data);
      // 还有待评价任务时自动打开下一位，保持连贯填写体验
      const next = r.data.find((t) => t.status === "pending") ?? null;
      if (next) {
        message.success(`互评已提交，继续评价下一位：${next.target_name}`);
        openEdit(next);
      } else {
        message.success("互评已提交，所有互评任务均已处理");
        setEditing(null);
      }
    } catch (e) {
      message.error(formatError(e, "提交失败"));
    } finally {
      setSaving(false);
    }
  }

  async function onDecline() {
    if (!declining) return;
    setDeclineSaving(true);
    try {
      const reason = declineReason.trim();
      await api.post(`/v1/peer/tasks/${declining.id}/decline`, {
        reason: reason === "" ? null : reason,
      });
      message.success("已拒绝该互评任务");
      setDeclining(null);
      setDeclineReason("");
      await load();
    } catch (e) {
      message.error(formatError(e, "拒绝失败"));
    } finally {
      setDeclineSaving(false);
    }
  }

  function statusTag(t: PeerTask) {
    if (t.status === "pending") return <StatusTag type="warning">待评价</StatusTag>;
    if (t.status === "submitted") return <StatusTag type="success">已提交</StatusTag>;
    return <StatusTag type="default">已拒绝</StatusTag>;
  }

  function actionsOf(t: PeerTask) {
    if (t.status === "declined") return [];
    if (t.status === "submitted") {
      return [
        <Button key="do" onClick={() => openEdit(t)}>
          重新提交
        </Button>,
      ];
    }
    return [
      <Button key="do" type="primary" onClick={() => openEdit(t)}>
        去评价
      </Button>,
      <Button
        key="decline"
        type="text"
        size={isMobile ? undefined : "small"}
        onClick={() => {
          setDeclining(t);
          setDeclineReason("");
        }}
      >
        拒绝
      </Button>,
    ];
  }

  // 被评人目标只读区：评价时展示，作为评分依据（抽屉/Modal 共用，随表单一起渲染）
  const objectiveBlock =
    editing && editing.objectives.length > 0 ? (
      <div style={{ marginBottom: 16, padding: 12, background: "var(--color-surface-raised)", borderRadius: "var(--radius-lg)" }}>
        <Typography.Text strong>{editing.target_name} 的绩效目标</Typography.Text>
        <ul style={{ margin: "8px 0 0", paddingLeft: 20 }}>
          {editing.objectives.map((o, i) => (
            <li key={i} style={{ marginBottom: 8 }}>
              <Typography.Text strong>{o.title}</Typography.Text>
              <Typography.Text type="secondary">（权重 {o.weight}% · 进度 {o.progress}%）</Typography.Text>
              {o.description && (
                <div>
                  <Typography.Text type="secondary">{o.description}</Typography.Text>
                </div>
              )}
              {o.measure_criteria && (
                <div>
                  <Typography.Text type="secondary">衡量标准：{o.measure_criteria}</Typography.Text>
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    ) : null;

  const evalForm = (
    <>
      {objectiveBlock}
      <Form form={form} layout="vertical" onValuesChange={onValuesChange}>
      <Form.Item
        name="perf_score"
        label="业绩评分（1-5，0.25 分段）"
        rules={[{ required: true, message: "请打分" }]}
      >
        <InputNumber min={1} max={5} step={0.25} style={{ width: 200 }} inputMode="decimal" />
      </Form.Item>
      <ValueGradeForm />
      <Form.Item name="comment" label="评语（可选）">
        <Input.TextArea rows={3} />
      </Form.Item>
    </Form>
    </>
  );

  const evalTitle = editing ? `评价 ${editing.target_name}` : "";

  return (
    <Card title="我的互评任务">
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="请客观评价同事；被评人无法看到自己收到的评价内容，请安心填写"
      />
      {tasks.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Progress percent={progressPercent} size="small" />
          <Typography.Text type="secondary">
            已完成 {processedCount}/{tasks.length}（含已拒绝）
          </Typography.Text>
        </div>
      )}
      {loading ? (
        <div style={{ textAlign: "center", padding: 32 }}>
          <Spin />
        </div>
      ) : tasks.length === 0 ? (
        <Empty description="暂无互评任务" />
      ) : (
        <List
          // 待评价排前、已完成在后，组内保持原顺序（sort 稳定）
          dataSource={[...tasks].sort((a, b) => Number(a.status !== "pending") - Number(b.status !== "pending"))}
          renderItem={(t) => (
            <List.Item actions={actionsOf(t)}>
              <List.Item.Meta
                title={
                  <>
                    {t.target_name} {statusTag(t)}
                  </>
                }
                description={
                  t.status === "declined" && t.decline_reason
                    ? `${t.target_position ?? ""} · ${t.cycle_name} · 拒绝原因：${t.decline_reason}`
                    : `${t.target_position ?? ""} · ${t.cycle_name}`
                }
              />
            </List.Item>
          )}
        />
      )}

      {/* 评价表单：移动端全屏底部抽屉（键盘弹起不遮挡 + 底部固定提交），桌面端 Modal */}
      {isMobile ? (
        <Drawer
          open={!!editing}
          title={evalTitle}
          placement="bottom"
          height="100%"
          onClose={() => setEditing(null)}
          destroyOnClose
          classNames={{ wrapper: "pms-form-drawer" }}
        >
          {evalForm}
          <BottomActions>
            <Button type="primary" block loading={saving} onClick={onSubmit}>
              提交
            </Button>
          </BottomActions>
        </Drawer>
      ) : (
        <Modal
          open={!!editing}
          title={evalTitle}
          onOk={onSubmit}
          confirmLoading={saving}
          onCancel={() => setEditing(null)}
          destroyOnClose
        >
          {evalForm}
        </Modal>
      )}

      <Modal
        open={!!declining}
        title={declining ? `拒绝对 ${declining.target_name} 的互评` : ""}
        onOk={onDecline}
        confirmLoading={declineSaving}
        okText="确认拒绝"
        onCancel={() => setDeclining(null)}
        destroyOnClose
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="拒绝后该任务将标记为已拒绝，上级评估流程不再等待"
        />
        <Input.TextArea
          rows={3}
          placeholder="拒绝原因（可选），例如：与该同事合作较少，无法客观评价"
          value={declineReason}
          onChange={(e) => setDeclineReason(e.target.value)}
        />
      </Modal>
    </Card>
  );
}
