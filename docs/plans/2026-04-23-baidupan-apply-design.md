# 百度网盘执行器设计

日期：2026-04-23

## 目标

为现有 manifest 体系补执行层，但保持高安全性：

1. 默认只预览
2. 只有 `--execute --yes` 才执行
3. 只支持低风险、已规划好的远端动作
4. 删除语义统一收口为归档

## 第一版范围

- `archive_remote`
- `mkdir_remote`
- `move_remote`
- `rename_remote`

不支持：

- `copy_remote`
- 任何直接删除动作

## 执行策略

- 通过 access token 直接调用网盘接口
- `move/rename/archive` 统一转换为 move
- 执行前自动确保目标父目录存在
- 执行结果输出为 JSON 日志

## 安全约束

- 预览与执行分离
- 执行需要双显式参数确认
- manifest 中若包含不支持动作，直接拒绝
