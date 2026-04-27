# 百度网盘命令分流表

## 任务到技能的映射

| 任务 | 推荐技能/脚本 | 原因 |
|---|---|---|
| 首次授权、确认 token 是否可用 | `bypy-baidu-netdisk` / `bypy info` | `bypy` 最适合做 OAuth 首次认证 |
| 单文件上传/下载 | `bypy-enhanced/scripts/bdpan_enhanced.py` | 已有断点续传和更清晰的输出 |
| 浏览目录、树形查看 | `bypy-enhanced/scripts/bdpan_enhanced.py` | 支持 `tree`、递归 `list`、时间戳 |
| 搜索文件、统计目录 | `bypy-enhanced/scripts/bdpan_enhanced.py` | 原生 API 读操作更稳定 |
| 批量下载目录 | `bypy-enhanced/scripts/bdpan_enhanced.py batch-download` | 已封装递归下载与跳过逻辑 |
| 比较目录是否有变化 | `baidupan-monitor/scripts/bdpan_monitor.py` | 快照与 diff 结果更适合持续观察 |
| 规划本地与网盘同步 | `baidupan-sync/scripts/bdpan_sync.py` | 输出 `upload/download/conflict` 行动计划 |
| 找大文件、旧文件、重复候选 | `baidupan-cleanup/scripts/bdpan_cleanup.py` | 属于分析任务，不应混进传输脚本 |
| 本地 vs 网盘、网盘 vs 网盘差异对账 | `baidupan-reconcile/scripts/bdpan_reconcile.py` | 输出清晰文本报告和 JSON 报告 |
| 规划 move / copy / rename / mkdir / archive | `baidupan-fs/scripts/bdpan_fs.py` | 只生成 manifest，不直接执行 |
| 为对账结果生成归档计划 | `baidupan-archive/scripts/bdpan_archive.py` | 删除类动作统一转归档 |
| 校验 manifest 路径存在性 | `baidupan-verify/scripts/bdpan_verify.py` | 执行前安全检查 |
| 预览或执行 manifest | `baidupan-apply/scripts/bdpan_apply.py` | 默认预览，必须显式确认执行 |
| 汇总、合并、渲染 manifest | `baidupan-batch-runner/scripts/bdpan_batch_runner.py` | 输出 runbook，便于人工复核 |

## 推荐操作顺序

1. `info` 确认 token 可用
2. `list` 或 `tree` 确认目标目录
3. 需要变更时先跑 `stats`、`monitor diff` 或 `sync plan-*`
4. 再执行上传、下载或清理

## 命令示例

```bash
# 树形查看
python ./bypy-enhanced/scripts/bdpan_enhanced.py tree /项目资料 -d 3

# 变化检查
python ./baidupan-monitor/scripts/bdpan_monitor.py check /项目资料 --name project-docs

# 同步规划
python ./baidupan-sync/scripts/bdpan_sync.py plan-up ./docs /项目资料/docs --manifest sync-plan.json

# 清理分析
python ./baidupan-cleanup/scripts/bdpan_cleanup.py large-files /项目资料 --top 30

# 差异对账
python ./baidupan-reconcile/scripts/bdpan_reconcile.py compare-local ./docs /项目资料/docs --ignore-extension --output reconcile.txt --json-output reconcile.json

# 归档计划
python ./baidupan-archive/scripts/bdpan_archive.py from-report reconcile.json --source right --archive-root /归档整理 --output archive.json

# 执行前预览 / 执行
python ./baidupan-apply/scripts/bdpan_apply.py manifest archive.json
python ./baidupan-apply/scripts/bdpan_apply.py manifest archive.json --execute --yes --log apply-log.json
```
