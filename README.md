# baidupan-skill-suite

一组面向 Codex / agent 工作流的百度网盘技能与脚本，覆盖：

- 目录浏览与传输
- 目录监视与结构比较
- 本地 / 网盘、网盘 / 网盘差异对账
- 归档优先的安全整理流程
- manifest 规划、验证、预览与执行

这不是单个 skill，而是一整套 skill 组。

## 能力概览

当前包含 12 个技能目录：

1. `bypy-baidu-netdisk`  
   基础认证与总控入口。
2. `bypy-enhanced`  
   增强版只读与传输工具。
3. `baidupan-monitor`  
   快照、diff、watch、tree、compare。
4. `baidupan-sync`  
   本地与网盘同步规划。
5. `baidupan-cleanup`  
   大文件、旧文件、重复候选、空目录分析。
6. `baidupan-reconcile`  
   本地 / 网盘、网盘 / 网盘差异对账。
7. `baidupan-fs`  
   `mkdir/move/copy/rename/archive` manifest 规划。
8. `baidupan-index`  
   本地或网盘目录离线索引。
9. `baidupan-archive`  
   归档计划生成。
10. `baidupan-verify`  
   manifest 前置验证。
11. `baidupan-batch-runner`  
   manifest 汇总、合并、runbook。
12. `baidupan-apply`  
   manifest 执行器，默认预览，显式确认后执行。

另外提供一个总 skill：

- `baidupan-suite`  
  统一路由上述工具，适合给 Codex 挂载成单个入口 skill。

## 设计原则

- 先分析，再修复
- 先生成 manifest，再执行
- 删除类动作统一先转成归档
- 默认预览，只有显式确认才真正修改远端
- 兼容 Windows / Linux

## 目录结构

```text
baidupan-skill-suite/
├── baidupan-suite/            # Codex 总 skill
├── bypy-enhanced/             # 浏览 / 搜索 / 下载 / 上传
├── baidupan-monitor/          # 快照 / 比较 / tree
├── baidupan-reconcile/        # 差异对账
├── baidupan-fs/               # 远端整理规划
├── baidupan-archive/          # 归档计划
├── baidupan-verify/           # manifest 验证
├── baidupan-apply/            # manifest 执行器
├── baidupan-index/            # 离线索引
├── baidupan-sync/             # 同步规划
├── baidupan-cleanup/          # 清理分析
├── baidupan-batch-runner/     # runbook / merge
├── common/                    # 共享运行时 / inventory / manifest
├── scripts/                   # 打包 / 安装 / 更新脚本
└── docs/plans/                # 设计说明
```

## 依赖

- Python 3.8+
- `requests`
- `bypy`

最小依赖文件见：

- [requirements.min.txt](./requirements.min.txt)

## Token 规则

所有 Python 脚本统一按以下优先级查找 token：

1. `BYPY_TOKEN_FILE`
2. `~/.bypy/bypy.token.json`
3. `~/.bypy/bypy.json`
4. 当前工作目录 `./bypy.token.json`
5. 当前工作目录 `./bypy.json`
6. 工具根目录下的 `bypy.token.json`
7. 工具根目录下的 `bypy.json`

注意：

- `bypy.token.json`、`bypy.json` 不应提交到 Git 仓库
- token 文件按 `utf-8-sig` 读取，兼容 Windows BOM

## 快速开始

### 1. 在本地运行

创建最小虚拟环境：

```bash
python ./scripts/bootstrap_min_venv.py
```

Windows 示例：

```powershell
.\.venv\Scripts\python.exe .\bypy-enhanced\scripts\bdpan_enhanced.py info
.\.venv\Scripts\python.exe .\baidupan-reconcile\scripts\bdpan_reconcile.py --help
```

Linux 示例：

```bash
./.venv/bin/python ./bypy-enhanced/scripts/bdpan_enhanced.py info
./.venv/bin/python ./baidupan-reconcile/scripts/bdpan_reconcile.py --help
```

### 2. 打包给 Linux 使用

生成 Linux 包：

```powershell
python .\scripts\package_linux_bundle.py
```

默认输出到：

```text
dist/baidupan-tools-linux-YYYYMMDD-HHMMSS.tar.gz
```

默认不包含 token。

### 3. Linux 端安装

```bash
mkdir -p ~/tools
tar -xzf baidupan-tools-linux-*.tar.gz -C ~/tools
cd ~/tools/baidupan-tools
python3 ./scripts/bootstrap_min_venv.py
```

或者直接：

```bash
bash ./scripts/install_linux.sh
```

### 4. Linux 端一键更新

上传：

- 最新 `dist/*.tar.gz`
- `scripts/update_linux_bundle.sh`

然后执行：

```bash
bash ~/upload/update_linux_bundle.sh ~/upload/baidupan-tools-linux-YYYYMMDD-HHMMSS.tar.gz ~/tools
```

这个脚本会：

1. 备份旧目录
2. 解压新包
3. 恢复 `.venv`、`.bdpan_snapshots`、`.bypy_runtime`、token
4. 重新跑 `bootstrap_min_venv.py`
5. 刷新总 skill
6. 做一次烟雾测试

## 作为一个总 skill 给 Codex 使用

推荐在 Linux 上安装总 skill：

```bash
bash ~/tools/baidupan-tools/scripts/install_codex_suite_skill.sh
```

这会创建：

```bash
~/.codex/skills/baidupan-suite -> ~/tools/baidupan-tools/baidupan-suite
```

手动方式：

```bash
mkdir -p ~/.codex/skills
ln -sfn ~/tools/baidupan-tools/baidupan-suite ~/.codex/skills/baidupan-suite
```

然后新开一个 Codex 会话。

推荐触发词：

- `用 baidupan-suite 查看百度网盘根目录`
- `用 baidupan-suite 监视 /开智/录屏整理`
- `用 baidupan-suite 比较本地目录和 /开智/录屏整理`
- `用 baidupan-suite 预览 archive manifest`

## 典型工作流

### 1. 浏览与传输

```bash
./.venv/bin/python ./bypy-enhanced/scripts/bdpan_enhanced.py list /
./.venv/bin/python ./bypy-enhanced/scripts/bdpan_enhanced.py tree /开智 -d 2
```

### 2. 监视与结构比较

```bash
./.venv/bin/python ./baidupan-monitor/scripts/bdpan_monitor.py init /开智/录屏整理 --name kaizhi-recordings
./.venv/bin/python ./baidupan-monitor/scripts/bdpan_monitor.py compare /开智/录屏整理 视频整理 音频 --name kaizhi-recordings --ignore-extension --output compare.txt
```

### 3. 差异对账

```bash
./.venv/bin/python ./baidupan-reconcile/scripts/bdpan_reconcile.py compare-local ./local-dir /开智/录屏整理 --ignore-extension --output report.txt --json-output report.json
./.venv/bin/python ./baidupan-reconcile/scripts/bdpan_reconcile.py folder-summary report.json --output folders.txt
./.venv/bin/python ./baidupan-reconcile/scripts/bdpan_reconcile.py partial-files report.json --output partial-files.txt
```

### 4. 归档优先的执行链

```bash
./.venv/bin/python ./baidupan-archive/scripts/bdpan_archive.py from-report report.json --source right --archive-root /归档整理 --output archive.json
./.venv/bin/python ./baidupan-verify/scripts/bdpan_verify.py manifest archive.json
./.venv/bin/python ./baidupan-apply/scripts/bdpan_apply.py manifest archive.json
./.venv/bin/python ./baidupan-apply/scripts/bdpan_apply.py manifest archive.json --execute --yes --log apply-log.json
./.venv/bin/python ./baidupan-batch-runner/scripts/bdpan_batch_runner.py runbook archive.json --output runbook.txt
```

## 安全说明

- 不要把 token、快照、运行时目录、虚拟环境提交到 Git
- `baidupan-apply` 默认是预览模式
- 删除类动作应先转换成 `archive_remote`
- 如果你要做真实移动或归档，先跑 `verify`

## 发布产物

打包脚本：

- [scripts/package_linux_bundle.py](./scripts/package_linux_bundle.py)
- [scripts/make_release.py](./scripts/make_release.py)

更新脚本：

- [scripts/update_linux_bundle.sh](./scripts/update_linux_bundle.sh)

总 skill 安装脚本：

- [scripts/install_codex_suite_skill.sh](./scripts/install_codex_suite_skill.sh)

## 版本发布

当前版本：

- `v0.1.0`

生成版本化 release 产物：

```powershell
python .\scripts\make_release.py
```

会在 `dist/` 下生成：

- `baidupan-skill-suite-v0.1.0-linux.tar.gz`
- `baidupan-skill-suite-v0.1.0-linux.sha256`
- `baidupan-skill-suite-v0.1.0-release-notes.md`

## 设计文档

- [2026-04-22-baidu-netdisk-skill-design.md](./docs/plans/2026-04-22-baidu-netdisk-skill-design.md)
- [2026-04-22-secondary-tools-design.md](./docs/plans/2026-04-22-secondary-tools-design.md)
- [2026-04-23-baidupan-apply-design.md](./docs/plans/2026-04-23-baidupan-apply-design.md)

## 发布说明

- [v0.1.0](./docs/releases/v0.1.0.md)

## 许可证

仓库包含：

- [LICENSE](./LICENSE)
