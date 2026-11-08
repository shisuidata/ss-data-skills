-- 示例 DDL：dws_user_activation_1d（脱敏）
CREATE TABLE IF NOT EXISTS dws.dws_user_activation_1d (
  user_id STRING COMMENT '用户 ID',
  channel STRING COMMENT '注册渠道',
  create_workspace_flag INT COMMENT '是否创建工作区',
  invite_member_flag INT COMMENT '是否邀请成员',
  complete_task_flag INT COMMENT '是否完成核心任务',
  activated_flag INT
)
COMMENT '新注册用户 7 日激活明细'
PARTITIONED BY (register_date STRING COMMENT '注册日期')
STORED AS ORC;
