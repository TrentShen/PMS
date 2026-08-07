// HR 目标周期详情页：参与人管理、全员目标状态、Excel 导入、催办
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tooltip,
  Typography,
  Upload,
  message,
} from "antd";
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import { api, formatError } from "@/services/api";
import type { OfflineObjectiveImportResult, ObjectiveCycleParticipant, UserBrief } from "@/services/api.types";
import { showOfflineObjectiveImportResult } from "@/components/ui/showImportResult";
import StatusTag from "@/components/ui/StatusTag";
import type { StatusType } from "@/components/ui/StatusTag";
import TableCardList from "@/components/ui/TableCardList";
import type { CardColumn } from "@/components/ui/TableCardList";


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

const STATUS_LABEL: Record<string, { text: string; type: StatusType }> = {
  draft: { text: "制定中", type: "default" },
  active: { text: "执行中", type: "primary" },
  completed: { text: "已结束", type: "success" },
};

const PSTATUS_LABEL: Record<string, { text: string; type: StatusType }> = {
  pending: { text: "未提交", type: "default" },
  pending_review: { text: "待审批", type: "warning" },
  approved: { text: "已确认", type: "success" },
};

export default function ObjectiveCycleDetail() {
  const { id } = useParams();
  const [cycle, setCycle] = useState<ObjectiveCycle | null>(null);
  const [participants, setParticipants] = useState<ObjectiveCycleParticipant[]>([]);
  const [users, setUsers] = useState<UserBrief[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [addingIds, setAddingIds] = useState<number[]>([]);
  const [urgeOpen, setUrgeOpen] = useState(false);
  const [urgeIds, setUrgeIds] = useState<number[]>([]);
  // 防重复提交：添加/移除参与人、催办在途标记
  const [adding, setAdding] = useState(false);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const [urging, setUrging] = useState(false);

  // 加载失败提示 + loadError 让页面停在错误态而非永久 Spin
  const [loadError, setLoadError] = useState("");

  async function loadCycle() {
    try {
      const r = await api.get<ObjectiveCycle>(`/v1/objective-cycles/${id}`);
      setCycle(r.data);
    } catch (e) {
      setLoadError(formatError(e, "加载失败"));
    }
  }

  async function loadParticipants() {
    const r = await api.get<{ items: ObjectiveCycleParticipant[]; total: number }>(`/v1/objective-cycles/${id}/participants?page_size=9999`);
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
    loadParticipants().catch((e) => message.error(formatError(e, "加载参与人失败")));
    loadUsers().catch((e) => message.error(formatError(e, "加载用户失败")));
    loadSummary().catch((e) => message.error(formatError(e, "加载目标状态失败")));
  }, [id]);

  async function onAddParticipants() {
    if (addingIds.length === 0) return;
    setAdding(true);
    try {
      await api.post(`/v1/objective-cycles/${id}/participants`, { user_ids: addingIds });
      message.success(`已添加 ${addingIds.length} 位参与人`);
      setAddingIds([]);
      await loadParticipants();
      await loadSummary();
    } catch (e) {
      message.error(formatError(e, "添加失败"));
    } finally {
      setAdding(false);
    }
  }

  async function onRemoveParticipant(participantId: number) {
    setRemovingId(participantId);
    try {
      await api.delete(`/v1/objective-cycles/${id}/participants/${participantId}`);
      message.success("已移除");
      await loadParticipants();
      await loadSummary();
    } catch (e) {
      message.error(formatError(e, "移除失败"));
    } finally {
      setRemovingId(null);
    }
  }

  async function onUploadExcel(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post(`/v1/objective-cycles/${id}/excel/import`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000, // Excel 导入解析较慢，覆盖默认 10s 超时
      });
      message.success(`导入成功：${r.data.imported_rows} 行，${r.data.affected_users} 位员工`);
      await loadParticipants();
      await loadSummary();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string | { errors?: string[] } } } };
      const detail = err.response?.data?.detail;
      if (typeof detail === "object" && detail?.errors) {
        Modal.error({
          title: "导入校验失败",
          width: 600,
          content: (
            <ul style={{ paddingLeft: 18, margin: 0 }}>
              {detail.errors.map((msg, i) => (
                <li key={i}>{msg}</li>
              ))}
            </ul>
          ),
        });
      } else {
        message.error(typeof detail === "string" ? detail : "导入失败");
      }
    }
    return false;
  }

  // === 线下《目标设定及考核表》多文件导入 ===
  // antd Upload multiple 时 beforeUpload 会按文件逐个同步触发，先收集再合并为一次请求
  const offlineFilesRef = useRef<File[]>([]);

  async function uploadOfflineObjectives(files: File[]) {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    try {
      const r = await api.post<OfflineObjectiveImportResult>(
        `/v1/objective-cycles/${id}/excel/import-offline`,
        fd,
        {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 60000, // Excel 导入解析较慢，覆盖默认 10s 超时
        }
      );
      showOfflineObjectiveImportResult(r.data);
      await loadParticipants();
      await loadSummary();
    } catch (e) {
      message.error(formatError(e, "导入失败"));
    }
  }

  function onSelectOfflineFiles(file: File) {
    offlineFilesRef.current.push(file);
    setTimeout(() => {
      const batch = offlineFilesRef.current;
      offlineFilesRef.current = [];
      if (batch.length > 0) void uploadOfflineObjectives(batch);
    }, 0);
    return false; // 阻止 antd 默认上传
  }

  async function onUrge() {
    if (urgeIds.length === 0) return;
    setUrging(true);
    try {
      // 复用评估周期的催办接口（企微通知）
      const r = await api.post("/v1/notify/urge-objectives", { objective_cycle_id: Number(id), user_ids: urgeIds });
      message.success(`已催办 ${r.data.sent} 人`);
      setUrgeOpen(false);
      setUrgeIds([]);
    } catch (e) {
      message.error(formatError(e, "催办失败"));
    } finally {
      setUrging(false);
    }
  }

  const availableUsers = users.filter(
    (u) => u.role !== "super_admin" && u.role !== "hrbp" && !participants.find((p) => p.user_id === u.id)
  );
  const pendingParticipants = participants.filter((p) => p.status === "pending");

  // 移动端卡片列：姓名 / 职位 / 部门 / 目标状态
  const participantCardColumns: CardColumn<ObjectiveCycleParticipant>[] = [
    { title: "姓名", dataIndex: "user_name" },
    { title: "职位", render: (p) => p.user_position ?? "-" },
    { title: "部门", render: (p) => p.dept_name_snapshot ?? "-" },
    {
      title: "目标状态",
      render: (p) => (
        <StatusTag type={PSTATUS_LABEL[p.status]?.type}>{PSTATUS_LABEL[p.status]?.text}</StatusTag>
      ),
    },
  ];

  if (!cycle) {
    if (loadError) {
      return (
        <div style={{ textAlign: "center", padding: 64 }}>
          <Typography.Text type="danger">{loadError}</Typography.Text>
        </div>
      );
    }
    return (
      <div style={{ textAlign: "center", padding: 64 }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title={cycle.name}>
        <Descriptions column={3} size="small">
          <Descriptions.Item label="状态">
            <StatusTag type={STATUS_LABEL[cycle.status]?.type}>{STATUS_LABEL[cycle.status]?.text}</StatusTag>
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
            <Tooltip title="支持线下《目标设定及考核表》原表上传，每人一个文件，按工号匹配">
              <Upload
                accept=".xlsx"
                multiple
                showUploadList={false}
                beforeUpload={(f) => onSelectOfflineFiles(f)}
              >
                <Button size="small" icon={<UploadOutlined />}>导入线下目标表</Button>
              </Upload>
            </Tooltip>
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
            <Button type="primary" onClick={onAddParticipants} loading={adding}>添加参与人</Button>
          </Space>
        )}

        {participants.length === 0 && <Alert type="info" message="尚未添加参与人" />}

        {/* 桌面端：表格；移动端：卡片列表（.table-card-list 由 CSS 在 ≤767px 自动显示） */}
        <div className="pms-responsive-table">
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
                render: (v) => <StatusTag type={PSTATUS_LABEL[v]?.type}>{PSTATUS_LABEL[v]?.text}</StatusTag>,
              },
              {
                title: "操作",
                render: (_, r) =>
                  cycle.status === "draft" ? (
                    <a
                      style={{ color: "var(--color-danger)" }}
                      onClick={() => { if (removingId == null) onRemoveParticipant(r.id); }}
                    >
                      移除
                    </a>
                  ) : null,
              },
            ]}
          />
        </div>
        <TableCardList<ObjectiveCycleParticipant>
          columns={participantCardColumns}
          dataSource={participants}
          rowKey={(p) => p.id}
          renderActions={(p) =>
            cycle.status === "draft" ? (
              <a
                style={{ color: "var(--color-danger)" }}
                onClick={() => { if (removingId == null) onRemoveParticipant(p.id); }}
              >
                移除
              </a>
            ) : null
          }
        />
      </Card>

      <Modal title="催办未提交目标人员" open={urgeOpen} onCancel={() => setUrgeOpen(false)} onOk={onUrge} confirmLoading={urging}>
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
