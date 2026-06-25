-- 数据修复：已关闭（closed）周期中，状态为 pending/self_done/leader_done 的参与人改为 excluded
-- 修复原因：周期归档后不应存在未完成状态的参与人
-- 执行前建议先备份数据库

UPDATE cycle_participant cp
JOIN performance_cycle c ON cp.cycle_id = c.id
SET cp.status = 'excluded'
WHERE c.status = 'closed'
  AND cp.status IN ('pending', 'self_done', 'leader_done');
