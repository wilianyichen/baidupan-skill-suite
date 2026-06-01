---
name: bypy-enhanced
description: 百度网盘增强技能。基于 token 和原生 API 提供 tree、search、stats、upload、download、batch-download 等更清晰的操作入口。
---

# 百度网盘增强技能

当任务需要更好的可视化输出、批量只读分析，或希望绕开 `bypy` 的部分交互问题时，优先使用这个技能。

## 适用场景

- 递归浏览目录树
- 统计目录大小或做流式聚合统计
- 使用百度原生搜索接口搜索文件
- 查看当前授权账号、文件元信息、下载链接前置元数据
- 下载单文件或整个目录
- 上传单文件到指定目录

## 默认入口

```bash
python ./bypy-enhanced/scripts/bdpan_enhanced.py doctor
python ./bypy-enhanced/scripts/bdpan_enhanced.py auth
python ./bypy-enhanced/scripts/bdpan_enhanced.py auth --code <AUTH_CODE>
python ./bypy-enhanced/scripts/bdpan_enhanced.py info
python ./bypy-enhanced/scripts/bdpan_enhanced.py whoami
python ./bypy-enhanced/scripts/bdpan_enhanced.py list /路径
python ./bypy-enhanced/scripts/bdpan_enhanced.py tree /路径 -d 3 --size none
python ./bypy-enhanced/scripts/bdpan_enhanced.py tree /路径 -d 2 --size recursive
python ./bypy-enhanced/scripts/bdpan_enhanced.py du /路径
python ./bypy-enhanced/scripts/bdpan_enhanced.py du /路径A /路径B --concurrency 2
python ./bypy-enhanced/scripts/bdpan_enhanced.py search "关键词" /路径 --limit 20
python ./bypy-enhanced/scripts/bdpan_enhanced.py stats /路径 --top 10
python ./bypy-enhanced/scripts/bdpan_enhanced.py metas /网盘/文件路径
python ./bypy-enhanced/scripts/bdpan_enhanced.py upload 本地文件 /网盘目录/
python ./bypy-enhanced/scripts/bdpan_enhanced.py download /网盘文件 ./downloads/
python ./bypy-enhanced/scripts/bdpan_enhanced.py batch-download /网盘目录 ./downloads/
```

## 使用原则

- 先读后写，先看目录再操作文件
- 先运行 `doctor` 检查 Python、token、skill 安装状态，再进入网盘操作
- 首次授权使用 `auth`，它会打印浏览器授权链接，并支持 `auth --code <AUTH_CODE>` 直接写 token
- `tree` 默认推荐 `--size none`，结构浏览与递归统计分离
- 目录总大小优先使用 `du`，其底层走 `xpan/multimedia?method=listall` 分页流式统计
- `search` 优先使用百度原生 `method=search`，避免客户端 DFS 扫全盘
- `metas` 使用 `method=filemetas`；目录 `size` 不是递归总大小，会明确标注
- 多路径 `du` 可受控并行；单一路径 listall 的 cursor 分页保持顺序，不强行并行
- 长时间 `du` 可启用 `--resume` 记录 checkpoint 到 `.bypy_runtime/listall-checkpoints/`
- 批量操作前先确认目标路径，必要时配合 `baidupan-sync` 先生成计划
- token 优先读取 `~/.bypy/bypy.token.json`，然后依次回退到当前工作目录和技能包根目录下的 `bypy.token.json`
- 脚本默认兼容 Windows 和 Linux，输出按 UTF-8 处理
