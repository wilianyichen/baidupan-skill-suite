---
name: baidupan-suite
description: 百度网盘总技能。统一处理 bypy 认证、网盘目录浏览、监视、对账、本地和网盘差异比较、归档计划、manifest 验证与执行。用户提到百度网盘、bypy、网盘目录监视、音频视频结构比较、同步规划、归档或执行 manifest 时使用。
---

# 百度网盘总技能

这是整套百度网盘工具的统一入口 skill。优先把用户请求路由到最合适的脚本，而不是让用户记具体工具名。

## 使用前提

- 整套工具目录保持完整，例如：`~/tools/baidupan-tools`
- 推荐先创建最小环境：
  - `python3 ~/tools/baidupan-tools/scripts/bootstrap_min_venv.py`
- Linux 下推荐统一使用：
  - `~/tools/baidupan-tools/.venv/bin/python`

## Token 约定

脚本统一按以下优先级查找 token：

1. `BYPY_TOKEN_FILE`
2. `~/.bypy/bypy.token.json`
3. `~/.bypy/bypy.json`
4. 当前工作目录 `./bypy.token.json`
5. 当前工作目录 `./bypy.json`
6. 工具根目录下的 `bypy.token.json`
7. 工具根目录下的 `bypy.json`

## 路由规则

- 认证、查看根目录、搜索、上传下载：
  - `../bypy-enhanced/scripts/bdpan_enhanced.py`
- 快照监视、树结构、分支比较：
  - `../baidupan-monitor/scripts/bdpan_monitor.py`
- 本地 vs 网盘、网盘 vs 网盘差异对账：
  - `../baidupan-reconcile/scripts/bdpan_reconcile.py`
- 同步规划：
  - `../baidupan-sync/scripts/bdpan_sync.py`
- 清理分析：
  - `../baidupan-cleanup/scripts/bdpan_cleanup.py`
- 远端文件系统变更规划：
  - `../baidupan-fs/scripts/bdpan_fs.py`
- 归档计划：
  - `../baidupan-archive/scripts/bdpan_archive.py`
- manifest 验证：
  - `../baidupan-verify/scripts/bdpan_verify.py`
- manifest 执行：
  - `../baidupan-apply/scripts/bdpan_apply.py`
- manifest 汇总与 runbook：
  - `../baidupan-batch-runner/scripts/bdpan_batch_runner.py`
- 离线索引：
  - `../baidupan-index/scripts/bdpan_index.py`

## 默认工作流

1. 只读需求优先直接分析
2. 涉及差异修复时先用 `reconcile` 或 `sync`
3. 删除类诉求统一先转成 `archive`
4. 执行前先 `verify`
5. 执行时默认先 `apply` 预览，只有明确需要才 `--execute --yes`

## 常用示例

```bash
# 网盘浏览
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/bypy-enhanced/scripts/bdpan_enhanced.py list /

# 监视目录
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-monitor/scripts/bdpan_monitor.py check /开智/录屏整理 --name kaizhi-recordings

# 本地 / 网盘对账
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-reconcile/scripts/bdpan_reconcile.py compare-local ./local-dir /开智/录屏整理 --ignore-extension --output report.txt --json-output report.json

# 归档执行链
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-archive/scripts/bdpan_archive.py from-report report.json --source right --archive-root /归档整理 --output archive.json
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-verify/scripts/bdpan_verify.py manifest archive.json
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-apply/scripts/bdpan_apply.py manifest archive.json
```

详细路由示例见 `references/commands.md`。
