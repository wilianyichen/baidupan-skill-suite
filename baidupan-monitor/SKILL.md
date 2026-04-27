---
name: baidupan-monitor
description: 百度网盘目录监控技能。通过快照和哈希树对比目录变化，支持 init、check、diff、update、watch。
---

# 百度网盘目录监控技能

这个技能用于回答“目录有没有变化”“新增了哪些文件”“我想持续盯住这个目录”这类问题。

## 典型场景

- 给某个网盘目录建立初始快照
- 检查从上次观察到现在是否有变化
- 输出新增、删除、修改的详细列表
- 定时轮询一个目录

## 命令入口

```bash
python ./baidupan-monitor/scripts/bdpan_monitor.py init /网盘/目录 --name docs-snapshot
python ./baidupan-monitor/scripts/bdpan_monitor.py check /网盘/目录 --name docs-snapshot
python ./baidupan-monitor/scripts/bdpan_monitor.py diff /网盘/目录 --name docs-snapshot
python ./baidupan-monitor/scripts/bdpan_monitor.py update /网盘/目录 --name docs-snapshot
python ./baidupan-monitor/scripts/bdpan_monitor.py watch /网盘/目录 --name docs-snapshot --interval 300
python ./baidupan-monitor/scripts/bdpan_monitor.py tree /网盘/目录 --name docs-snapshot --branch 子目录 --output tree.txt
python ./baidupan-monitor/scripts/bdpan_monitor.py compare /网盘/目录 左分支 右分支 --name docs-snapshot --ignore-extension --output compare.txt
```

## 注意事项

- 这是快照轮询，不是服务端推送
- 大目录首次扫描会比较慢
- 更新快照前，最好先跑一次 `diff` 看看变化是否符合预期
- `tree` 和 `compare` 默认基于本地快照工作，不会重新请求网盘
- `compare --ignore-extension` 适合对比视频目录和音频目录的相对结构是否对齐
