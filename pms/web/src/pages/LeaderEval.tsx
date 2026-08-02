// Leader 端：选周期 -> 列下属 -> 进入单人评估页
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Empty, List, Progress, Select, Space, Typography } from "antd";
import { api } from "@/services/api";
import { useAuth } from "@/stores/auth";
import StatusTag from "@/components/ui/StatusTag";
import type { StatusType } from "@/components/ui/StatusTag";
import TableCardList from "@/components/ui/TableCardList";
import type { CardColumn } from "@/components/ui/TableCardList";
import ResponsiveShow from "@/components/ui/ResponsiveShow";

interface Cycle {
  id: number;
  name: string;
  status: string;
}

interface Participant {
  id: number;
  cycle_id: number;
  user_id: number;
  user_name: string;
  user_position: string | null;
  status: string;
}

const PSTATUS_LABEL: Record<string, string> = {
  pending: "未开始自评",
  self_done: "等待上级评估",
  leader_done: "已完成上级评估",
  published: "已公布",
  excluded: "已排除",
};
const PSTATUS_TYPE: Record<string, StatusType> = {
  pending: "default",
  self_done: "warning",
  leader_done: "primary",
  published: "success",
  excluded: "default",
};

function actionText(status: string): string {
  if (status === "pending") return "等待自评";
  if (status === "self_done") return "去评估";
  return "查看";
}

export default function LeaderEval() {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selectedCycle, setSelectedCycle] = useState<number | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const navigate = useNavigate();
  const me = useAuth((s) => s.user)!;

  useEffect(() => {
    api.get<Cycle[]>("/v1/cycles").then((r) => {
      setCycles(r.data);
      // 默认选第一个进行中的
      const inp = r.data.find((c) => c.status === "in_progress");
      if (inp) setSelectedCycle(inp.id);
    });
  }, []);

  useEffect(() => {
    if (!selectedCycle) return;
    // 只拉自己的直属下属（不是全部参与人）
    api
      .get<{items: Participant[]; total: number}>(`/v1/cycles/${selectedCycle}/participants`, {
        params: { only_subordinates: true, page_size: 9999 },
      })
      .then((r) => setParticipants(r.data.items));
  }, [selectedCycle]);

  const visible = participants.filter((p) => p.user_id !== me.id);
  // 已评 = leader_done / published；self_done 为待评估；pending 为等待自评
  const total = visible.length;
  const doneCount = visible.filter(
    (p) => p.status === "leader_done" || p.status === "published"
  ).length;
  const todoCount = visible.filter((p) => p.status === "self_done").length;
  // 待评估（self_done）排最前，其余保持原顺序（sort 稳定）
  const sorted = [...visible].sort(
    (a, b) => Number(b.status === "self_done") - Number(a.status === "self_done")
  );

  const goDetail = (p: Participant): void => {
    navigate(`/leader/${p.cycle_id}/users/${p.user_id}`);
  };

  const cardColumns: CardColumn<Participant>[] = [
    { title: "姓名", dataIndex: "user_name" },
    { title: "职位", render: (p) => p.user_position ?? "-" },
    {
      title: "状态",
      render: (p) => (
        <StatusTag type={PSTATUS_TYPE[p.status] ?? "default"}>
          {PSTATUS_LABEL[p.status] ?? p.status}
        </StatusTag>
      ),
    },
    { title: "操作", render: (p) => <Typography.Link>{actionText(p.status)}</Typography.Link> },
  ];

  return (
    <Card
      title="下属评估"
      extra={
        <Select
          style={{ width: 320 }}
          placeholder="选择周期"
          value={selectedCycle ?? undefined}
          onChange={(v) => setSelectedCycle(v)}
          options={cycles.map((c) => ({
            value: c.id,
            label: `${c.name}（${c.status}）`,
          }))}
        />
      }
    >
      {visible.length === 0 ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Space direction="vertical" size={4}>
              <Typography.Text strong>没有可评估的下属</Typography.Text>
              <Typography.Text type="secondary">
                当前周期暂无分配给你的直属下属
              </Typography.Text>
            </Space>
          }
        />
      ) : (
        <>
          {/* 完成度汇总：还差几人没评 */}
          <div style={{ marginBottom: 16 }}>
            <Space style={{ width: "100%", justifyContent: "space-between" }}>
              <Typography.Text strong>
                待评估 {todoCount} 人 / 共 {total} 人
              </Typography.Text>
              <Typography.Text type="secondary">已评 {doneCount} 人</Typography.Text>
            </Space>
            <Progress
              percent={total > 0 ? Math.round((doneCount / total) * 100) : 0}
              size="small"
            />
          </div>
          {/* 桌面端：列表 */}
          <ResponsiveShow on="desktop">
            <List
              dataSource={sorted}
              renderItem={(p) => (
                <List.Item
                  actions={[
                    <a key="eval" onClick={() => goDetail(p)}>
                      {actionText(p.status)}
                    </a>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        {p.user_name}
                        <StatusTag type={PSTATUS_TYPE[p.status] ?? "default"}>
                          {PSTATUS_LABEL[p.status] ?? p.status}
                        </StatusTag>
                      </Space>
                    }
                    description={p.user_position}
                  />
                </List.Item>
              )}
            />
          </ResponsiveShow>
          {/* 移动端：卡片列表（.table-card-list 由 CSS 在 ≤767px 自动显示） */}
          <TableCardList<Participant>
            columns={cardColumns}
            dataSource={sorted}
            rowKey={(p) => p.id}
            onCardClick={goDetail}
          />
        </>
      )}
    </Card>
  );
}
