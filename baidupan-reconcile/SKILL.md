---
name: baidupan-reconcile
description: 百度网盘差异对账技能。对比本地目录和网盘目录，或两个网盘目录的结构差异，重点输出清晰、可视化、可保存的差异结果，支持忽略扩展名。
---

# 百度网盘差异对账技能

这个技能专门做差异可视化，不直接执行修复。

## 典型场景

- 比较本地素材目录和网盘目录是否对齐
- 比较两个网盘分支的结构差异
- 忽略扩展名比较视频目录和音频目录
- 输出“缺目录”“缺文件”“部分文件差异”的清晰报告

## 命令入口

```bash
python ./baidupan-reconcile/scripts/bdpan_reconcile.py compare-local ./local-dir /网盘/目录 --ignore-extension --output report.txt --json-output report.json
python ./baidupan-reconcile/scripts/bdpan_reconcile.py compare-remote /网盘/左分支 /网盘/右分支 --ignore-extension --output report.txt --json-output report.json
python ./baidupan-reconcile/scripts/bdpan_reconcile.py folder-summary report.json --output folders.txt --json-output folders.json
python ./baidupan-reconcile/scripts/bdpan_reconcile.py partial-files report.json --output partial-files.txt --json-output partial-files.json
```

## 约束

- 当前只输出结果和 JSON 报告，不执行修复
- 删除相关动作后续统一走归档方案，不直接删
- `folder-summary` 适合快速看哪些目录存在差异
- `partial-files` 适合只看“共享目录中缺失了哪些文件”
