// 互评名单审核面板：Leader 审核某员工的互评候选人（追加/移除/确认发起）
// 从 LeaderEvalDetail 抽出，供独立的互评名单审核页（/peer-review）使用
import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Popconfirm,
  Select,
  Space,
  Table,
  Typography,
  message,
} from "antd";
import { api, formatError } from "@/services/api";
import StatusTag from "@/components/ui/StatusTag";
import TableCardList from "@/components/ui/TableCardList";
import type { CardColumn } from "@/components/ui/TableCardList";

// 互评三态：pending（员工选的）/ approved（已发起）/ removed（Leader 删除）
interface PeerCandidate {
  user_id: number;
  name: string;
  position: string | null;
  status: string;
  proposed_by: string | null;
}

export default function PeerReviewPanel({
  cycleId,
  userId,
  cycleStatus,
  onChanged,
}: {
  cycleId: number;
  userId: number;
  cycleStatus: string;
  /** 确认发起成功后回调（父页面可借此刷新待审列表） */
  onChanged?: () => void;
}) {
  const [cands, setCands] = useState<PeerCandidate[]>([]);
  const [allUsers, setAllUsers] = useState<{ id: number; name: string; position: string | null }[]>([]);
  const [addIds, setAddIds] = useState<number[]>([]);
  const [removeIds, setRemoveIds] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const r = await api.get<PeerCandidate[]>(`/v1/cycles/${cycleId}/users/${userId}/peer/pending`);
      setCands(r.data);
      // 候选人：脱敏同事列表（/v1/cycles/:id/participants 按 scope 过滤，员工视角下可选人恒为空）
      const u = await api.get<{ id: number; name: string; position: string | null }[]>("/v1/users/colleagues");
      setAllUsers(u.data.filter((x) => x.id !== userId));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load().catch((e) => message.error(formatError(e, "加载互评名单失败")));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cycleId, userId]);

  const pending = cands.filter((c) => c.status === "pending");
  const approved = cands.filter((c) => c.status === "approved");
  const removed = cands.filter((c) => c.status === "removed");
  const canEdit = cycleStatus === "in_progress" && approved.length === 0;

  // 桌面表格与移动端卡片共用同一套渲染
  function peerStatusTag(v: string) {
    return v === "approved" ? (
      <StatusTag type="success">已发起互评</StatusTag>
    ) : v === "removed" ? (
      <StatusTag>已移除</StatusTag>
    ) : (
      <StatusTag type="warning">待审核</StatusTag>
    );
  }

  function peerRemoveAction(r: PeerCandidate) {
    return canEdit && r.status === "pending" ? (
      <a onClick={() => setRemoveIds((prev) => Array.from(new Set([...prev, r.user_id])))}>
        拟移除
      </a>
    ) : null;
  }

  const peerCardColumns: CardColumn<PeerCandidate>[] = [
    { title: "姓名", dataIndex: "name" },
    { title: "职位", render: (c) => c.position ?? "-" },
    {
      title: "来源",
      render: (c) =>
        c.proposed_by === "leader" ? (
          <StatusTag type="primary">上级加</StatusTag>
        ) : (
          <StatusTag>员工选</StatusTag>
        ),
    },
    { title: "状态", render: (c) => peerStatusTag(c.status) },
  ];

  async function onConfirm() {
    setSaving(true);
    try {
      const r = await api.post(
        `/v1/cycles/${cycleId}/users/${userId}/peer/approve`,
        {
          add_user_ids: addIds,
          remove_user_ids: removeIds,
        }
      );
      message.success(`已发起互评：新增 ${r.data.approved_tasks} 人，共 ${r.data.total_peers} 人`);
      setAddIds([]);
      setRemoveIds([]);
      await load();
      onChanged?.();
    } catch (e) {
      message.error(formatError(e, "操作失败"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card title="互评名单审核">
      {approved.length > 0 && (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 12 }}
          message={`已发起 ${approved.length} 人的正式互评；不能再修改`}
        />
      )}
      {!loading && cands.length === 0 && approved.length === 0 && (
        <Alert type="info" showIcon message="员工尚未提交互评人邀请" style={{ marginBottom: 12 }} />
      )}

      {(pending.length > 0 || removed.length > 0 || approved.length > 0) && (
        <>
          {/* 桌面端：表格 */}
          <div className="pms-responsive-table" style={{ marginBottom: 16 }}>
            <Table
              size="small"
              rowKey="user_id"
              pagination={false}
              dataSource={cands}
              columns={[
                { title: "姓名", dataIndex: "name" },
                { title: "职位", dataIndex: "position" },
                {
                  title: "来源",
                  dataIndex: "proposed_by",
                  render: (v) => (v === "leader" ? <StatusTag type="primary">上级加</StatusTag> : <StatusTag>员工选</StatusTag>),
                },
                {
                  title: "状态",
                  dataIndex: "status",
                  render: (v) => peerStatusTag(v),
                },
                {
                  title: "操作",
                  render: (_, r) => peerRemoveAction(r),
                },
              ]}
            />
          </div>
          {/* 移动端：卡片列表（.table-card-list 由 CSS 在 ≤767px 自动显示） */}
          <TableCardList<PeerCandidate>
            columns={peerCardColumns}
            dataSource={cands}
            rowKey={(c) => c.user_id}
            renderActions={peerRemoveAction}
          />
        </>
      )}

      {canEdit && (
        <Space direction="vertical" style={{ width: "100%" }}>
          <div>
            <Typography.Text>追加互评人：</Typography.Text>
            <Select
              mode="multiple"
              value={addIds}
              onChange={setAddIds}
              style={{ width: "100%", maxWidth: 360 }}
              placeholder="选同事"
              options={allUsers
                .filter((u) => !cands.find((c) => c.user_id === u.id))
                .map((u) => ({ value: u.id, label: `${u.name}（${u.position ?? ""}）` }))}
            />
          </div>
          {removeIds.length > 0 && (
            <div>
              <Typography.Text type="danger">
                将移除：{cands.filter((c) => removeIds.includes(c.user_id)).map((c) => c.name).join(", ")}
              </Typography.Text>
            </div>
          )}
          <Popconfirm
            title="确认发起互评？"
            description="发起后将生成正式互评任务，名单不能再修改"
            okText="确认发起"
            cancelText="取消"
            onConfirm={onConfirm}
          >
            <Button type="primary" loading={saving}>
              确认并发起互评
            </Button>
          </Popconfirm>
        </Space>
      )}
    </Card>
  );
}
