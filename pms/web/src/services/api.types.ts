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
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  reject_reason: string | null;
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
