---
name: baidupan-sync
description: 百度网盘同步规划技能。比较本地目录和网盘目录，生成 upload、download、conflict、delete-extra 计划与待执行命令。
---

# 百度网盘同步规划技能

这个技能不直接盲目同步，而是先把差异算清楚，再生成命令。适合做“上传前检查”“下载前检查”“备份演练”。

## 典型场景

- 我想把本地目录同步到百度网盘，但先看看会发生什么
- 我想把网盘目录拉到本地，先列出哪些文件需要下载
- 我想生成一份同步清单，交给后续步骤执行

## 命令入口

```bash
python ./baidupan-sync/scripts/bdpan_sync.py plan-up ./local-dir /网盘/目录 --manifest sync-up.json
python ./baidupan-sync/scripts/bdpan_sync.py plan-down /网盘/目录 ./local-dir --manifest sync-down.json
python ./baidupan-sync/scripts/bdpan_sync.py commands-up ./local-dir /网盘/目录
python ./baidupan-sync/scripts/bdpan_sync.py commands-down /网盘/目录 ./local-dir
```

## 使用原则

- 先做 `plan-*`，再决定是否执行
- 有冲突时默认停下来，不自动覆盖更新较新的那一侧
- `--delete-extra` 只用于用户明确要求镜像同步的场景
