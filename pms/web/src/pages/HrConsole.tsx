// HR 管理台：周期管理 + 参与人 + Excel 导入/导出 + 催办 + 考核对象过滤
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Table,
  Typography,
  Upload,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { DownloadOutlined, UploadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api, formatError } from "@/services/api";
import StatusTag, { type StatusType } from "@/components/ui/StatusTag";
import TableCardList from "@/components/ui/TableCardList";
import { PARTICIPANT_STATUS_LABEL, PARTICIPANT_STATUS_TYPE } from "@/components/ui/participantStatus";
import ResponsiveShow from "@/components/ui/ResponsiveShow";
import { useMobile } from "@/hooks/useMobile";
import { showHistoricalEvaluationImportResult, showObjectiveImportResult } from "@/components/ui/showImportResult";
import type {
  Cycle,
  DeptBrief,
  ExclusionRules,
  HistoricalEvaluationImportResult,
  ObjectiveCycle,
  ObjectiveImportResult,
  Paginated,
  Participant,
  UserBrief,
} from "@/services/api.types";

interface CycleCreateForm {
  name: string;
  range: [dayjs.Dayjs, dayjs.Dayjs];
  objective_cycle_id?: number;
  enable_self_eval?: boolean;
  enable_peer_eval?: boolean;
  enable_calibration?: boolean;
  enable_feedback?: boolean;
}

interface FilterFormValues {
  exclude_roles?: string[];
  exclude_user_ids?: number[];
  exclude_dept_ids?: number[];
  exclude_levels?: string[];
  min_hired_before?: dayjs.Dayjs;
}

const STATUS_LABEL: Record<string, string> = { draft: "草稿", in_progress: "进行中", published: "已公布", closed: "已归档" };

// 周期状态语义：进行中→primary、已公布/已归档→success、草稿→warning、其他→default
function cycleStatusType(status: string): StatusType {
  switch (status) {
    case "in_progress":
      return "primary";
    case "published":
    case "closed":
      return "success";
    case "draft":
      return "warning";
    default:
      return "default";
  }
}

/** 操作列图标统一 16px */
const ACTION_ICON_STYLE: React.CSSProperties = { fontSize: 16 };


export default function HrConsole() {
  const navigate = useNavigate();
  const isMobile = useMobile();
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [objectiveCycles, setObjectiveCycles] = useState<ObjectiveCycle[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form] = Form.useForm();
  const [selectedCycle, setSelectedCycle] = useState<Cycle | null>(null);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [users, setUsers] = useState<UserBrief[]>([]);
  const [departments, setDepartments] = useState<DeptBrief[]>([]);
  const [addingIds, setAddingIds] = useState<number[]>([]);
  const [adding, setAdding] = useState(false);
  // 删除参与人在途保护：防止 Popconfirm 快速双击发两次 DELETE
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [cycleActing, setCycleActing] = useState(false);
  const [cyclesLoading, setCyclesLoading] = useState(false);
  const [participantsLoading, setParticipantsLoading] = useState(false);
  const [urgeOpen, setUrgeOpen] = useState(false);
  const [urging, setUrging] = useState(false);
  const [urgeIds, setUrgeIds] = useState<number[]>([]);
  const [filterOpen, setFilterOpen] = useState(false);
  const [filtering, setFiltering] = useState(false);
  const [filterForm] = Form.useForm();
  // Excel 导入/导出防重：上传超时 60s，期间禁用按钮
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function loadCycles(): Promise<Cycle[]> {
    setCyclesLoading(true);
    try { const r = await api.get<Cycle[]>("/v1/cycles"); setCycles(r.data); return r.data; }
    finally { setCyclesLoading(false); }
  }
  async function loadObjectiveCycles() { const r = await api.get<ObjectiveCycle[]>("/v1/objective-cycles"); setObjectiveCycles(r.data); }
  async function loadUsers() { const r = await api.get<UserBrief[]>("/v1/users"); setUsers(r.data); }
  async function loadDepartments() { const r = await api.get<DeptBrief[]>("/v1/admin/departments"); setDepartments(r.data); }
  async function loadParticipants(cid: number) {
    setParticipantsLoading(true);
    try { const r = await api.get<Paginated<Participant>>(`/v1/cycles/${cid}/participants?page_size=9999`); setParticipants(r.data.items); }
    finally { setParticipantsLoading(false); }
  }
  useEffect(() => {
    loadCycles().catch((e) => message.error(formatError(e, "加载失败")));
    loadObjectiveCycles().catch((e) => message.error(formatError(e, "加载失败")));
    loadUsers().catch((e) => message.error(formatError(e, "加载失败")));
    loadDepartments().catch((e) => message.error(formatError(e, "加载失败")));
  }, []);
  useEffect(() => {
    if (selectedCycle) {
      loadParticipants(selectedCycle.id).catch((e) => message.error(formatError(e, "加载参与人失败")));
    }
  }, [selectedCycle]);
  // 筛选弹窗打开时，用周期已保存的规则预填充表单
  useEffect(() => {
    if (filterOpen && selectedCycle?.exclusion_rules) {
      const rules = selectedCycle.exclusion_rules;
      filterForm.setFieldsValue({
        exclude_roles: rules.exclude_roles,
        exclude_user_ids: rules.exclude_user_ids,
        exclude_dept_ids: rules.exclude_dept_ids,
        exclude_levels: rules.exclude_levels,
        min_hired_before: rules.min_hired_before ? dayjs(rules.min_hired_before) : null,
      });
    }
  }, [filterOpen]);

  // 周期操作后刷新列表并同步 selectedCycle（状态标签/可用操作需用新对象；被删周期自动取消选中）
  async function refreshCycles() {
    try {
      const list = await loadCycles();
      setSelectedCycle((prev) => (prev ? list.find((c) => c.id === prev.id) ?? null : prev));
    } catch (e) {
      message.error(formatError(e, "刷新周期列表失败"));
    }
  }

  async function onCreate(values: CycleCreateForm) {
    setCreating(true);
    try {
      const payload: Record<string, unknown> = {
        name: values.name,
        start_date: values.range[0].format("YYYY-MM-DD"),
        end_date: values.range[1].format("YYYY-MM-DD"),
      };
      if (values.objective_cycle_id) {
        payload.objective_cycle_id = values.objective_cycle_id;
      }
      if (values.enable_self_eval !== undefined) payload.enable_self_eval = values.enable_self_eval;
      if (values.enable_peer_eval !== undefined) payload.enable_peer_eval = values.enable_peer_eval;
      if (values.enable_calibration !== undefined) payload.enable_calibration = values.enable_calibration;
      if (values.enable_feedback !== undefined) payload.enable_feedback = values.enable_feedback;
      await api.post("/v1/cycles", payload);
      message.success("周期已创建"); setCreateOpen(false); form.resetFields(); await refreshCycles();
    } catch (e) { message.error(formatError(e, "创建失败")); }
    finally { setCreating(false); }
  }
  async function onAddParticipants() {
    if (!selectedCycle || addingIds.length === 0) return;
    setAdding(true);
    try {
      await api.post(`/v1/cycles/${selectedCycle.id}/participants`, { user_ids: addingIds });
      message.success(`已添加 ${addingIds.length} 位`); setAddingIds([]); await loadParticipants(selectedCycle.id);
    } catch (e) { message.error(formatError(e, "添加失败")); }
    finally { setAdding(false); }
  }
  async function onDeleteParticipant(participantId: number) {
    if (!selectedCycle || deletingId != null) return;
    setDeletingId(participantId);
    try {
      await api.delete(`/v1/cycles/${selectedCycle.id}/participants/${participantId}`);
      message.success("已删除");
      await loadParticipants(selectedCycle.id);
    } catch (e) { message.error(formatError(e, "删除失败")); }
    finally { setDeletingId(null); }
  }
  async function onStart(c: Cycle) {
    setCycleActing(true);
    // refreshCycles 会同步 selectedCycle 为新对象，触发参与人列表自动刷新
    try { await api.post(`/v1/cycles/${c.id}/start`); message.success("周期已启动"); await refreshCycles(); }
    catch (e) { message.error(formatError(e, "启动失败")); }
    finally { setCycleActing(false); }
  }
  async function onPublish(c: Cycle) {
    setCycleActing(true);
    try { await api.post(`/v1/cycles/${c.id}/publish`); message.success("已发布"); await refreshCycles(); }
    catch (e) { message.error(formatError(e, "发布失败")); }
    finally { setCycleActing(false); }
  }
  async function onClose(c: Cycle) {
    setCycleActing(true);
    try { await api.post(`/v1/cycles/${c.id}/close`); message.success("已归档"); await refreshCycles(); }
    catch (e) { message.error(formatError(e, "归档失败")); }
    finally { setCycleActing(false); }
  }
  async function onDelete(c: Cycle) {
    setCycleActing(true);
    try {
      await api.delete(`/v1/cycles/${c.id}`);
      message.success("周期已删除");
      await refreshCycles();
    } catch (e) { message.error(formatError(e, "删除失败")); }
    finally { setCycleActing(false); }
  }

  // === Excel 导入 ===
  async function onUploadExcel(file: File) {
    if (!selectedCycle || importing) return false;
    const fd = new FormData();
    fd.append("file", file);
    setImporting(true);
    try {
      if (!selectedCycle.objective_cycle_id) {
        message.error("当前评估周期未关联目标周期，无法导入目标");
        return false;
      }
      const r = await api.post(`/v1/objective-cycles/${selectedCycle.objective_cycle_id}/excel/import`, fd, { headers: { "Content-Type": "multipart/form-data" }, timeout: 60000 });
      message.success(`导入成功：${r.data.imported_rows} 行，${r.data.affected_users} 位员工`);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string | { errors?: string[] } } } };
      const detail = err.response?.data?.detail;
      if (typeof detail === "object" && detail?.errors) {
        Modal.error({
          title: "导入校验失败",
          content: (
            <ul style={{ margin: 0, paddingInlineStart: 20, maxHeight: 400, overflow: "auto" }}>
              {detail.errors.map((msg, i) => (<li key={i}>{msg}</li>))}
            </ul>
          ),
          width: 600,
        });
      } else { message.error(typeof detail === "string" ? detail : "导入失败"); }
    } finally { setImporting(false); }
    return false; // 阻止 antd 默认上传
  }

  // === 历史绩效导入 ===
  async function onUploadHistorical(file: File) {
    if (importing) return false;
    const fd = new FormData();
    fd.append("file", file);
    setImporting(true);
    try {
      const r = await api.post("/v1/import/historical-performance", fd, { headers: { "Content-Type": "multipart/form-data" } });
      const { success, failed, errors } = r.data;
      if (failed > 0) {
        Modal.warning({
          title: `导入完成：成功 ${success} 条，失败 ${failed} 条`,
          content: errors.length > 0 ? (
            <ul style={{ margin: 0, paddingInlineStart: 20, maxHeight: 400, overflow: "auto" }}>
              {errors.map((msg: string, i: number) => (<li key={i}>{msg}</li>))}
            </ul>
          ) : "",
          width: 600,
        });
      } else {
        message.success(`历史绩效导入成功：${success} 条`);
      }
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string | { errors?: string[] } } } };
      const detail = err.response?.data?.detail;
      if (typeof detail === "object" && detail?.errors) {
        Modal.error({
          title: "导入校验失败",
          content: (
            <ul style={{ margin: 0, paddingInlineStart: 20, maxHeight: 400, overflow: "auto" }}>
              {detail.errors.map((msg, i) => (<li key={i}>{msg}</li>))}
            </ul>
          ),
          width: 600,
        });
      } else { message.error(typeof detail === "string" ? detail : "导入失败"); }
    } finally { setImporting(false); }
    return false;
  }

  // === 历史目标导入 ===
  async function onUploadHistoricalObjectives(file: File) {
    if (importing) return false;
    const fd = new FormData();
    fd.append("file", file);
    setImporting(true);
    try {
      const r = await api.post<ObjectiveImportResult>("/v1/import/historical-objectives", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      showObjectiveImportResult(r.data);
    } catch (e) {
      message.error(formatError(e, "导入失败"));
    } finally { setImporting(false); }
    return false;
  }

  // === 历史考核导入（汇总 / 明细，响应结构 {imported, skipped}） ===
  async function onUploadHistoricalEvaluations(url: string, file: File) {
    if (importing) return false;
    const fd = new FormData();
    fd.append("file", file);
    setImporting(true);
    try {
      const r = await api.post<HistoricalEvaluationImportResult>(url, fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      });
      showHistoricalEvaluationImportResult(r.data);
    } catch (e) {
      message.error(formatError(e, "导入失败"));
    } finally { setImporting(false); }
    return false;
  }

  // === Excel 导出 ===
  async function onExport() {
    if (!selectedCycle || exporting) return;
    setExporting(true);
    try {
      const r = await api.get(`/v1/export/cycles/${selectedCycle.id}`, { responseType: "blob", timeout: 60000 });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a"); a.href = url; a.download = `${selectedCycle.name}_绩效结果.xlsx`; a.click();
      URL.revokeObjectURL(url);
      message.success("导出成功");
    } catch (e) { message.error(formatError(e, "导出失败")); }
    finally { setExporting(false); }
  }

  // === 催办 ===
  async function onUrge() {
    if (!selectedCycle) return;
    if (urgeIds.length === 0) { message.warning("请选择催办对象"); return; }
    setUrging(true);
    try {
      const r = await api.post("/v1/notify/urge", { cycle_id: selectedCycle.id, user_ids: urgeIds });
      message.success(`已催办 ${r.data.sent} 人`); setUrgeOpen(false); setUrgeIds([]);
    } catch (e) { message.error(formatError(e, "催办失败")); }
    finally { setUrging(false); }
  }

  // === 考核对象过滤 ===
  async function onFilter(values: FilterFormValues) {
    if (!selectedCycle) return;
    const rules: ExclusionRules = {};
    if (values.exclude_roles?.length) rules.exclude_roles = values.exclude_roles;
    if (values.exclude_user_ids?.length) rules.exclude_user_ids = values.exclude_user_ids;
    if (values.exclude_dept_ids?.length) rules.exclude_dept_ids = values.exclude_dept_ids;
    if (values.exclude_levels?.length) rules.exclude_levels = values.exclude_levels;
    if (values.min_hired_before) rules.min_hired_before = values.min_hired_before.format("YYYY-MM-DD");

    setFiltering(true);
    try {
      // 先保存排除规则到周期
      await api.put(`/v1/cycles/${selectedCycle.id}`, { exclusion_rules: rules });
      // 再调用 suggest（不传 body，自动使用 cycle 保存的规则）
      const r = await api.post<UserBrief[]>(`/v1/cycles/${selectedCycle.id}/suggest-participants`, {});
      const ids = r.data.map((u) => u.id);
      if (ids.length === 0) { message.warning("按条件未筛选到人"); return; }
      await api.post(`/v1/cycles/${selectedCycle.id}/participants`, { user_ids: ids });
      message.success(`已按条件添加 ${ids.length} 人`);
      setFilterOpen(false); filterForm.resetFields();
      await loadParticipants(selectedCycle.id);
      await loadCycles(); // 刷新周期列表以更新 exclusion_rules
    } catch (e) { message.error(formatError(e, "操作失败")); }
    finally { setFiltering(false); }
  }

  // employee_type 为 null 时按全职放行，与后端 is_fte 的"null 默认放行"口径一致
  const availableUsers = users.filter((u) => (u.employee_type ?? "full_time") === "full_time" && u.role !== "super_admin" && u.role !== "hrbp" && !participants.find((p) => p.user_id === u.id));
  const pendingParticipants = participants.filter((p) => p.status === "pending" || p.status === "self_done");

  // 周期关联信息（桌面表格与移动端卡片共用）
  function objectiveCycleName(c: Cycle): string | null {
    if (!c.objective_cycle_id) return null;
    return objectiveCycles.find((oc) => oc.id === c.objective_cycle_id)?.name ?? `ID ${c.objective_cycle_id}`;
  }
  function cycleStageText(c: Cycle): string {
    return [
      c.enable_self_eval && "自评",
      c.enable_peer_eval && "互评",
      c.enable_calibration && "校准",
      c.enable_feedback && "反馈",
    ].filter(Boolean).join(" ");
  }

  // 周期操作（桌面操作列与移动端卡片底部共用，图标按钮间距 8px）
  function renderCycleActions(c: Cycle): React.ReactNode {
    return (
      <Space size={8} wrap>
        <a onClick={() => setSelectedCycle(c)}>详情</a>
        {c.status === "draft" && (
          <Popconfirm title="启动后不能再加人，确认？" onConfirm={() => onStart(c)} okButtonProps={{ loading: cycleActing }}><a>启动</a></Popconfirm>
        )}
        {c.status === "in_progress" && (
          <Popconfirm title="需要先完成校准审批，确认发布？" onConfirm={() => onPublish(c)} okButtonProps={{ loading: cycleActing }}><a style={{ color: "var(--color-warning)" }}>发布</a></Popconfirm>
        )}
        {c.status === "published" && (
          <Popconfirm title="归档后周期将关闭，未完成员工会被标记为 excluded，确认？" onConfirm={() => onClose(c)} okButtonProps={{ loading: cycleActing }}><a style={{ color: "var(--color-text-secondary)" }}>归档</a></Popconfirm>
        )}
        {c.status === "draft" && (
          <Popconfirm title="确定删除该周期？删除后无法恢复。" onConfirm={() => onDelete(c)} okButtonProps={{ loading: cycleActing }}><a style={{ color: "var(--color-danger)" }}>删除</a></Popconfirm>
        )}
      </Space>
    );
  }

  const cycleColumns: ColumnsType<Cycle> = [
    { title: "周期名", dataIndex: "name" },
    {
      title: "状态",
      dataIndex: "status",
      width: 96,
      render: (s: string) => <StatusTag type={cycleStatusType(s)}>{STATUS_LABEL[s] ?? s}</StatusTag>,
    },
    { title: "考核时间", width: 210, render: (_, c) => `${c.start_date} ~ ${c.end_date}` },
    { title: "关联目标周期", render: (_, c) => objectiveCycleName(c) ?? "-" },
    { title: "环节", width: 160, render: (_, c) => cycleStageText(c) },
    { title: "操作", width: 220, render: (_, c) => renderCycleActions(c) },
  ];

  // 参与人操作（桌面操作列与移动端卡片底部共用）
  function renderParticipantActions(p: Participant): React.ReactNode {
    if (!selectedCycle) return null;
    return (
      <Space size={8} wrap>
        <Link to={`/leader/${selectedCycle.id}/users/${p.user_id}`}>详情</Link>
        {selectedCycle.status === "published" && (
          <a onClick={() => navigate(`/feedback/${selectedCycle.id}/${p.user_id}`)}>反馈</a>
        )}
        {selectedCycle.status === "draft" && (
          <Popconfirm title="确定删除该参与人？" onConfirm={() => onDeleteParticipant(p.id)}>
            <a style={{ color: "var(--color-danger)" }}>删除</a>
          </Popconfirm>
        )}
      </Space>
    );
  }

  const participantColumns: ColumnsType<Participant> = [
    { title: "姓名", dataIndex: "user_name" },
    { title: "职位", dataIndex: "user_position" },
    {
      title: "进度",
      dataIndex: "status",
      render: (s: string) => <StatusTag type={PARTICIPANT_STATUS_TYPE[s] ?? "default"}>{PARTICIPANT_STATUS_LABEL[s] ?? s}</StatusTag>,
    },
    { title: "业绩", render: (_, p) => (p.final_perf_score != null ? p.final_perf_score.toFixed(2) : "-") },
    {
      title: "价值观",
      render: (_, p) => (
        <span>{p.final_value_belief ?? p.final_value_team ?? p.final_value_growth ?? "-"}</span>
      ),
    },
    { title: "操作", render: (_, p) => renderParticipantActions(p) },
  ];

  // 当前周期的导入/导出/催办按钮（桌面横排在卡片 extra，移动端 100% 宽上下堆叠）
  function renderCycleTools(): React.ReactNode {
    if (!selectedCycle) return null;
    return (
      <>
        <Button size="small" icon={<DownloadOutlined style={ACTION_ICON_STYLE} />} href="/api/v1/objective-cycles/excel/template">下载导入模板</Button>
        <Upload accept=".xlsx" showUploadList={false} beforeUpload={(f) => onUploadExcel(f)}>
          <Button size="small" icon={<UploadOutlined style={ACTION_ICON_STYLE} />} loading={importing} disabled={importing}>Excel 导入目标</Button>
        </Upload>
        {selectedCycle.status === "published" && (
          <Button size="small" icon={<DownloadOutlined style={ACTION_ICON_STYLE} />} onClick={onExport} loading={exporting} disabled={exporting}>导出结果</Button>
        )}
        {selectedCycle.status === "in_progress" && (
          <Button size="small" onClick={() => { setUrgeIds(pendingParticipants.map((p) => p.user_id)); setUrgeOpen(true); }}>催办</Button>
        )}
      </>
    );
  }

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {/* 周期列表 */}
      <Card title="周期管理" extra={<Button type="primary" onClick={() => setCreateOpen(true)}>新建周期</Button>}>
        {/* 桌面：表格，选中行高亮 --color-primary-subtle */}
        <div className="pms-responsive-table">
          <Table<Cycle>
            rowKey="id"
            dataSource={cycles}
            columns={cycleColumns}
            pagination={false}
            loading={cyclesLoading}
            rowClassName={(c) => (c.id === selectedCycle?.id ? "hr-cycle-row-selected" : "")}
          />
        </div>
        {/* 移动端：卡片列表（参与人数字段契约中不存在，仅在已选中周期时展示已加载数量） */}
        <TableCardList<Cycle>
          dataSource={cycles}
          rowKey={(c) => c.id}
          loading={cyclesLoading}
          onCardClick={(c) => setSelectedCycle(c)}
          columns={[
            { title: "周期名", dataIndex: "name" },
            {
              title: "状态",
              render: (c) => <StatusTag type={cycleStatusType(c.status)}>{STATUS_LABEL[c.status] ?? c.status}</StatusTag>,
            },
            { title: "考核时间", render: (c) => `${c.start_date} ~ ${c.end_date}` },
            { title: "参与人数", render: (c) => (c.id === selectedCycle?.id ? String(participants.length) : "-") },
          ]}
          renderActions={(c) => renderCycleActions(c)}
        />
      </Card>

      {/* 历史数据导入：模板与上传按类型配对，附用途说明；导入结果为只读快照，不参与当前流程 */}
      <Card title="历史数据导入" size="small">
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="三步完成导入：① 下载对应模板 ② 按模板填写 Excel ③ 上传导入"
          description="导入的历史数据为只读快照，用于历史档案与趋势分析，不参与当前考核流程。"
        />
        <List
          dataSource={[
            {
              key: "performance",
              title: "历史绩效结果",
              description: "历年最终考核结果（业绩分、等级、价值观评级），历史绩效页可见",
              templateUrl: "/api/v1/import/historical-performance/template",
              onUpload: onUploadHistorical,
            },
            {
              key: "objectives",
              title: "历史目标留档",
              description: "历年绩效目标（目标项、权重、衡量标准），仅留档查看",
              templateUrl: "/api/v1/import/historical-objectives/template",
              onUpload: onUploadHistoricalObjectives,
            },
            {
              key: "eval-summary",
              title: "历史考核汇总",
              description: "按人按周期一条：自评 / 互评 / 上级评分与校准结果汇总",
              templateUrl: "/api/v1/import/historical-evaluations/summary/template",
              onUpload: (f: File) => onUploadHistoricalEvaluations("/v1/import/historical-evaluations/summary", f),
            },
            {
              key: "eval-detail",
              title: "历史考核详情",
              description: "含自评产出、上级评价、逐条互评评语等完整明细",
              templateUrl: "/api/v1/import/historical-evaluations/detail/template",
              onUpload: (f: File) => onUploadHistoricalEvaluations("/v1/import/historical-evaluations/detail", f),
            },
          ]}
          renderItem={(item) => (
            <List.Item style={{ display: "block" }}>
              <List.Item.Meta
                title={item.title}
                description={item.description}
              />
              <Space style={{ marginTop: 8 }}>
                <Button icon={<DownloadOutlined style={ACTION_ICON_STYLE} />} href={item.templateUrl}>
                  下载模板
                </Button>
                <Upload accept=".xlsx" showUploadList={false} beforeUpload={item.onUpload}>
                  <Button type="primary" ghost icon={<UploadOutlined style={ACTION_ICON_STYLE} />} loading={importing} disabled={importing}>
                    上传导入
                  </Button>
                </Upload>
              </Space>
            </List.Item>
          )}
        />
      </Card>

      {/* 参与人详情 */}
      {selectedCycle && (
        <Card
          title={
            <Space size={8}>
              {`参与人（${selectedCycle.name}）`}
              <StatusTag type={cycleStatusType(selectedCycle.status)}>{STATUS_LABEL[selectedCycle.status] ?? selectedCycle.status}</StatusTag>
            </Space>
          }
          extra={
            <ResponsiveShow on="desktop">
              <Space size={8}>{renderCycleTools()}</Space>
            </ResponsiveShow>
          }
        >
          {/* 移动端：导入/导出/催办按钮 100% 宽上下堆叠 */}
          <ResponsiveShow on="mobile">
            <div className="hr-console-mobile-actions" style={{ marginBottom: 12 }}>
              {renderCycleTools()}
            </div>
          </ResponsiveShow>
          {/* 草稿：加参与人 */}
          {selectedCycle.status === "draft" && (
            <Space style={{ marginBottom: 16 }} wrap>
              <Select mode="multiple" placeholder="选择员工" style={{ width: "100%", minWidth: 200 }} value={addingIds} onChange={setAddingIds}
                options={availableUsers.map((u) => ({ value: u.id, label: `${u.name}（${u.position ?? ""}）` }))} />
              <Button type="primary" onClick={onAddParticipants} loading={adding}>添加</Button>
              <Button onClick={() => setFilterOpen(true)}>按条件筛选添加</Button>
            </Space>
          )}
          {selectedCycle.status === "draft" && participants.length === 0 && (
            <Alert type="info" message="尚未添加参与人" />
          )}
          {/* 参与人列表：桌面表格 / 移动端卡片，按断点条件渲染避免双份挂载 */}
          {isMobile ? (
            <TableCardList<Participant>
              dataSource={participants}
              rowKey={(p) => p.id}
              loading={participantsLoading}
              columns={[
                { title: "姓名", dataIndex: "user_name" },
                { title: "职位", render: (p) => p.user_position ?? "-" },
                {
                  title: "进度",
                  render: (p) => <StatusTag type={PARTICIPANT_STATUS_TYPE[p.status] ?? "default"}>{PARTICIPANT_STATUS_LABEL[p.status] ?? p.status}</StatusTag>,
                },
                { title: "业绩", render: (p) => (p.final_perf_score != null ? p.final_perf_score.toFixed(2) : "-") },
                {
                  title: "价值观",
                  render: (p) => p.final_value_belief ?? p.final_value_team ?? p.final_value_growth ?? "-",
                },
              ]}
              renderActions={(p) => renderParticipantActions(p)}
            />
          ) : (
            <Table<Participant>
              rowKey="id"
              size="small"
              dataSource={participants}
              pagination={false}
              loading={participantsLoading}
              columns={participantColumns}
              scroll={{ x: 640 }}
            />
          )}
        </Card>
      )}

      {/* 新建周期弹窗 */}
      <Modal title="新建周期" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => form.submit()} confirmLoading={creating}>
        <Form form={form} layout="vertical" onFinish={onCreate}>
          <Form.Item name="name" label="周期名" initialValue="2025 下半年度绩效考核" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="range" label="考核周期" initialValue={[dayjs("2025-07-01"), dayjs("2025-12-31")]} rules={[{ required: true }]}><DatePicker.RangePicker /></Form.Item>
          <Form.Item name="objective_cycle_id" label="关联目标周期" extra="本评估周期将评估所选目标周期内的目标">
            <Select placeholder="选择目标周期" allowClear options={objectiveCycles.map((oc) => ({ value: oc.id, label: `${oc.name}（${oc.start_date} ~ ${oc.end_date}）` }))} />
          </Form.Item>
          <Form.Item label="考核环节（关闭后员工端将隐藏对应入口）">
            <Form.Item name="enable_self_eval" noStyle initialValue={true} valuePropName="checked">
              <Switch /> 自评
            </Form.Item>
            <Form.Item name="enable_peer_eval" noStyle initialValue={true} valuePropName="checked">
              <Switch /> 互评
            </Form.Item>
            <Form.Item name="enable_calibration" noStyle initialValue={true} valuePropName="checked">
              <Switch /> 校准
            </Form.Item>
            <Form.Item name="enable_feedback" noStyle initialValue={true} valuePropName="checked">
              <Switch /> 反馈
            </Form.Item>
          </Form.Item>
        </Form>
      </Modal>

      {/* 催办弹窗 */}
      <Modal title="催办未完成人员" open={urgeOpen} onCancel={() => setUrgeOpen(false)} onOk={onUrge} confirmLoading={urging}>
        <Typography.Paragraph>将向以下 {urgeIds.length} 人发送催办通知：</Typography.Paragraph>
        <Select mode="multiple" style={{ width: "100%" }} value={urgeIds} onChange={setUrgeIds}
          options={participants.map((p) => ({ value: p.user_id, label: `${p.user_name}（${PARTICIPANT_STATUS_LABEL[p.status] ?? p.status}）` }))} />
      </Modal>

      {/* 时间线配置 */}
      {selectedCycle && (
        <StageConfigPanel cycleId={selectedCycle.id} cycleStatus={selectedCycle.status} />
      )}

      {/* 按条件筛选参与人弹窗 */}
      <Modal title="按条件筛选参与人" open={filterOpen} onCancel={() => setFilterOpen(false)} onOk={() => filterForm.submit()} confirmLoading={filtering} style={{ top: 20 }}>
        <Form form={filterForm} layout="vertical" onFinish={onFilter}>
          <Form.Item name="exclude_roles" label="排除角色">
            <Select mode="multiple" options={[
              { value: "super_admin", label: "超级管理员" },
              { value: "hrbp", label: "HR" },
              { value: "dept_leader", label: "部门 Leader" },
              { value: "direct_leader", label: "直属上级" },
            ]} />
          </Form.Item>
          <Form.Item name="exclude_user_ids" label="排除指定人员">
            <Select mode="multiple" placeholder="选择要排除的员工" style={{ width: "100%" }}
              options={users.map((u) => ({ value: u.id, label: `${u.name}（${u.position ?? ""}）` }))} />
          </Form.Item>
          <Form.Item name="exclude_dept_ids" label="排除部门">
            <Select mode="multiple" placeholder="选择要排除的部门" style={{ width: "100%" }}
              options={departments.map((d) => ({ value: d.id, label: d.name }))} />
          </Form.Item>
          <Form.Item name="exclude_levels" label="排除职级">
            <Select mode="multiple" placeholder="选择要排除的职级" style={{ width: "100%" }}
              options={Array.from(new Set(users.map((u) => u.level).filter(Boolean))).map((lvl) => ({ value: lvl, label: lvl }))} />
          </Form.Item>
          <Form.Item name="min_hired_before" label="入职日期不晚于" extra="只纳入在此日期前入职的员工">
            <DatePicker style={{ width: "100%" }} />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}

// ========== 时间线配置面板（PRD 3.2.3）==========
function StageConfigPanel({ cycleId }: { cycleId: number; cycleStatus: string }) {
  const [stageForm] = Form.useForm();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get(`/v1/notify/cycles/${cycleId}/stages`).then((r) => {
      if (r.data.stages) {
        // 把 "2025-01-06" 字符串转成 dayjs
        const vals: Record<string, dayjs.Dayjs | null> = {};
        for (const [k, v] of Object.entries(r.data.stages as Record<string, string>)) {
          vals[k] = v ? dayjs(v) : null;
        }
        stageForm.setFieldsValue(vals);
      }
    }).catch((e) => message.error(formatError(e, "加载失败")));
  }, [cycleId]);

  async function onSave() {
    const vals = await stageForm.validateFields();
    // 把 dayjs 转成 "YYYY-MM-DD" 字符串
    const payload: Record<string, string> = {};
    for (const [k, v] of Object.entries(vals)) {
      if (v) payload[k] = (v as dayjs.Dayjs).format("YYYY-MM-DD");
    }
    setLoading(true);
    try {
      await api.put(`/v1/notify/cycles/${cycleId}/stages`, payload);
      message.success("时间线已保存");
    } catch (e) {
      message.error(formatError(e, "保存失败"));
    } finally { setLoading(false); }
  }

  const STAGES = [
    { key: "self_eval", label: "自评" },
    { key: "peer_confirm", label: "互评名单确认" },
    { key: "peer_eval", label: "互评" },
    { key: "superior_eval", label: "上级评估" },
    { key: "calibration", label: "绩效校准" },
    { key: "approval", label: "公司级审批" },
    { key: "feedback", label: "绩效反馈" },
  ];

  return (
    <Card title="时间线配置（各环节截止日期）" extra={
      <Button type="primary" size="small" onClick={onSave} loading={loading}>保存时间线</Button>
    }>
      <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message="配置后系统会在截止前3天、1天和当天自动发送提醒（企微消息接入后自动推送）" />
      <Form form={stageForm} layout="vertical">
        <Row gutter={[12, 12]}>
          {STAGES.map((s) => (
            <Col key={s.key} xs={24} md={12} lg={8}>
              <div style={{ marginBottom: 4, fontWeight: 500 }}>{s.label}</div>
              <Space style={{ display: "flex", width: "100%" }}>
                <Form.Item name={`${s.key}_start`} noStyle style={{ flex: 1 }}>
                  <DatePicker placeholder="开始" size="small" style={{ width: "100%" }} aria-label={`${s.label}开始日期`} />
                </Form.Item>
                <span>~</span>
                <Form.Item name={`${s.key}_end`} noStyle style={{ flex: 1 }}>
                  <DatePicker placeholder="截止" size="small" style={{ width: "100%" }} aria-label={`${s.label}截止日期`} />
                </Form.Item>
              </Space>
            </Col>
          ))}
          <Col xs={24} md={12} lg={8}>
            <div style={{ marginBottom: 4, fontWeight: 500 }}>结果公布</div>
            <Form.Item name="publish_date" noStyle>
              <DatePicker placeholder="公布日" size="small" style={{ width: "100%" }} aria-label="结果公布日期" />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Card>
  );
}
