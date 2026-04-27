# 百度网盘技能增强设计

日期：2026-04-22

## 目标

把当前仓库从“基础 bypy skill + 一个增强脚本 + 一个未完成监控说明”升级为一套可路由、可复用、可扩展的百度网盘技能包。

## 核心设计

1. 保留 `bypy-baidu-netdisk` 作为总控技能。
2. `bypy-enhanced` 负责原生 API 的高频操作与更清晰的输出。
3. `baidupan-monitor` 负责快照、diff、watch。
4. 新增 `baidupan-sync`，专门输出同步计划与命令。
5. 新增 `baidupan-cleanup`，专门做清理分析。

## 设计原则

- 先读后写
- 高风险操作前先输出计划
- 技能说明尽量精简，把复杂流程拆成专用脚本
- token 查找统一支持 `~/.bypy/bypy.token.json`、仓库根目录 `bypy.token.json`、环境变量 `BYPY_TOKEN_FILE`

## 预期收益

- 用户能更快找到“应该用哪个技能”
- 高价值场景从说明文档变成可执行脚本
- 同步、监控、清理不再挤在一个脚本里，职责更清晰
