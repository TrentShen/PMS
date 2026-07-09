// HR 目标周期详情页：参与人管理、全员目标状态、Excel 导入、催办
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Upload,
  message,
} from "antd";
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import { api, formatError } from "@/services/api";
import type { Participant, UserBrief } from "@/services/api.types";


interface ObjectiveCycle {
  id: number;
  name: string;
  status: string;
  start_date: string;
  end_date: string;
}

interface Summary {
  total: number;
  pending: number;
  pending_review: number;
  approved: number;
}

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  draft: { text: "制定中", color: "default" },
  active: { text: "执行中", color: "blue" },
  completed: { text: "已结束", color: "green" },
};

const PSTATUS_LABEL: Record<string, { text: string; color: string }> = {
  pending: { text: "未提交", color: "default" },
  pending_review: { text: "待审批", color: "orange" },
  approved: { text: "已确认", color: "green" },
};

export default function ObjectiveCycleDetail() {
  const { id } = useParams();
  const [cycle, setCycle] = useState<ObjectiveCycle | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [users, setUsers] = useState<UserBrief[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [addingIds, setAddingIds] = useState<number[]>([]);
  const [urgeOpen, setUrgeOpen] = useState(false);
  const [urgeIds, setUrgeIds] = useState<number[]>([]);

  async function loadCycle() {
    const r = await api.get<ObjectiveCycle>(`/v1/objective-cycles/${id}`);
    setCycle(r.data);
  }

  async function loadParticipants() {
    const r = await api.get<{ items: Participant[]; total: number }>(`/v1/objective-cycles/${id}/participants?page_size=9999`);
    setParticipants(r.data.items);
  }

  async function loadUsers() {
    const r = await api.get<UserBrief[]>("/v1/users");
    setUsers(r.data);
  }

  async function loadSummary() {
    const r = await api.get<Summary>(`/v1/objective-cycles/${id}/objective-status-summary`);
    setSummary(r.data);
  }

  useEffect(() => {
    loadCycle();
    loadParticipants();
    loadUsers();
    loadSummary();
  }, [id]);

  async function onAddParticipants() {
    if (addingIds.length === 0) return;
    try {
      await api.post(`/v1/objective-cycles/${id}/participants`, { user_ids: addingIds });
      message.success(`已添加 ${addingIds.length} 位参与人`);
      setAddingIds([]);
      await loadParticipants();
      await loadSummary();
    } catch (e) {
      message.error(formatError(e, "添加失败"));
    }
  }

  async function onRemoveParticipant(participantId: number) {
    try {
      await api.delete(`/v1/objective-cycles/${id}/participants/${participantId}`);
      message.success("已移除");
      await loadParticipants();
      await loadSummary();
    } catch (e) {
      message.error(formatError(e, "移除失败"));
    }
  }

  async function onUploadExcel(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post(`/v1/objective-cycles/${id}/excel/import`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      message.success(`导入成功：${r.data.imported_rows} 行，${r.data.affected_users} 位员工`);
      await loadParticipants();
      await loadSummary();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string | { errors?: string[] } } } };
      const detail = err.response?.data?.detail;
      if (typeof detail === "object" && detail?.errors) {
        Modal.error({ title: "导入校验失败", content: detail.errors.join("\n"), width: 600 });
      } else {
        message.error(typeof detail === "string" ? detail : "导入失败");
      }
    }
    return false;
  }

  async function onUrge() {
    if (urgeIds.length === 0) return;
    try {
      // 复用评估周期的催办接口（企微通知）
      const r = await api.post("/v1/notify/urge-objectives", { objective_cycle_id: Number(id), user_ids: urgeIds });
      message.success(`已催办 ${r.data.sent} 人`);
      setUrgeOpen(false);
      setUrgeIds([]);
    } catch (e) {
      message.error(formatError(e, "催办失败"));
    }
  }

  const availableUsers = users.filter(
    (u) => u.role !== "super_admin" && u.role !== "hrbp" && !participants.find((p) => p.user_id === u.id)
  );
  const pendingParticipants = participants.filter((p) => p.status === "pending");

  if (!cycle) return null;

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title={cycle.name}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="状态">
            <Tag color={STATUS_LABEL[cycle.status]?.color}>{STATUS_LABEL[cycle.status]?.text}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="周期">{cycle.start_date} ~ {cycle.end_date}</Descriptions.Item>
        </Descriptions>
      </Card>

      {summary && (
        <Card title="目标状态汇总">
          <Space size="large">
            <span>参与人：{summary.total}</span>
            <span>未提交：{summary.pending}</span>
            <span>待审批：{summary.pending_review}</span>
            <span>已确认：{summary.approved}</span>
          </Space>
        </Card>
      )}

      <Card
        title="参与人目标状态"
        extra={
          <Space>
            <Button size="small" icon={<DownloadOutlined />} href="/api/v1/objective-cycles/excel/template">
              下载导入模板
            </Button>
            <Upload accept=".xlsx" showUploadList={false} beforeUpload={(f) => onUploadExcel(f)}>
              <Button size="small" icon={<UploadOutlined />}>Excel 导入目标</Button>
            </Upload>
            {cycle.status !== "completed" && (
              <Button
                size="small"
                onClick={() => { setUrgeIds(pendingParticipants.map((p) => p.user_id)); setUrgeOpen(true); }}
              >
                催办
              </Button>
            )}
          </Space>
        }
      >
        {cycle.status === "draft" && (
          <Space style={{ marginBottom: 16 }} wrap>
            <Select
              mode="multiple"
              placeholder="选择员工"
              style={{ width: 320 }}
              value={addingIds}
              onChange={setAddingIds}
              options={availableUsers.map((u) => ({ value: u.id, label: `${u.name}（${u.position ?? ""}）` }))}
            />
            <Button type="primary" onClick={onAddParticipants}>添加参与人</Button>
          </Space>
        )}

        {participants.length === 0 && <Alert type="info" message="尚未添加参与人" />}

        <Table
          rowKey="id"
          size="small"
          pagination={false}
          dataSource={participants}
          columns={[
            { title: "姓名", dataIndex: "user_name" },
            { title: "职位", dataIndex: "user_position" },
            { title: "部门", dataIndex: "dept_name_snapshot" },
            {
              title: "目标状态",
              dataIndex: "status",
              render: (v) => <Tag color={PSTATUS_LABEL[v]?.color}>{PSTATUS_LABEL[v]?.text}</Tag>,
            },
            {
              title: "操作",
              render: (_, r) =>
                cycle.status === "draft" ? (
                  <a style={{ color: "#ff4d4f" }} onClick={() => onRemoveParticipant(r.id)}>移除</a>
                ) : null,
            },
          ]}
        />
      </Card>

      <Modal title="催办未提交目标人员" open={urgeOpen} onCancel={() => setUrgeOpen(false)} onOk={onUrge}>
        <p>将向以下 {urgeIds.length} 人发送催办通知：</p>
        <Select
          mode="multiple"
          style={{ width: "100%" }}
          value={urgeIds}
          onChange={setUrgeIds}
          options={participants.map((p) => ({ value: p.user_id, label: `${p.user_name}（${PSTATUS_LABEL[p.status]?.text}）` }))}
        />
      </Modal>
    </Space>
  );
}
