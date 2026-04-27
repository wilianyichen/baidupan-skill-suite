---
name: bypy-baidu-netdisk
description: 基于 bypy 的百度网盘总控技能。处理认证、基础上传下载、目录查看，并把任务路由到增强版、目录监控、同步规划、清理分析等二级技能。
---

# 百度网盘总控技能

这是整个百度网盘技能包的入口技能。默认先判断任务类型，再选择最合适的二级技能或脚本。

## 默认工作流

1. 先确认 token 是否存在，优先查找：
   - 环境变量 `BYPY_TOKEN_FILE`
   - `~/.bypy/bypy.token.json`
   - `~/.bypy/bypy.json`
   - 当前工作目录下的 `./bypy.token.json`
   - 当前工作目录下的 `./bypy.json`
   - 技能包根目录下的 `bypy.token.json`
   - 技能包根目录下的 `bypy.json`
2. 默认先做只读探查，再执行修改：
   - `info`
   - `list`
   - `tree`
   - `stats`
3. 涉及删除、覆盖、批量同步时，先给出计划、差异或待执行命令。
4. 如果用户只是要单次文件操作，优先用现成脚本，不要重新发明调用流程。

## 路由规则

- 基础认证、简单上传下载、快速解释 bypy 命令：继续使用当前技能
- 需要树形浏览、搜索、统计、批量下载：切到 `bypy-enhanced`
- 需要监控目录变化、做快照对比：切到 `baidupan-monitor`
- 需要比较本地目录和网盘目录、生成同步计划：切到 `baidupan-sync`
- 需要找大文件、旧文件、可疑重复文件、空目录：切到 `baidupan-cleanup`
- 需要做本地 / 网盘或网盘 / 网盘差异对账：切到 `baidupan-reconcile`
- 需要为 move / rename / mkdir / 归档生成 manifest：切到 `baidupan-fs`
- 需要导出离线索引：切到 `baidupan-index`
- 需要把远端独有文件转成归档计划：切到 `baidupan-archive`
- 需要在执行前验证 manifest：切到 `baidupan-verify`
- 需要真正执行 manifest：切到 `baidupan-apply`
- 需要合并或渲染多个 manifest：切到 `baidupan-batch-runner`

## 基础操作建议

- 认证仍以 `bypy` 为主，因为它最适合处理首次 OAuth 授权
- 高级只读分析优先使用本技能包中的原生 API 脚本
- 对写操作保持保守：先看、再计划、再执行
- 所有 Python 脚本应兼容 Windows 和 Linux，避免写死 `/home/...` 这类路径
- 如果 `bypy` 包装脚本命中了当前目录 token，会自动写入当前工作目录下的 `.bypy_runtime/`，并通过 `ByPy(configdir=...)` 使用它

## 常用入口

```bash
# 首次认证
bypy info

# 基础 bypy 操作
bypy list /
bypy upload local.txt /备份/
bypy download /备份/local.txt .

# 增强版只读与传输
python ./bypy-enhanced/scripts/bdpan_enhanced.py tree / -d 2
python ./bypy-enhanced/scripts/bdpan_enhanced.py search "关键字" /
python ./bypy-enhanced/scripts/bdpan_enhanced.py batch-download /资料 ./downloads/
```

需要更细的命令分流时，再读取 `references/command-routing.md`。
