// Leader 端：选周期 -> 列下属 -> 进入单人评估页
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Empty, List, Progress, Select, Space, Typography, message } from "antd";
import { api, formatError } from "@/services/api";
import { useAuth } from "@/stores/auth";
import StatusTag from "@/components/ui/StatusTag";
import { PARTICIPANT_STATUS_LABEL, PARTICIPANT_STATUS_TYPE } from "@/components/ui/participantStatus";
import TableCardList from "@/components/ui/TableCardList";
import type { CardColumn } from "@/components/ui/TableCardList";
import ResponsiveShow from "@/components/ui/ResponsiveShow";

interface Cycle {
  id: number;
  name: string;
  status: string;
  enable_feedback: boolean;
}

interface Participant {
  id: number;
  cycle_id: number;
  user_id: number;
  user_name: string;
  user_position: string | null;
  status: string;
}

// 评估周期状态中文映射（与 LeaderEvalDetail 的 CYCLE_STATUS_LABEL 一致）
const CYCLE_STATUS_LABEL: Record<string, string> = {
  draft: "草稿", in_progress: "进行中", published: "已公布", closed: "已关闭",
};

function actionText(status: string): string {
  if (status === "pending") return "等待自评";
  if (status === "self_done") return "去评估";
  return "查看";
}

export default function LeaderEval() {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [cyclesLoading, setCyclesLoading] = useState(false);
  const [selectedCycle, setSelectedCycle] = useState<number | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const me = useAuth((s) => s.user)!;

  useEffect(() => {
    let cancelled = false;
    setCyclesLoading(true);
    api.get<Cycle[]>("/v1/cycles").then((r) => {
      if (cancelled) return;
      setCycles(r.data);
      // 默认选第一个进行中的
      const inp = r.data.find((c) => c.status === "in_progress");
      if (inp) setSelectedCycle(inp.id);
    }).catch((e) => { if (!cancelled) message.error(formatError(e, "加载周期列表失败")); })
      .finally(() => { if (!cancelled) setCyclesLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!selectedCycle) return;
    // 只拉自己的直属下属（不是全部参与人）；防响应乱序：快速切周期时旧响应不覆盖
    let cancelled = false;
    setLoading(true);
    api
      .get<{items: Participant[]; total: number}>(`/v1/cycles/${selectedCycle}/participants`, {
        params: { only_subordinates: true, page_size: 9999 },
      })
      .then((r) => { if (!cancelled) setParticipants(r.data.items); })
      .catch((e) => { if (!cancelled) message.error(formatError(e, "加载下属列表失败")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
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

  // 反馈填写入口：周期进行中且开启反馈环节、上级评估已完成的下属，可直达面谈记录页
  const selectedCycleObj = cycles.find((c) => c.id === selectedCycle) ?? null;
  const feedbackEnabled = selectedCycleObj?.status === "in_progress" && selectedCycleObj.enable_feedback;
  const canWriteFeedback = (p: Participant): boolean =>
    !!feedbackEnabled && (p.status === "leader_done" || p.status === "published");
  const goFeedback = (p: Participant): void => {
    navigate(`/feedback/${p.cycle_id}/${p.user_id}`);
  };

  const cardColumns: CardColumn<Participant>[] = [
    { title: "姓名", dataIndex: "user_name" },
    { title: "职位", render: (p) => p.user_position ?? "-" },
    {
      title: "状态",
      render: (p) => (
        <StatusTag type={PARTICIPANT_STATUS_TYPE[p.status] ?? "default"}>
          {PARTICIPANT_STATUS_LABEL[p.status] ?? p.status}
        </StatusTag>
      ),
    },
  ];

  return (
    <Card
      title="下属评估"
      extra={
        <Select
          style={{ width: "100%", maxWidth: 320 }}
          placeholder="选择周期"
          loading={cyclesLoading}
          value={selectedCycle ?? undefined}
          onChange={(v) => setSelectedCycle(v)}
          options={cycles.map((c) => ({
            value: c.id,
            label: `${c.name}（${CYCLE_STATUS_LABEL[c.status] ?? c.status}）`,
          }))}
        />
      }
    >
      {!loading && !cyclesLoading && visible.length === 0 ? (
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
              loading={loading || cyclesLoading}
              dataSource={sorted}
              renderItem={(p) => (
                <List.Item
                  actions={[
                    <a key="eval" onClick={() => goDetail(p)}>
                      {actionText(p.status)}
                    </a>,
                    ...(canWriteFeedback(p)
                      ? [<a key="fb" onClick={() => goFeedback(p)}>反馈</a>]
                      : []),
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        {p.user_name}
                        <StatusTag type={PARTICIPANT_STATUS_TYPE[p.status] ?? "default"}>
                          {PARTICIPANT_STATUS_LABEL[p.status] ?? p.status}
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
            loading={loading || cyclesLoading}
            onCardClick={goDetail}
            renderActions={(p) =>
              canWriteFeedback(p) ? (
                <a onClick={() => goFeedback(p)}>写面谈反馈</a>
              ) : undefined
            }
          />
        </>
      )}
    </Card>
  );
}
