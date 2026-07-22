// HR 绩效看板：展示某个绩效周期各环节整体进度
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Card, Col, Progress, Row, Select, Space, Statistic, Typography, message } from "antd";
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
  performance_participant_count: number;
  self_eval_done: number;
  self_eval_total: number;
  peer_list_confirmed: number;
  peer_eval_done: number;
  superior_eval_done: number;
  superior_eval_total: number;
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
  value: number;
  suffix: string;
  color?: string;
}

const STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  in_progress: "进行中",
  published: "已公布",
  closed: "已归档",
};

// 图表色板（@ant-design/charts 配置只接受色值，顺序对应 --color-chart-1~6）
const CHART_COLORS: string[] = ["#3370FF", "#14C9C9", "#F7BA1E", "#F53F3F", "#86909C", "#00B42A"];

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
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);

  useEffect(() => {
    api.get<CycleBrief[]>("/v1/cycles").then((r) => {
      setCycles(r.data);
      if (r.data.length > 0 && !selectedCycleId) {
        setSelectedCycleId(r.data[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedCycleId) return;
    api.get<DashboardData>(`/v1/cycles/${selectedCycleId}/dashboard`)
      .then((r) => setData(r.data))
      .catch((e) => message.error(formatError(e, "加载失败")));
  }, [selectedCycleId]);

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
      ]
    : [];

  // 部门自评/互评完成率对比图数据（色板前两色：自评 #3370FF、互评 #14C9C9）
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

      {data && (
        <>
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

          {mergedDepts.length > 0 && (
            <Card title="部门完成率对比">
              <Column
                data={deptChartData}
                xField="department"
                yField="percent"
                seriesField="type"
                color={CHART_COLORS}
                height={280}
                yAxis={{ max: 100 }}
                tooltip={{
                  formatter: (d: { type: string; percent: number }) => ({
                    name: d.type,
                    value: `${d.percent}%`,
                  }),
                }}
              />
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
