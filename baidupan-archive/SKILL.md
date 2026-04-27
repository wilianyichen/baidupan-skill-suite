---
name: baidupan-archive
description: 百度网盘归档计划技能。把差异报告或指定路径转换为网盘归档 manifest，确保删除类动作走归档而不是直接删除。
---

# 百度网盘归档计划技能

## 命令入口

```bash
python ./baidupan-archive/scripts/bdpan_archive.py from-report report.json --source right --archive-root /归档整理 --output archive.json
python ./baidupan-archive/scripts/bdpan_archive.py direct-paths /待归档/路径1 /待归档/路径2 --archive-root /归档整理 --output archive.json
```
