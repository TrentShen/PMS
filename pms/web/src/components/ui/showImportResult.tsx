// 目标导入结果弹窗：成功 N 人 M 条 + 跳过明细
// 试用期目标导入与历史目标导入共用同一响应结构
import { Modal, Typography } from "antd";
import type { ObjectiveImportResult, OfflineObjectiveImportResult, HistoricalEvaluationImportResult } from "@/services/api.types";

export function showObjectiveImportResult(result: ObjectiveImportResult): void {
  Modal.info({
    title: `导入完成：成功 ${result.imported_users} 人，共 ${result.imported_objectives} 条目标`,
    width: 600,
    content:
      result.skipped.length > 0 ? (
        <div>
          <Typography.Text type="warning">跳过 {result.skipped.length} 条：</Typography.Text>
          <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
            {result.skipped.map((s, i) => (
              <li key={i}>
                {s.name}（{s.wecom_userid}）：{s.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null,
  });
}

// 历史考核导入（汇总 / 明细）结果弹窗：成功 N 条 + 跳过明细
// 响应结构与目标导入不同：imported 为总条数，无 imported_users / imported_objectives
export function showHistoricalEvaluationImportResult(result: HistoricalEvaluationImportResult): void {
  Modal.info({
    title: `导入完成：成功 ${result.imported} 条`,
    width: 600,
    content:
      result.skipped.length > 0 ? (
        <div>
          <Typography.Text type="warning">跳过 {result.skipped.length} 条：</Typography.Text>
          <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
            {result.skipped.map((s, i) => (
              <li key={i}>
                {s.name}（{s.wecom_userid}）：{s.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null,
  });
}

// 线下《目标设定及考核表》多文件导入结果弹窗：额外展示解析警告
export function showOfflineObjectiveImportResult(result: OfflineObjectiveImportResult): void {
  Modal.info({
    title: `导入完成：成功 ${result.imported_users} 人，共 ${result.imported_objectives} 条目标`,
    width: 600,
    content: (
      <div>
        {result.skipped.length > 0 && (
          <div>
            <Typography.Text type="warning">跳过 {result.skipped.length} 条：</Typography.Text>
            <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
              {result.skipped.map((s, i) => (
                <li key={i}>
                  {s.name}（{s.wecom_userid}）：{s.reason}
                </li>
              ))}
            </ul>
          </div>
        )}
        {result.warnings.length > 0 && (
          <div style={{ marginTop: result.skipped.length > 0 ? 12 : 0 }}>
            <Typography.Text type="warning">警告 {result.warnings.length} 条：</Typography.Text>
            <ul style={{ marginTop: 8, marginBottom: 0, paddingLeft: 20 }}>
              {result.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    ),
  });
}
