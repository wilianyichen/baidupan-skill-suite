---
name: baidupan-fs
description: 百度网盘文件系统规划技能。为 mkdir、move、copy、rename、archive 等远端改动生成 manifest，不直接执行。
---

# 百度网盘文件系统规划技能

这个技能只产出 manifest，不直接执行远端修改。

## 命令入口

```bash
python ./baidupan-fs/scripts/bdpan_fs.py mkdir-plan /目标/目录 --output mkdir.json
python ./baidupan-fs/scripts/bdpan_fs.py move-plan /源路径 /目标路径 --output move.json
python ./baidupan-fs/scripts/bdpan_fs.py rename-plan /源路径 新文件名 --output rename.json
python ./baidupan-fs/scripts/bdpan_fs.py copy-plan /源路径 /目标路径 --output copy.json
python ./baidupan-fs/scripts/bdpan_fs.py archive-plan /待归档/路径1 /待归档/路径2 --archive-root /归档整理 --output archive.json
```

## 约束

- 当前不执行 manifest
- 删除类需求统一转换为归档计划，不直接删除
