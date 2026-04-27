---
name: baidupan-cleanup
description: 百度网盘清理分析技能。扫描目录中的大文件、旧文件、后缀分布、重复候选和空目录，帮助做清理决策。
---

# 百度网盘清理分析技能

这个技能专门做“先分析再清理”。它默认只读，不直接删除文件。

## 典型场景

- 找出目录里最大的文件
- 找出长期未更新的旧文件
- 看看某个目录里主要都是什么类型的文件
- 找可能重复的文件名与大小组合
- 找空目录

## 命令入口

```bash
python ./baidupan-cleanup/scripts/bdpan_cleanup.py large-files /网盘/目录 --top 30
python ./baidupan-cleanup/scripts/bdpan_cleanup.py stale-files /网盘/目录 --days 180
python ./baidupan-cleanup/scripts/bdpan_cleanup.py suffix-report /网盘/目录 --top 20
python ./baidupan-cleanup/scripts/bdpan_cleanup.py duplicate-candidates /网盘/目录
python ./baidupan-cleanup/scripts/bdpan_cleanup.py empty-dirs /网盘/目录
```

## 使用原则

- 先扫描、后决策，不自动删除
- `duplicate-candidates` 是“同名同大小”的重复候选，不等于内容绝对相同
- 真要删文件时，再把结果交给总控 skill 或增强脚本处理
