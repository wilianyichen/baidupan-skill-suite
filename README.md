# 百度网盘工具套件

打包日期：2026-04-22

## 包含内容

### 技能目录 (12 个)
1. **bypy-baidu-netdisk** - 基础认证技能
2. **bypy-enhanced** - 增强版命令行工具（主力使用）
3. **baidupan-monitor** - 目录监控技能（快照 / diff / watch）
4. **baidupan-sync** - 本地与网盘同步规划技能
5. **baidupan-cleanup** - 大文件 / 旧文件 / 重复候选分析技能
6. **baidupan-reconcile** - 本地 / 网盘、网盘 / 网盘差异对账技能
7. **baidupan-fs** - 远端文件系统操作规划技能
8. **baidupan-index** - 离线索引与查询技能
9. **baidupan-archive** - 归档计划技能
10. **baidupan-verify** - manifest 前置验证技能
11. **baidupan-batch-runner** - manifest 汇总与 runbook 技能
12. **baidupan-apply** - manifest 执行器技能（默认预览，显式确认执行）

### Token 文件
- `bypy.token.json` - 百度网盘访问令牌

## 使用方法

### 在 Windows / Linux 中使用

在项目根目录执行时，推荐直接用相对路径调用脚本。

### 打包给 Linux 使用

在当前 Windows 项目根目录执行：

```powershell
python .\scripts\package_linux_bundle.py
```

会生成一个 `dist/*.tar.gz`，默认不包含 `bypy.token.json`。

如果你确认要把当前 token 一起打进包：

```powershell
python .\scripts\package_linux_bundle.py --include-token
```

默认不建议这么做，除非这个包只在你自己的 Linux 机器之间传递。

### Linux 端安装步骤

把打好的 `tar.gz` 传到 Linux 后：

```bash
mkdir -p ~/tools
tar -xzf baidupan-tools-linux-*.tar.gz -C ~/tools
cd ~/tools/baidupan-tools
python3 ./scripts/bootstrap_min_venv.py
```

也可以直接运行：

```bash
bash ./scripts/install_linux.sh
```

如果包里没有 token，把你当前可用的 token 放到以下任一位置：

1. `~/.bypy/bypy.token.json`
2. `~/.bypy/bypy.json`
3. 项目根目录 `./bypy.token.json`
4. 项目根目录 `./bypy.json`

Linux 常用命令：

```bash
./.venv/bin/python ./bypy-enhanced/scripts/bdpan_enhanced.py info
./.venv/bin/python ./baidupan-monitor/scripts/bdpan_monitor.py --help
./.venv/bin/python ./baidupan-reconcile/scripts/bdpan_reconcile.py --help
./.venv/bin/python ./baidupan-apply/scripts/bdpan_apply.py --help
```

### Linux 端一键更新

如果 Linux 上已经有旧版 `~/tools/baidupan-tools`，推荐上传：

- 最新 `dist/*.tar.gz`
- `scripts/update_linux_bundle.sh`

然后在 Linux 上执行：

```bash
mkdir -p ~/upload
bash ~/upload/update_linux_bundle.sh ~/upload/baidupan-tools-linux-YYYYMMDD-HHMMSS.tar.gz ~/tools
```

这个更新脚本会做：

1. 备份旧目录
2. 解压新包到 `~/tools/baidupan-tools`
3. 恢复运行期数据：
   - `bypy.token.json`
   - `bypy.json`
   - `.bdpan_snapshots`
   - `.bypy_runtime`
   - `.venv`
4. 重新跑 `bootstrap_min_venv.py`
5. 刷新 `baidupan-suite` 到 `~/.codex/skills`
6. 做一次 `info` 烟雾测试

### 作为一个总 skill 给 Codex 使用

如果你只想让 Codex 识别一个总 skill，而不是 12 个子 skill，使用：

```bash
bash ~/tools/baidupan-tools/scripts/install_codex_suite_skill.sh
```

这个脚本会把：

```bash
~/tools/baidupan-tools/baidupan-suite
```

软链接到：

```bash
~/.codex/skills/baidupan-suite
```

手动方式也可以：

```bash
mkdir -p ~/.codex/skills
ln -sfn ~/tools/baidupan-tools/baidupan-suite ~/.codex/skills/baidupan-suite
```

然后新开一个 Codex 会话。

推荐触发方式：

- `用 baidupan-suite 查看百度网盘根目录`
- `用 baidupan-suite 比较本地目录和 /开智/录屏整理`
- `用 baidupan-suite 预览 archive manifest`

### 最小虚拟环境

当前项目已经创建了项目内虚拟环境 `.venv`，并验证可以直接运行核心脚本。

Windows PowerShell:
```powershell
.\.venv\Scripts\python.exe .\bypy-enhanced\scripts\bdpan_enhanced.py info
.\.venv\Scripts\python.exe .\bypy-baidu-netdisk\scripts\bypy_cmd.py info
```

Linux / macOS:
```bash
./.venv/bin/python ./bypy-enhanced/scripts/bdpan_enhanced.py info
./.venv/bin/python ./bypy-baidu-netdisk/scripts/bypy_cmd.py info
```

如果要重新创建最小环境，使用：

```bash
python ./scripts/bootstrap_min_venv.py
```

最小依赖清单见 `requirements.min.txt`，当前只包含：

- `requests`
- `bypy`

Linux / macOS:
```bash
python ./bypy-enhanced/scripts/bdpan_enhanced.py info
python ./bypy-enhanced/scripts/bdpan_enhanced.py list /
python ./bypy-enhanced/scripts/bdpan_enhanced.py upload ./local.txt /网盘路径/
python ./bypy-enhanced/scripts/bdpan_enhanced.py download /网盘/文件.txt ./downloads/
```

Windows PowerShell:
```powershell
python .\bypy-enhanced\scripts\bdpan_enhanced.py info
python .\bypy-enhanced\scripts\bdpan_enhanced.py list /
python .\bypy-enhanced\scripts\bdpan_enhanced.py upload .\local.txt /网盘路径/
python .\bypy-enhanced\scripts\bdpan_enhanced.py download /网盘/文件.txt .\downloads\
```

如果你已经把技能包安装到其他目录，直接把上面的相对路径替换成实际安装路径即可。

### 支持的命令
- `info` - 查看网盘容量
- `list` - 列出目录（显示时间戳）
- `tree` - 树形显示目录结构
- `search` - 搜索文件
- `stats` - 统计目录大小
- `delete` - 删除文件/目录
- `download` - 下载单文件（支持断点续传）
- `upload` - 上传文件（支持分片上传）
- `batch-download` - 批量下载整个目录

### 新增的二级技能

- `baidupan-monitor`
  - `init` / `check` / `diff` / `update` / `watch` / `tree` / `compare`
- `baidupan-sync`
  - `plan-up` / `plan-down` / `commands-up` / `commands-down`
- `baidupan-cleanup`
  - `large-files` / `stale-files` / `suffix-report` / `duplicate-candidates` / `empty-dirs`
- `baidupan-reconcile`
  - `compare-local` / `compare-remote` / `folder-summary` / `partial-files`
- `baidupan-fs`
  - `mkdir-plan` / `move-plan` / `copy-plan` / `rename-plan` / `archive-plan`
- `baidupan-index`
  - `build-local` / `build-remote` / `query` / `stats`
- `baidupan-archive`
  - `direct-paths` / `from-report`
- `baidupan-verify`
  - `manifest`
- `baidupan-batch-runner`
  - `summary` / `merge` / `runbook`
- `baidupan-apply`
  - `manifest`

## Token 配置

所有 Python 脚本现在统一按以下优先级查找 token：

1. 环境变量 `BYPY_TOKEN_FILE`
2. `~/.bypy/bypy.token.json`
3. `~/.bypy/bypy.json`
4. 当前工作目录下的 `./bypy.token.json`
5. 当前工作目录下的 `./bypy.json`
6. 项目根目录下的 `bypy.token.json`
7. 项目根目录下的 `bypy.json`

这意味着当前目录下的 `./bypy.token.json` 现在可以直接使用，优先级低于原始默认位置 `~/.bypy/bypy.token.json`。

对于依赖 `bypy` 库的包装脚本，项目会把命中的 token 规范化到一个显式 `configdir` 中，再用 `ByPy(configdir=...)` 启动。默认使用当前工作目录下的 `.bypy_runtime/`，也可以通过 `BYPY_CONFIG_DIR` 指定。这样不会依赖 `~/.bypy` 的写权限。

token 文件按 `utf-8-sig` 读取，能够兼容常见的 UTF-8 BOM 情况。

如果 token 过期，需要重新认证。

## 编码与路径兼容

- 所有 Python 脚本会在可用时把 stdout/stderr 重设为 UTF-8，降低 Windows 终端乱码概率
- 本地路径统一使用 `pathlib` / `os.path` 处理
- 网盘路径继续统一使用 `/` 作为远端路径分隔符
- 同步脚本生成建议命令时会按当前操作系统选择合适的 Python 可执行文件和命令行转义方式

## 监视对象附加能力

`baidupan-monitor` 现在会把快照视为一个可查询对象，支持：

- `tree`
  - 从已有快照中展开任意分支的完整目录结构
  - 支持 `--output` 保存到文件
- `compare`
  - 比较同一监视根目录下两个分支的相对结构
  - 支持 `--ignore-extension`，适合比较视频目录和音频目录的结构是否一致
  - 支持 `--output` 保存结果到文件

示例：

```powershell
.\.venv\Scripts\python.exe .\baidupan-monitor\scripts\bdpan_monitor.py tree /开智/录屏整理 --name kaizhi-recordings --branch 视频整理 --output .\tree.txt
.\.venv\Scripts\python.exe .\baidupan-monitor\scripts\bdpan_monitor.py compare /开智/录屏整理 视频整理 音频 --name kaizhi-recordings --ignore-extension --output .\compare.txt
```

## 新增二级工具

### 1. 对账

`baidupan-reconcile` 负责差异化比较，重点是清晰、可视、可保存的结果。

```powershell
.\.venv\Scripts\python.exe .\baidupan-reconcile\scripts\bdpan_reconcile.py compare-local .\local-dir /网盘/目录 --ignore-extension --output .\report.txt --json-output .\report.json
.\.venv\Scripts\python.exe .\baidupan-reconcile\scripts\bdpan_reconcile.py compare-remote /网盘/左分支 /网盘/右分支 --ignore-extension --output .\report.txt --json-output .\report.json
.\.venv\Scripts\python.exe .\baidupan-reconcile\scripts\bdpan_reconcile.py folder-summary .\report.json --output .\folders.txt --json-output .\folders.json
.\.venv\Scripts\python.exe .\baidupan-reconcile\scripts\bdpan_reconcile.py partial-files .\report.json --output .\partial-files.txt --json-output .\partial-files.json
```

### 2. 文件系统规划

`baidupan-fs` 只生成 manifest，不直接执行远端修改。删除类动作统一转换成归档计划。

```powershell
.\.venv\Scripts\python.exe .\baidupan-fs\scripts\bdpan_fs.py archive-plan /待归档/路径 --archive-root /归档整理 --output .\archive.json
```

### 3. 索引

`baidupan-index` 用于减少重复扫描。

```powershell
.\.venv\Scripts\python.exe .\baidupan-index\scripts\bdpan_index.py build-remote /开智/录屏整理 --output .\recordings-index.json --include-dirs
.\.venv\Scripts\python.exe .\baidupan-index\scripts\bdpan_index.py query .\recordings-index.json 智慧的大聪明 --limit 20
```

### 4. 归档 / 验证 / 批处理

```powershell
.\.venv\Scripts\python.exe .\baidupan-archive\scripts\bdpan_archive.py from-report .\report.json --source right --archive-root /归档整理 --output .\archive.json
.\.venv\Scripts\python.exe .\baidupan-verify\scripts\bdpan_verify.py manifest .\archive.json
.\.venv\Scripts\python.exe .\baidupan-apply\scripts\bdpan_apply.py manifest .\archive.json
.\.venv\Scripts\python.exe .\baidupan-apply\scripts\bdpan_apply.py manifest .\archive.json --execute --yes --log .\apply-log.json
.\.venv\Scripts\python.exe .\baidupan-batch-runner\scripts\bdpan_batch_runner.py runbook .\archive.json --output .\runbook.txt
```

### 5. 执行器

`baidupan-apply` 是当前唯一会真正执行远端变更的工具，但它默认仍是预览模式。

- 默认：只展示 manifest 预览
- 执行：必须显式传入 `--execute --yes`
- 当前仅支持：
  - `archive_remote`
  - `mkdir_remote`
  - `move_remote`
  - `rename_remote`
- 不支持：
  - `copy_remote`
  - 任何直接删除动作

建议顺序：

1. `reconcile` 产出差异报告
2. `archive` 或 `fs` 产出 manifest
3. `verify` 检查 source/target
4. `apply` 先预览
5. `apply --execute --yes` 执行
6. `batch-runner runbook` 留档

## 依赖

- Python 3.8+
- requests
- bypy

## 更新记录

### 2026-04-22
- 添加 upload 上传功能
- 添加 batch-download 批量下载
- 增强 list 输出（显示时间戳）
- 完成 baidupan-monitor 监控技能
- 新增 baidupan-sync 同步规划技能
- 新增 baidupan-cleanup 清理分析技能
- 重写总控 skill，使其支持技能路由
- 新增统一运行时，支持 Windows / Linux 跨平台路径与编码处理
- 统一支持当前工作目录下的 `bypy.token.json` 作为低优先级 token 来源
- 新增 baidupan-reconcile，对焦本地 / 网盘、网盘 / 网盘差异化比较
- 新增 baidupan-fs，以 manifest 形式规划 mkdir / move / rename / copy / archive
- 新增 baidupan-index，用于导出离线索引并查询
- 新增 baidupan-archive / baidupan-verify / baidupan-batch-runner，串联归档、验证和批处理 runbook
- 新增 baidupan-apply，支持在显式确认下执行 archive/mkdir/move/rename manifest

### 2026-04-23
- 新增 baidupan-apply 执行器，默认预览，`--execute --yes` 才真正执行
- 新增 reconcile 的 `folder-summary` 和 `partial-files` 结果视图
- 修复 manifest 在 Windows BOM 编码下的读取兼容性
