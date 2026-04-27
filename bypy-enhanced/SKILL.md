---
name: bypy-enhanced
description: 百度网盘增强技能。基于 token 和原生 API 提供 tree、search、stats、upload、download、batch-download 等更清晰的操作入口。
---

# 百度网盘增强技能

当任务需要更好的可视化输出、批量只读分析，或希望绕开 `bypy` 的部分交互问题时，优先使用这个技能。

## 适用场景

- 递归浏览目录树
- 搜索文件
- 统计目录大小
- 下载单文件或整个目录
- 上传单文件到指定目录

## 默认入口

```bash
python ./bypy-enhanced/scripts/bdpan_enhanced.py info
python ./bypy-enhanced/scripts/bdpan_enhanced.py list /路径
python ./bypy-enhanced/scripts/bdpan_enhanced.py tree /路径 -d 3
python ./bypy-enhanced/scripts/bdpan_enhanced.py search "关键词" /路径
python ./bypy-enhanced/scripts/bdpan_enhanced.py stats /路径
python ./bypy-enhanced/scripts/bdpan_enhanced.py upload 本地文件 /网盘目录/
python ./bypy-enhanced/scripts/bdpan_enhanced.py download /网盘文件 ./downloads/
python ./bypy-enhanced/scripts/bdpan_enhanced.py batch-download /网盘目录 ./downloads/
```

## 使用原则

- 先读后写，先看目录再操作文件
- 大目录优先用 `tree -d N` 或 `stats`，避免一次性输出过多
- 批量操作前先确认目标路径，必要时配合 `baidupan-sync` 先生成计划
- token 优先读取 `~/.bypy/bypy.token.json`，然后依次回退到当前工作目录和技能包根目录下的 `bypy.token.json`
- 脚本默认兼容 Windows 和 Linux，输出按 UTF-8 处理
