-- 为 objective 表增加审批状态字段
-- 执行方式: docker exec -i pms-mysql mysql -u pms -p<PASSWORD> pms < add_objective_status_fields.sql

ALTER TABLE objective
    ADD COLUMN status VARCHAR(16) NOT NULL DEFAULT 'draft' AFTER order_num,
    ADD COLUMN reviewed_by VARCHAR(64) DEFAULT NULL AFTER status,
    ADD COLUMN reviewed_at DATETIME DEFAULT NULL AFTER reviewed_by,
    ADD COLUMN reject_reason TEXT DEFAULT NULL AFTER reviewed_at;

-- 为已有数据标记为 approved（历史导入的数据视为已确认）
UPDATE objective SET status = 'approved' WHERE status = 'draft';

-- 添加索引加速查询
CREATE INDEX idx_objective_status ON objective(status);
