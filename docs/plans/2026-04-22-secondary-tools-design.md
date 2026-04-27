# 百度网盘二级工具扩展设计

日期：2026-04-22

## 目标

在现有读取、监视、同步规划和清理分析基础上，补齐：

1. 差异对账
2. 文件系统变更规划
3. 离线索引
4. 归档计划
5. manifest 验证
6. manifest 批处理

## 设计原则

- 先可视化，再修复
- 修复动作先生成 manifest，不直接执行
- 删除类动作统一改为网盘归档
- 本地 vs 网盘比较优先于直接远端修改

## 本轮实现范围

- 完成 `baidupan-reconcile`
- 完成 `baidupan-fs`
- 完成 `baidupan-index`
- 完成 `baidupan-archive`
- 完成 `baidupan-verify`
- 完成 `baidupan-batch-runner`

## 执行策略

- 新工具统一复用 `common/` 下的 token、inventory、manifest 工具
- `reconcile` 输出文本和 JSON
- `archive` 从 `reconcile` 的 JSON 报告生成归档 manifest
- `verify` 只做存在性检查
- `batch-runner` 只做汇总和 runbook 渲染
