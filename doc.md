支持任务类型
1. 普通任务（越快越好）
2. 时间严苛（在deadline之后完成会判定失败）
3. DAG（一系列任务，需要按顺序完成）
4. 数据依赖（只能在有数据库的节点上执行）
{
  "task_id": "task-123",
  "func": "process_data",
  "type": "time_critical",            // 可为 normal / time_critical / dag / data_bound
  "payload": { "input": "xxx" },
  "ddl": 1717201981.8,                // deadline（仅 time_critical 需要）
  "dag_info": {
    "dag_id": "dag-001",              // 所属 DAG ID
    "stage": 2,                       // 第几阶段任务（可按拓扑排序结果）
    "total_stages": 4,               // DAG 总阶段数
    "dependencies": ["task-122"]     // 前置任务 ID
  },
  "tag": "user-xyz",                  // 标识来源用户或请求批次
  "hop": 0                            // 当前已跳转几次（用于联邦架构限制转发层数）
}
