// 试用期管理主页面：列表视图
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ColumnsType } from "antd/es/table";
import { Button, Card, Input, message, Select, Space, Table, Tooltip, Typography, Upload } from "antd";
import { DownloadOutlined, ReloadOutlined, UploadOutlined } from "@ant-design/icons";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { hasAnyRole } from "@/components/RequireRole";
import { ROLE } from "@/App";
import StatusTag from "@/components/ui/StatusTag";
import type { StatusType } from "@/components/ui/StatusTag";
import TableCardList, { type CardColumn } from "@/components/ui/TableCardList";
import { showObjectiveImportResult, showOfflineObjectiveImportResult } from "@/components/ui/showImportResult";
import type { ObjectiveImportResult, OfflineObjectiveImportResult } from "@/services/api.types";


interface ProbationListItem {
  id: number;
  user_id: number;
  user_name: string;
  department_name: string | null;
  leader_name: string | null;
  start_date: string;
  end_date: string;
  remaining_days: number;
  status: string;
  status_text: string;
  has_evaluation: boolean;
}

// extended 原为 purple，StatusTag 无对应语义色，取中性 default
const STATUS_LABEL: Record<string, { text: string; type: StatusType }> = {
  draft: { text: "计划已创建", type: "default" },
  objective_draft: { text: "填写目标中", type: "primary" },
  objective_pending_review: { text: "目标待审批", type: "warning" },
  in_progress: { text: "试用期进行中", type: "info" },
  pending_evaluation: { text: "临转正，待评估", type: "warning" },
  completed: { text: "已完成", type: "success" },
  extended: { text: "已延期", type: "default" },
};

export default function Probation() {
  const navigate = useNavigate();
  const user = useAuth((s) => s.user)!;
  const isHr = hasAnyRole(user?.role, [...ROLE.HR]) || user?.has_hr_permission;

  const [items, setItems] = useState<ProbationListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [keyword, setKeyword] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);

  async function load() {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      if (keyword) params.keyword = keyword;
      const r = await api.get<ProbationListItem[]>("/v1/probation", { params });
      setItems(r.data);
    } catch (e) {
      message.error(formatError(e, "加载失败"));
    } finally {
      setLoading(false);
    }
  }

  async function syncPlans() {
    setSyncing(true);
    try {
      const r = await api.post<{ created: number }>("/v1/probation/sync-plans");
      message.success(`同步完成，新增 ${r.data.created} 个试用期计划`);
      load();
    } catch (e) {
      message.error(formatError(e, "同步失败"));
    } finally {
      setSyncing(false);
    }
  }

  // === 试用期目标导入 ===
  async function onUploadObjectives(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post<ObjectiveImportResult>("/v1/probation/import-objectives", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000, // Excel 导入解析较慢，覆盖默认 10s 超时
      });
      showObjectiveImportResult(r.data);
      load();
    } catch (e) {
      message.error(formatError(e, "导入失败"));
    }
    return false; // 阻止 antd 默认上传
  }

  // === 线下《目标设定及考核表》多文件导入 ===
  // antd Upload multiple 时 beforeUpload 会按文件逐个同步触发，先收集再合并为一次请求
  const offlineFilesRef = useRef<File[]>([]);

  async function uploadOfflineObjectives(files: File[]) {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    try {
      const r = await api.post<OfflineObjectiveImportResult>(
        "/v1/probation/import-offline-objectives",
        fd,
        {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 60000, // Excel 导入解析较慢，覆盖默认 10s 超时
        }
      );
      showOfflineObjectiveImportResult(r.data);
      load();
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

  useEffect(() => {
    load();
  }, [statusFilter]);

  // 桌面列（≤767px 时整个 Table 由 CSS 隐藏，改由 TableCardList 卡片呈现）
  const columns: ColumnsType<ProbationListItem> = [
    {
      title: "姓名",
      dataIndex: "user_name",
      key: "user_name",
      fixed: "left",
      width: 120,
    },
    {
      title: "部门",
      dataIndex: "department_name",
      key: "department_name",
      width: 140,
    },
    {
      title: "直属上级",
      dataIndex: "leader_name",
      key: "leader_name",
      width: 120,
    },
    {
      title: "开始日期",
      dataIndex: "start_date",
      key: "start_date",
      width: 120,
    },
    {
      title: "结束日期",
      dataIndex: "end_date",
      key: "end_date",
      width: 120,
    },
    {
      title: "剩余天数",
      dataIndex: "remaining_days",
      key: "remaining_days",
      width: 110,
      render: (v: number) => (v < 0 ? `已逾期 ${Math.abs(v)} 天` : `${v} 天`),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 160,
      render: (status: string, record: ProbationListItem) => {
        const cfg = STATUS_LABEL[status] ?? { text: record.status_text, type: "default" as StatusType };
        return <StatusTag type={cfg.type}>{cfg.text}</StatusTag>;
      },
    },
    {
      title: "操作",
      key: "action",
      fixed: "right",
      width: 120,
      render: (_: unknown, record: ProbationListItem) => (
        <Button type="link" size="small" onClick={() => navigate(`/probation/${record.user_id}`)}>
          查看
        </Button>
      ),
    },
  ];

  // 移动端卡片列：姓名 / 状态 / 剩余天数 + 操作区，点击卡片跳详情
  const cardColumns: CardColumn<ProbationListItem>[] = [
    { title: "姓名", dataIndex: "user_name" },
    {
      title: "状态",
      render: (record) => {
        const cfg = STATUS_LABEL[record.status] ?? { text: record.status_text, type: "default" as StatusType };
        return <StatusTag type={cfg.type}>{cfg.text}</StatusTag>;
      },
    },
    {
      title: "剩余天数",
      render: (record) =>
        record.remaining_days < 0 ? `已逾期 ${Math.abs(record.remaining_days)} 天` : `${record.remaining_days} 天`,
    },
  ];

  return (
    <div>
      <Typography.Title level={4}>试用期管理</Typography.Title>
      <Card style={{ marginTop: 16 }}>
        <Space wrap style={{ marginBottom: 16 }}>
          <Input.Search
            placeholder="搜索姓名"
            allowClear
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onSearch={load}
            style={{ width: 200 }}
          />
          <Select
            placeholder="状态筛选"
            allowClear
            style={{ width: 160 }}
            value={statusFilter}
            onChange={setStatusFilter}
            options={Object.entries(STATUS_LABEL).map(([k, v]) => ({ value: k, label: v.text }))}
          />
          <Button onClick={load} loading={loading}>
            刷新
          </Button>
          {isHr && (
            <Button icon={<ReloadOutlined />} onClick={syncPlans} loading={syncing}>
              同步试用期计划
            </Button>
          )}
          {isHr && (
            <>
              <Button icon={<DownloadOutlined />} href="/api/v1/probation/import-objectives/template">
                下载目标导入模板
              </Button>
              <Upload accept=".xlsx" showUploadList={false} beforeUpload={(f) => onUploadObjectives(f)}>
                <Button icon={<UploadOutlined />}>导入试用期目标</Button>
              </Upload>
              <Tooltip title="支持线下《目标设定及考核表》原表上传，每人一个文件，按工号匹配">
                <Upload
                  accept=".xlsx"
                  multiple
                  showUploadList={false}
                  beforeUpload={(f) => onSelectOfflineFiles(f)}
                >
                  <Button icon={<UploadOutlined />}>导入线下目标表</Button>
                </Upload>
              </Tooltip>
            </>
          )}
        </Space>

        <div className="pms-responsive-table">
          <Table
            rowKey="id"
            dataSource={items}
            columns={columns}
            loading={loading}
            size="small"
            pagination={false}
          />
        </div>
        <TableCardList<ProbationListItem>
          columns={cardColumns}
          dataSource={items}
          rowKey={(r) => r.id}
          onCardClick={(r) => navigate(`/probation/${r.user_id}`)}
          renderActions={(r) => (
            <Button type="link" size="small" onClick={() => navigate(`/probation/${r.user_id}`)}>
              查看
            </Button>
          )}
        />
      </Card>
    </div>
  );
}

