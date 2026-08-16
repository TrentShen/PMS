// 参与人进度状态（cycle_participant.status）的全站统一文案与语义色
// 供 LeaderEval / LeaderEvalDetail / Calibration / HrConsole 等页面共用，避免一处一译
import type { StatusType } from "@/components/ui/StatusTag";

export const PARTICIPANT_STATUS_LABEL: Record<string, string> = {
  pending: "待自评",
  self_done: "待上级评估",
  leader_done: "上级已评",
  published: "已公布",
  excluded: "已排除",
};

export const PARTICIPANT_STATUS_TYPE: Record<string, StatusType> = {
  pending: "warning",
  self_done: "info",
  leader_done: "primary",
  published: "success",
  excluded: "default",
};
