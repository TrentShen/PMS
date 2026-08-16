// HR 绩效看板：展示某个绩效周期各环节整体进度
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Card, Col, Empty, Progress, Row, Select, Space, Statistic, Typography, message } from "antd";
import { Column } from "@ant-design/charts";
import KPIScrollGrid from "@/components/ui/KPIScrollGrid";
import ResponsiveShow from "@/components/ui/ResponsiveShow";
import StatusTag from "@/components/ui/StatusTag";
import TableCardList from "@/components/ui/TableCardList";
import type { CardColumn } from "@/components/ui/TableCardList";
import { api, formatError } from "@/services/api";


interface CycleBrief {
  id: number;
  name: string;
  status: string;
  start_date: string;
  end_date: string;
  objective_cycle_id: number | null;
}

interface DepartmentProgress {
  department_id: number;
  department_name: string;
  total: number;
  done: number;
  undone: number;
}

interface DashboardData {
  cycle: CycleBrief;
  objective_cycle_participant_count: number;
  objective_submitted_count: number;
  performance_participant_count: number;
  self_eval_done: number;
  self_eval_total: number;
  peer_list_confirmed: number;
  peer_eval_done: number;
  superior_eval_done: number;
  superior_eval_total: number;
  calibration_done: number;
  calibration_total: number;
  approval_status: string;
  feedback_filled: number;
  feedback_confirmed: number;
  feedback_total: number;
  result_distribution: { level: string; count: number }[];
  self_eval_progress_by_department: DepartmentProgress[];
  peer_eval_progress_by_department: DepartmentProgress[];
}

// 部门自评/互评进度合并视图（仅展示层合并，不改动接口数据）
interface MergedDeptProgress {
  department_id: number;
  department_name: string;
  self_done: number;
  self_total: number;
  peer_done: number;
  peer_total: number;
}

interface KpiItem {
  title: string;
  value: number | string;
  suffix: string;
  color?: string;
}

const STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  in_progress: "进行中",
  published: "已公布",
  closed: "已归档",
};

// 审批状态文案（与后端 CycleApproval.status 口径一致，无记录=校准中）
const APPROVAL_STATUS_LABEL: Record<string, string> = {
  calibrating: "校准中",
  pending_hr: "待 HR 审批",
  pending_ceo: "待 CEO 审批",
  approved: "审批已通过",
  rejected_by_hr: "HR 已驳回",
  rejected_by_ceo: "CEO 已驳回",
};

// 结果分布等级文案（与后端 PerfLevel 一致）
const RESULT_LEVEL_LABEL: Record<string, string> = {
  excellent: "优秀",
  exceed_part: "部分超出",
  meet: "符合",
  below_part: "部分不符",
  below: "不符合",
  unset: "未定级",
};

// @ant-design/charts 需要具体色值字符串，运行时从设计令牌读取（fallback 与 tokens.css 保持一致）
function getChartColor(token: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  return v || fallback;
}

// 图表色板（顺序对应 --color-chart-1~6）
const CHART_COLOR_TOKENS: [string, string][] = [
  ["--color-chart-1", "#3370FF"],
  ["--color-chart-2", "#14C9C9"],
  ["--color-chart-3", "#F7BA1E"],
  ["--color-chart-4", "#F53F3F"],
  ["--color-chart-5", "#86909C"],
  ["--color-chart-6", "#00B42A"],
];

function percentOf(done: number, total: number): number {
  return total === 0 ? 0 : Math.round((done / total) * 100);
}

// 按 department_id 合并自评/互评两条部门进度列表，供双进度条与对比图使用
function mergeDepartmentProgress(
  selfList: DepartmentProgress[],
  peerList: DepartmentProgress[]
): MergedDeptProgress[] {
  const map = new Map<number, MergedDeptProgress>();
  for (const d of selfList) {
    map.set(d.department_id, {
      department_id: d.department_id,
      department_name: d.department_name,
      self_done: d.done,
      self_total: d.total,
      peer_done: 0,
      peer_total: 0,
    });
  }
  for (const d of peerList) {
    const existing = map.get(d.department_id);
    if (existing) {
      existing.peer_done = d.done;
      existing.peer_total = d.total;
    } else {
      map.set(d.department_id, {
        department_id: d.department_id,
        department_name: d.department_name,
        self_done: 0,
        self_total: 0,
        peer_done: d.done,
        peer_total: d.total,
      });
    }
  }
  // 按总人数倒序，便于看重点部门
  return [...map.values()].sort(
    (a, b) => b.self_total + b.peer_total - (a.self_total + a.peer_total)
  );
}

function deptStatusTag(d: MergedDeptProgress): ReactNode {
  const finished =
    d.self_total > 0 &&
    d.peer_total > 0 &&
    d.self_done === d.self_total &&
    d.peer_done === d.peer_total;
  return finished ? (
    <StatusTag type="success">已完成</StatusTag>
  ) : (
    <StatusTag type="primary">进行中</StatusTag>
  );
}

export default function HrDashboard() {
  const [cycles, setCycles] = useState<CycleBrief[]>([]);
  const [cyclesLoaded, setCyclesLoaded] = useState(false);
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<CycleBrief[]>("/v1/cycles").then((r) => {
      setCycles(r.data);
      setCyclesLoaded(true);
      if (r.data.length > 0 && !selectedCycleId) {
        setSelectedCycleId(r.data[0].id);
      }
    }).catch((e) => message.error(formatError(e, "加载失败")));
  }, []);

  useEffect(() => {
    if (!selectedCycleId) return;
    setLoading(true);
    // 切周期先清空旧数据，避免残留上一周期的看板内容
    setData(null);
    api.get<DashboardData>(`/v1/cycles/${selectedCycleId}/dashboard`)
      .then((r) => setData(r.data))
      .catch((e) => message.error(formatError(e, "加载失败")))
      .finally(() => setLoading(false));
  }, [selectedCycleId]);

  const chartColors = CHART_COLOR_TOKENS.map(([token, fallback]) => getChartColor(token, fallback));

  const mergedDepts: MergedDeptProgress[] = data
    ? mergeDepartmentProgress(
        data.self_eval_progress_by_department,
        data.peer_eval_progress_by_department
      )
    : [];

  const kpiItems: KpiItem[] = data
    ? [
        {
          title: "参与绩效目标设定人数",
          value: data.objective_cycle_participant_count,
          suffix: "人",
        },
        {
          title: "目标提交",
          value: data.objective_submitted_count,
          suffix: `/ ${data.objective_cycle_participant_count}`,
          color:
            data.objective_submitted_count === data.objective_cycle_participant_count
              ? "var(--color-success)"
              : "var(--color-primary)",
        },
        { title: "参与绩效评估人数", value: data.performance_participant_count, suffix: "人" },
        {
          title: "自评完成",
          value: data.self_eval_done,
          suffix: `/ ${data.self_eval_total}`,
          color:
            data.self_eval_done === data.self_eval_total
              ? "var(--color-success)"
              : "var(--color-primary)",
        },
        { title: "互评名单确认", value: data.peer_list_confirmed, suffix: "人" },
        { title: "互评完成", value: data.peer_eval_done, suffix: "人" },
        {
          title: "上级评估完成",
          value: data.superior_eval_done,
          suffix: `/ ${data.superior_eval_total}`,
          color:
            data.superior_eval_done === data.superior_eval_total
              ? "var(--color-success)"
              : "var(--color-primary)",
        },
        {
          title: "已定分（校准）",
          value: data.calibration_done,
          suffix: `/ ${data.calibration_total}`,
          color:
            data.calibration_done === data.calibration_total
              ? "var(--color-success)"
              : "var(--color-primary)",
        },
        {
          title: "审批状态",
          value: APPROVAL_STATUS_LABEL[data.approval_status] ?? data.approval_status,
          suffix: "",
        },
        {
          title: "反馈确认",
          value: data.feedback_confirmed,
          suffix: `/ ${data.feedback_total}`,
          color:
            data.feedback_confirmed === data.feedback_total
              ? "var(--color-success)"
              : "var(--color-primary)",
        },
      ]
    : [];

  // 绩效结果分布图数据（进行中=校准定分情况，发布后=最终等级分布）
  const resultChartData = (data?.result_distribution ?? []).map((d) => ({
    level: RESULT_LEVEL_LABEL[d.level] ?? d.level,
    count: d.count,
  }));

  // 部门自评/互评完成率对比图数据（色板前两色：自评 --color-chart-1、互评 --color-chart-2）
  const deptChartData = mergedDepts.flatMap((d) => [
    {
      department: d.department_name,
      type: "自评",
      percent: percentOf(d.self_done, d.self_total),
    },
    {
      department: d.department_name,
      type: "互评",
      percent: percentOf(d.peer_done, d.peer_total),
    },
  ]);

  // 移动端部门卡片列：部门名、自评完成率、互评完成率、状态
  const deptCardColumns: CardColumn<MergedDeptProgress>[] = [
    { title: "部门", dataIndex: "department_name" },
    {
      title: "自评完成率",
      render: (d) => `${d.self_done}/${d.self_total}（${percentOf(d.self_done, d.self_total)}%）`,
    },
    {
      title: "互评完成率",
      render: (d) => `${d.peer_done}/${d.peer_total}（${percentOf(d.peer_done, d.peer_total)}%）`,
    },
    { title: "状态", render: (d) => deptStatusTag(d) },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card title="绩效看板">
        <Select
          style={{ width: 320, maxWidth: "100%" }}
          placeholder="选择绩效周期"
          value={selectedCycleId}
          onChange={(v) => setSelectedCycleId(v)}
          options={cycles.map((c) => ({ value: c.id, label: `${c.name}（${STATUS_LABEL[c.status]}）` }))}
        />
      </Card>

      {/* 无绩效周期：整页空态（加载完成后再判定，避免首屏闪空态） */}
      {cyclesLoaded && cycles.length === 0 && (
        <Card>
          <Empty description="暂无绩效周期" />
        </Card>
      )}

      {!data && loading && <Card loading />}

      {data && (        <>
          <Card title={data.cycle.name}>
            <ResponsiveShow on="desktop">
              <Row gutter={[16, 16]}>
                {kpiItems.map((item) => (
                  <Col xs={12} md={8} lg={4} key={item.title}>
                    <Statistic
                      title={item.title}
                      value={item.value}
                      suffix={item.suffix}
                      valueStyle={item.color ? { color: item.color } : undefined}
                    />
                  </Col>
                ))}
              </Row>
            </ResponsiveShow>
            <ResponsiveShow on="mobile">
              <KPIScrollGrid>
                {kpiItems.map((item) => (
                  <div
                    key={item.title}
                    style={{
                      background: "var(--color-surface-raised)",
                      border: "1px solid var(--color-border)",
                      borderRadius: "var(--radius-lg)",
                      padding: "var(--space-4)",
                    }}
                  >
                    <Statistic
                      title={item.title}
                      value={item.value}
                      suffix={item.suffix}
                      valueStyle={item.color ? { color: item.color } : undefined}
                    />
                  </div>
                ))}
              </KPIScrollGrid>
            </ResponsiveShow>
          </Card>

          {/* 绩效结果分布：桌面柱图；移动端降级为文本列表 */}
          <Card title="绩效结果分布">
            <ResponsiveShow on="desktop">
              <div
                role="img"
                aria-label={`绩效结果分布柱状图：${resultChartData.map((d) => `${d.level} ${d.count} 人`).join("，")}`}
              >
                <Column
                  data={resultChartData}
                  xField="level"
                  yField="count"
                  color={chartColors[0]}
                  height={240}
                  yAxis={{ min: 0 }}
                />
              </div>
            </ResponsiveShow>
            <ResponsiveShow on="mobile">
              <Space direction="vertical" size={4}>
                {resultChartData.map((d) => (
                  <Typography.Text key={d.level}>
                    {d.level}：{d.count} 人
                  </Typography.Text>
                ))}
              </Space>
            </ResponsiveShow>
          </Card>

          {mergedDepts.length > 0 && (
            <Card title="部门完成率对比">
              {/* 桌面：柱图；移动端：降级为完成率文本列表（375px 下分组柱图不可读） */}
              <ResponsiveShow on="desktop">
                <div
                  role="img"
                  aria-label={`各部门自评互评完成率对比柱状图：${mergedDepts.map((d) => `${d.department_name}自评 ${percentOf(d.self_done, d.self_total)}%、互评 ${percentOf(d.peer_done, d.peer_total)}%`).join("，")}`}
                >
                  <Column
                    data={deptChartData}
                    xField="department"
                    yField="percent"
                    seriesField="type"
                    color={chartColors}
                    height={280}
                    yAxis={{ max: 100 }}
                    tooltip={{
                      formatter: (d: { type: string; percent: number }) => ({
                        name: d.type,
                        value: `${d.percent}%`,
                      }),
                    }}
                  />
                </div>
              </ResponsiveShow>
              <ResponsiveShow on="mobile">
                <Space direction="vertical" size={4}>
                  {mergedDepts.map((d) => (
                    <Typography.Text key={d.department_id}>
                      {d.department_name}：自评 {percentOf(d.self_done, d.self_total)}%，互评 {percentOf(d.peer_done, d.peer_total)}%
                    </Typography.Text>
                  ))}
                </Space>
              </ResponsiveShow>
            </Card>
          )}

          <Card title="部门进度">
            {mergedDepts.length === 0 ? (
              <Typography.Text type="secondary">暂无数据</Typography.Text>
            ) : (
              <>
                <ResponsiveShow on="desktop">
                  <Space direction="vertical" size="middle" style={{ width: "100%" }}>
                    <Space size="large">
                      <span>
                        <span
                          style={{
                            display: "inline-block",
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            background: "var(--color-primary)",
                            marginRight: 4,
                          }}
                        />
                        自评
                      </span>
                      <span>
                        <span
                          style={{
                            display: "inline-block",
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            background: "var(--color-chart-2)",
                            marginRight: 4,
                          }}
                        />
                        互评
                      </span>
                    </Space>
                    {mergedDepts.map((d) => (
                      <div key={d.department_id}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            marginBottom: 4,
                          }}
                        >
                          <span>{d.department_name}</span>
                          {deptStatusTag(d)}
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <Typography.Text type="secondary" style={{ width: 32, flexShrink: 0 }}>
                            自评
                          </Typography.Text>
                          <Progress
                            percent={percentOf(d.self_done, d.self_total)}
                            size="small"
                            strokeColor="var(--color-primary)"
                            style={{ flex: 1 }}
                            format={() => `${d.self_done}/${d.self_total}`}
                          />
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <Typography.Text type="secondary" style={{ width: 32, flexShrink: 0 }}>
                            互评
                          </Typography.Text>
                          <Progress
                            percent={percentOf(d.peer_done, d.peer_total)}
                            size="small"
                            strokeColor="var(--color-chart-2)"
                            style={{ flex: 1 }}
                            format={() => `${d.peer_done}/${d.peer_total}`}
                          />
                        </div>
                      </div>
                    ))}
                  </Space>
                </ResponsiveShow>
                <ResponsiveShow on="mobile">
                  <TableCardList<MergedDeptProgress>
                    columns={deptCardColumns}
                    dataSource={mergedDepts}
                    rowKey={(d) => d.department_id}
                  />
                </ResponsiveShow>
              </>
            )}
          </Card>
        </>
      )}
    </Space>
  );
}
