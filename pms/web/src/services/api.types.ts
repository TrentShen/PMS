// 前后端 API 契约共享类型
// 本文件类型必须与后端 Pydantic Schema 保持一致，修改时请同步更新 scripts/check_contract.py 报告

export interface ObjectiveCycle {
  id: number;
  name: string;
  status: string;
  start_date: string;
  end_date: string;
}

export interface Cycle {
  id: number;
  name: string;
  status: string;
  start_date: string;
  end_date: string;
  published_at: string | null;
  objective_cycle_id: number | null;
  enable_self_eval: boolean;
  enable_peer_eval: boolean;
  enable_calibration: boolean;
  enable_feedback: boolean;
  exclusion_rules?: ExclusionRules | null;
}

export interface ExclusionRules {
  exclude_roles?: string[];
  exclude_user_ids?: number[];
  exclude_dept_ids?: number[];
  exclude_levels?: string[];
  min_hired_before?: string;
}

export interface UserBrief {
  id: number;
  name: string;
  role: string;
  position: string | null;
  level: string | null;
  department_id: number | null;
  employee_type: string | null;
}

export interface DeptBrief {
  id: number;
  name: string;
}

export interface Participant {
  id: number;
  cycle_id: number;
  user_id: number;
  user_name: string;
  user_position: string | null;
  status: string;
  final_perf_level: string | null;
  final_perf_score: number | null;
  final_value_belief: string | null;
  final_value_team: string | null;
  final_value_growth: string | null;
}

// GET /v1/objective-cycles/{id}/participants 的单条参与人（后端 objective_cycles.py ParticipantDetail）
// 与评估周期的 Participant 不是同一结构，勿混用
export interface ObjectiveCycleParticipant {
  id: number;
  objective_cycle_id: number;
  user_id: number;
  user_name: string;
  user_position: string | null;
  leader_userid_snapshot: string | null;
  dept_name_snapshot: string | null;
  status: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
}

export interface StageConfig {
  stages?: Record<string, string>;
  publish_date?: string | null;
}

export interface AdjustmentView {
  id: number;
  objective_cycle_id: number;
  user_id: number;
  reason: string;
  old_objectives?: Record<string, unknown>[] | null;
  new_objectives?: Record<string, unknown>[] | null;
  status: string;
  requested_by_userid: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  reject_reason: string | null;
  created_at: string;
}

export interface ObjectiveInput {
  title: string;
  description: string;
  measure_criteria: string;
  weight: number;
}

export interface ObjectiveView {
  id: number;
  title: string;
  description: string;
  measure_criteria: string;
  weight: number;
  progress: number;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  reject_reason: string | null;
}

// 目标导入（试用期目标 / 历史目标）跳过的单条记录
export interface ObjectiveImportSkip {
  wecom_userid: string;
  name: string;
  reason: string;
}

// POST /v1/probation/import-objectives 与 POST /v1/import/historical-objectives 的响应
export interface ObjectiveImportResult {
  imported_users: number;
  imported_objectives: number;
  skipped: ObjectiveImportSkip[];
}

// 线下《目标设定及考核表》多文件导入的响应
// POST /v1/objective-cycles/{id}/excel/import-offline 与 POST /v1/probation/import-offline-objectives
export interface OfflineObjectiveImportResult extends ObjectiveImportResult {
  warnings: string[];
}

// GET /v1/import/historical-objectives 的单条历史目标
export interface HistoricalObjective {
  id: number;
  user_id: number;
  user_name: string;
  cycle_name: string;
  title: string;
  description: string | null;
  measure_criteria: string | null;
  weight: number;
  order_num: number;
}

// POST /v1/import/historical-evaluations/summary 与 POST /v1/import/historical-evaluations/detail 的响应
export interface HistoricalEvaluationImportResult {
  imported: number;
  skipped: ObjectiveImportSkip[];
}

// GET /v1/history/users/{user_id}/evaluations 的汇总部分（敏感数据，严格权限）
export interface HistoricalEvaluationSummaryView {
  superior_score: number | null;
  superior_level: string | null;
  superior_value_grade: string | null;
  peer_avg_score: number | null;
  peer_level: string | null;
  peer_value_grade: string | null;
  self_score: number | null;
  self_level: string | null;
  self_value_grade: string | null;
  is_calibrated: boolean;
  calibration_suggestion: string | null;
  calibrated_score: number | null;
  calibrated_result: string | null;
  comment: string | null;
}

// GET /v1/history/users/{user_id}/evaluations 的明细部分
export interface HistoricalEvaluationDetailView {
  self_score: number | null;
  self_value_grade: string | null;
  self_output: string | null;
  self_comment: string | null;
  superior_score: number | null;
  superior_value_grade: string | null;
  superior_comment: string | null;
  // 互评明细：后端匿名化，仅给序号
  peers: { index: number; score: number | null; comment: string | null }[];
}

// GET /v1/history/users/{user_id}/evaluations 的单条周期记录
export interface HistoricalEvaluationView {
  cycle_name: string;
  summary: HistoricalEvaluationSummaryView | null;
  detail: HistoricalEvaluationDetailView | null;
}

// 通用 API 错误结构（axios 错误响应）
export interface ApiErrorResponse {
  response?: {
    status?: number;
    data?: {
      detail?: string | { errors?: string[]; [key: string]: unknown };
    };
  };
  message?: string;
}
