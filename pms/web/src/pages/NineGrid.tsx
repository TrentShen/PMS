// 人才盘点（九宫格，PRD 3.6.2）：绩效（横轴 A/B/C）× 潜力（纵轴 高/中/低）
// 数据：/v1/cycles/:id/nine-grid；潜力由 HR 在「用户与权限」中评定
import { Fragment, useEffect, useState } from "react";
import { Card, Empty, Select, Spin, Typography, message } from "antd";
import { api, formatError } from "@/services/api";
import StatusTag from "@/components/ui/StatusTag";
import { useMobile } from "@/hooks/useMobile";

interface Cycle {
  id: number;
  name: string;
  status: string;
}

interface Member {
  user_id: number;
  name: string;
  position: string | null;
  dept_name: string | null;
  final_perf_score: number | null;
  final_perf_level: string | null;
  potential_level: string | null;
}

interface Cell {
  perf_band: string; // A / B / C
  potential: string; // high / medium / low
  members: Member[];
}

interface NineGridData {
  cycle_id: number;
  cycle_name: string;
  cycle_status: string;
  cells: Cell[];
  unrated_potential: Member[];
  unset_count: number;
}

const BAND_LABEL: Record<string, string> = { A: "A 档（优秀/部分超出）", B: "B 档（符合预期）", C: "C 档（部分不符/不符合）" };
const POTENTIAL_LABEL: Record<string, string> = { high: "高潜力", medium: "中潜力", low: "低潜力" };
const PERF_LABEL: Record<string, string> = {
  excellent: "优秀", exceed_part: "部分超出", meet: "符合", below_part: "部分不符", below: "不符合",
};

// 象限色调：右上最佳（success）、中间过渡（info/warning）、左下最差（danger），全部走 tokens
const BAND_SCORE: Record<string, number> = { A: 2, B: 1, C: 0 };
const POTENTIAL_SCORE: Record<string, number> = { high: 2, medium: 1, low: 0 };
function cellBackground(band: string, potential: string): string {
  const score = (BAND_SCORE[band] ?? 0) + (POTENTIAL_SCORE[potential] ?? 0);
  if (score >= 3) return "var(--color-success-bg)";
  if (score === 2) return "var(--color-info-bg)";
  if (score === 1) return "var(--color-warning-bg)";
  return "var(--color-danger-bg)";
}

function CellCard({ cell }: { cell: Cell }) {
  return (
    <div
      style={{
        background: cellBackground(cell.perf_band, cell.potential),
        borderRadius: "var(--radius-lg)",
        padding: "var(--space-3)",
        minHeight: 96,
      }}
    >
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {cell.members.length} 人
      </Typography.Text>
      <div style={{ marginTop: 4, display: "flex", flexWrap: "wrap", gap: 4 }}>
        {cell.members.map((m) => (
          <StatusTag key={m.user_id} type="default">
            {m.name} {m.final_perf_score != null ? m.final_perf_score.toFixed(2) : ""}
          </StatusTag>
        ))}
      </div>
    </div>
  );
}

export default function NineGrid() {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selectedCid, setSelectedCid] = useState<number | null>(null);
  const [data, setData] = useState<NineGridData | null>(null);
  const [loading, setLoading] = useState(false);
  const [cyclesLoading, setCyclesLoading] = useState(true);
  const isMobile = useMobile();

  useEffect(() => {
    setCyclesLoading(true);
    api
      .get<Cycle[]>("/v1/cycles")
      .then((r) => {
        setCycles(r.data);
        // 默认选第一个进行中或已公布的周期
        const preferred = r.data.find((c) => c.status === "in_progress") ?? r.data[0];
        if (preferred) setSelectedCid(preferred.id);
      })
      .catch((e) => message.error(formatError(e, "加载周期列表失败")))
      .finally(() => setCyclesLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedCid) return;
    let cancelled = false;
    setLoading(true);
    api
      .get<NineGridData>(`/v1/cycles/${selectedCid}/nine-grid`)
      .then((r) => { if (!cancelled) setData(r.data); })
      .catch((e) => { if (!cancelled) message.error(formatError(e, "加载九宫格失败")); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [selectedCid]);

  // 纵轴：高潜力在上；横轴：C → A（左到右绩效递增）
  const potentials = ["high", "medium", "low"];
  const bands = ["C", "B", "A"];
  const cellOf = (band: string, potential: string): Cell =>
    data?.cells.find((c) => c.perf_band === band && c.potential === potential) ??
    { perf_band: band, potential, members: [] };

  return (
    <Card
      title="人才盘点（九宫格）"
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
      {loading || cyclesLoading ? (
        <div style={{ textAlign: "center", padding: "var(--space-9) 0" }}>
          <Spin />
        </div>
      ) : !data ? (
        <Empty description="请选择绩效周期" />
      ) : (
        <>
          <Typography.Text type="secondary" style={{ display: "block", marginBottom: 12 }}>
            横轴：绩效（左低右高）｜纵轴：潜力（下低上高）
            {data.unset_count > 0 && `｜另有 ${data.unset_count} 人未定绩效等级`}
          </Typography.Text>
          <div
            role="img"
            aria-label={`九宫格人才盘点：${data.cycle_name}`}
            style={{
              display: "grid",
              gridTemplateColumns: isMobile ? "56px 1fr" : "56px repeat(3, 1fr)",
              gap: "var(--space-2)",
            }}
          >
            {potentials.map((potential) => (
              <Fragment key={potential}>
                <div
                  style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
                >
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {POTENTIAL_LABEL[potential]}
                  </Typography.Text>
                </div>
                {isMobile ? (
                  // 移动端：一行一档，该潜力行内三档纵向堆叠
                  <div style={{ display: "grid", gap: "var(--space-2)" }}>
                    {bands.map((band) => (
                      <div key={band}>
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {BAND_LABEL[band]}
                        </Typography.Text>
                        <CellCard cell={cellOf(band, potential)} />
                      </div>
                    ))}
                  </div>
                ) : (
                  bands.map((band) => (
                    <CellCard key={`${potential}-${band}`} cell={cellOf(band, potential)} />
                  ))
                )}
              </Fragment>
            ))}
            {/* 桌面端底部横轴标签 */}
            {!isMobile && (
              <>
                <div />
                {bands.map((band) => (
                  <div key={`x-${band}`} style={{ textAlign: "center" }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {BAND_LABEL[band]}
                    </Typography.Text>
                  </div>
                ))}
              </>
            )}
          </div>

          {data.unrated_potential.length > 0 && (
            <Card type="inner" size="small" style={{ marginTop: 16 }} title="潜力未评定（已定绩效等级）">
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {data.unrated_potential.map((m) => (
                  <StatusTag key={m.user_id} type="warning">
                    {m.name}（{PERF_LABEL[m.final_perf_level ?? ""] ?? "-"}）
                  </StatusTag>
                ))}
              </div>
              <Typography.Text type="secondary" style={{ display: "block", marginTop: 8, fontSize: 12 }}>
                请在「用户与权限」中为这些员工评定潜力后，他们会自动落入对应象限
              </Typography.Text>
            </Card>
          )}
        </>
      )}
    </Card>
  );
}
