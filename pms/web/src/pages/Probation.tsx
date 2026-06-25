// 试用期管理主页面：列表视图
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ColumnsType } from "antd/es/table";
import { Button, Card, Input, message, Select, Space, Table, Tag, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";
import { hasAnyRole } from "@/components/RequireRole";
import { ROLE } from "@/App";
import { useMobile } from "@/hooks/useMobile";

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

const STATUS_LABEL: Record<string, { text: string; color: string }> = {
  draft: { text: "计划已创建", color: "default" },
  objective_draft: { text: "填写目标中", color: "blue" },
  objective_pending_review: { text: "目标待审批", color: "orange" },
  in_progress: { text: "试用期进行中", color: "processing" },
  pending_evaluation: { text: "临转正，待评估", color: "warning" },
  completed: { text: "已完成", color: "success" },
  extended: { text: "已延期", color: "purple" },
};

export default function Probation() {
  const navigate = useNavigate();
  const user = useAuth((s) => s.user)!;
  const isMobile = useMobile();
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
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "加载失败");
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
    } catch (e: any) {
      message.error(e?.response?.data?.detail ?? "同步失败");
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    load();
  }, [statusFilter]);

  const columns: ColumnsType<ProbationListItem> = [
    {
      title: "姓名",
      dataIndex: "user_name",
      key: "user_name",
      fixed: isMobile ? undefined : "left",
      width: isMobile ? 100 : 120,
    },
    {
      title: "部门",
      dataIndex: "department_name",
      key: "department_name",
      width: isMobile ? 100 : 140,
    },
    {
      title: "直属上级",
      dataIndex: "leader_name",
      key: "leader_name",
      width: isMobile ? 100 : 120,
    },
    {
      title: "开始日期",
      dataIndex: "start_date",
      key: "start_date",
      width: isMobile ? 110 : 120,
    },
    {
      title: "结束日期",
      dataIndex: "end_date",
      key: "end_date",
      width: isMobile ? 110 : 120,
    },
    {
      title: "剩余天数",
      dataIndex: "remaining_days",
      key: "remaining_days",
      width: isMobile ? 90 : 110,
      render: (v: number) => (v < 0 ? `已逾期 ${Math.abs(v)} 天` : `${v} 天`),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: isMobile ? 120 : 160,
      render: (status: string, record: ProbationListItem) => {
        const cfg = STATUS_LABEL[status] ?? { text: record.status_text, color: "default" };
        return <Tag color={cfg.color}>{cfg.text}</Tag>;
      },
    },
    {
      title: "操作",
      key: "action",
      fixed: isMobile ? undefined : "right",
      width: isMobile ? 90 : 120,
      render: (_: unknown, record: ProbationListItem) => (
        <Button type="link" size="small" onClick={() => navigate(`/probation/${record.user_id}`)}>
          查看
        </Button>
      ),
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
        </Space>

        <Table
          rowKey="id"
          dataSource={items}
          columns={columns}
          loading={loading}
          size="small"
          scroll={{ x: isMobile ? 700 : undefined }}
          pagination={false}
        />
      </Card>
    </div>
  );
}

