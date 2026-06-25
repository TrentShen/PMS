INSERT INTO cycle_participant (cycle_id, user_id, leader_userid_snapshot, dept_name_snapshot, status)
SELECT 4, u.id, NULL, d.name, 'pending'
FROM user u
LEFT JOIN department d ON u.department_id = d.id
WHERE u.wecom_userid IN ('huanglixian', 'zhangqiongyan', 'kuaishengkang', 'shenkangdi', 'wangyingying', 'wupeng');

SELECT id, cycle_id, user_id, dept_name_snapshot, status FROM cycle_participant;
