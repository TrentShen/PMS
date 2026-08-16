// 互评名单确认（Leader/HR 独立审核页）：选周期 → 下属待审列表 → 抽屉里审核并发起
// 从上级评估详情页拆出，保持"一件事一个页面"
import { useEffect, useState } from "react";
import { Button, Card, Drawer, Empty, List, Select, Space, Spin, Typography, message } from "antd";
import { api, formatError } from "@/services/api";
import PeerReviewPanel from "@/components/PeerReviewPanel";
import StatusTag from "@/components/ui/StatusTag";
import TableCardList from "@/components/ui/TableCardList";
import type { CardColumn } from "@/components/ui/TableCardList";
import { useMobile } from "@/hooks/useMobile";

interface Cycle {
  id: number;
  name: string;
  status: string;
}

interface ReviewItem {
  user_id: number;
  name: string;
  position: string | null;
  pending_count: number;
  approved_count: number;
}

// 审核状态：有待审 > 未提交 > 已发起
function reviewStatus(r: ReviewItem): { text: string; type: "warning" | "default" | "success" } {
  if (r.pending_count > 0) return { text: `待确认 ${r.pending_count} 人`, type: "warning" };
  if (r.approved_count > 0) return { text: "已发起", type: "success" };
  return { text: "员工未提交", type: "default" };
}

export default function PeerReview() {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selectedCid, setSelectedCid] = useState<number | null>(null);
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [cyclesLoading, setCyclesLoading] = useState(true);
  const [reviewing, setReviewing] = useState<ReviewItem | null>(null);
  // 审核发起成功后递增，触发列表刷新
  const [refreshKey, setRefreshKey] = useState(0);
  const isMobile = useMobile();

  useEffect(() => {
    setCyclesLoading(true);
    api
      .get<Cycle[]>("/v1/cycles")
      .then((r) => {
        const inp = r.data.filter((c) => c.status === "in_progress");
        setCycles(inp);
        if (inp.length > 0) setSelectedCid(inp[0].id);
      })
      .catch((e) => message.error(formatError(e, "加载周期列表失败")))
      .finally(() => setCyclesLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedCid) return;
    // 防响应乱序：快速切换周期时旧响应不覆盖新数据
    let cancelled = false;
    setLoading(true);
    api
      .get<ReviewItem[]>(`/v1/cycles/${selectedCid}/peer/review-list`)
      .then((r) => { if (!cancelled) setItems(r.data); })
      .catch((e) => { if (!cancelled) message.error(formatError(e, "加载待审名单失败")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selectedCid, refreshKey]);

  const selectedCycle = cycles.find((c) => c.id === selectedCid) ?? null;
  const pendingTotal = items.reduce((s, i) => s + i.pending_count, 0);

  const cardColumns: CardColumn<ReviewItem>[] = [
    { title: "姓名", dataIndex: "name" },
    { title: "职位", render: (r) => r.position ?? "-" },
    {
      title: "状态",
      render: (r) => {
        const s = reviewStatus(r);
        return <StatusTag type={s.type}>{s.text}</StatusTag>;
      },
    },
  ];

  const reviewButton = (r: ReviewItem) => (
    <Button size={isMobile ? undefined : "small"} onClick={() => setReviewing(r)}>
      审核
    </Button>
  );

  return (
    <Card
      title="互评名单确认"
      extra={
        <Select
          value={selectedCid ?? undefined}
          onChange={setSelectedCid}
          loading={cyclesLoading}
          style={{ width: "100%", maxWidth: 300 }}
          options={cycles.map((c) => ({ value: c.id, label: c.name }))}
        />
      }
    >
      {pendingTotal > 0 && (
        <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
          共 {pendingTotal} 条待审核的互评人提名
        </Typography.Text>
      )}
      {loading || cyclesLoading ? (
        <div style={{ textAlign: "center", padding: "var(--space-9) 0" }}>
          <Spin />
        </div>
      ) : cycles.length === 0 ? (
        <Empty description="暂无进行中的绩效周期" />
      ) : items.length === 0 ? (
        <Empty description="暂无需要审核的下属名单" />
      ) : isMobile ? (
        <TableCardList<ReviewItem>
          columns={cardColumns}
          dataSource={items}
          rowKey={(r) => r.user_id}
          renderActions={reviewButton}
        />
      ) : (
        <List
          dataSource={items}
          renderItem={(r) => {
            const s = reviewStatus(r);
            return (
              <List.Item actions={[reviewButton(r)]}>
                <List.Item.Meta
                  title={
                    <Space size={8}>
                      {r.name}
                      <StatusTag type={s.type}>{s.text}</StatusTag>
                    </Space>
                  }
                  description={r.position ?? ""}
                />
              </List.Item>
            );
          }}
        />
      )}

      {/* 审核抽屉：桌面右侧 640，移动端底部全屏 */}
      <Drawer
        open={!!reviewing}
        title={reviewing ? `审核 ${reviewing.name} 的互评名单` : ""}
        placement={isMobile ? "bottom" : "right"}
        height={isMobile ? "100%" : undefined}
        width={640}
        onClose={() => setReviewing(null)}
        destroyOnClose
        classNames={isMobile ? { wrapper: "pms-form-drawer" } : undefined}
      >
        {reviewing && selectedCycle && selectedCid && (
          <PeerReviewPanel
            cycleId={selectedCid}
            userId={reviewing.user_id}
            cycleStatus={selectedCycle.status}
            onChanged={() => setRefreshKey((k) => k + 1)}
          />
        )}
      </Drawer>
    </Card>
  );
}
