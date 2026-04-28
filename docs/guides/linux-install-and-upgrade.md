# Linux 安装与升级指南

适用对象：

- 你已经把 `baidupan-skill-suite` 上传到 Linux
- 你想在服务器上直接运行脚本
- 你想把它作为一个总 skill 提供给 Codex 使用

---

## 目录约定

本文默认安装目录：

```bash
~/tools/baidupan-tools
```

默认上传临时目录：

```bash
~/upload
```

---

## 一、首次安装

### 1. 上传 release 包

上传文件：

- `baidupan-skill-suite-vX.Y.Z-linux.tar.gz`

到服务器：

```bash
mkdir -p ~/upload
```

例如上传后路径为：

```bash
~/upload/baidupan-skill-suite-v0.1.0-linux.tar.gz
```

### 2. 解压

```bash
mkdir -p ~/tools
tar -xzf ~/upload/baidupan-skill-suite-v0.1.0-linux.tar.gz -C ~/tools
```

解压后目标目录应为：

```bash
~/tools/baidupan-tools
```

### 3. 创建最小环境

```bash
python3 ~/tools/baidupan-tools/scripts/bootstrap_min_venv.py
```

### 4. 放置 token

支持任一位置：

1. `~/.bypy/bypy.token.json`
2. `~/.bypy/bypy.json`
3. `~/tools/baidupan-tools/bypy.token.json`
4. `~/tools/baidupan-tools/bypy.json`

建议优先用：

```bash
~/.bypy/bypy.token.json
```

### 5. 烟雾测试

```bash
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/bypy-enhanced/scripts/bdpan_enhanced.py info
```

如果返回容量信息，说明基础链路可用。

---

## 二、安装为 Codex 总 skill

推荐安装总 skill：

```bash
bash ~/tools/baidupan-tools/scripts/install_codex_suite_skill.sh
```

效果：

```bash
~/.codex/skills/baidupan-suite -> ~/tools/baidupan-tools/baidupan-suite
```

然后新开一个 Codex 会话。

推荐触发方式：

- `用 baidupan-suite 查看百度网盘根目录`
- `用 baidupan-suite 监视 /开智/录屏整理`
- `用 baidupan-suite 比较本地目录和 /开智/录屏整理`
- `用 baidupan-suite 预览 archive manifest`

---

## 三、升级

### 推荐方式：一键更新

上传两个文件到服务器：

- `baidupan-skill-suite-vX.Y.Z-linux.tar.gz`
- `update_linux_bundle.sh`

执行：

```bash
chmod +x ~/upload/update_linux_bundle.sh
bash ~/upload/update_linux_bundle.sh ~/upload/baidupan-skill-suite-vX.Y.Z-linux.tar.gz ~/tools
```

这个脚本会自动：

1. 备份旧目录
2. 解压新版本
3. 恢复运行期数据：
   - token
   - `.venv`
   - `.bdpan_snapshots`
   - `.bypy_runtime`
4. 重新跑 `bootstrap_min_venv.py`
5. 刷新 `baidupan-suite`
6. 做一次 `info` 烟雾测试

---

## 四、升级后验证

### 1. 验证目录树大小

```bash
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/bypy-enhanced/scripts/bdpan_enhanced.py tree /开智/录屏整理 -d 1
```

期望目录大小不是 `0.00 B`。

### 2. 建立或刷新监视快照

如果之前没有快照，先初始化：

```bash
mkdir -p ~/tools/baidupan-tools/.bdpan_snapshots
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-monitor/scripts/bdpan_monitor.py init /开智/录屏整理 --name kaizhi-recordings
```

如果已经有快照，刷新：

```bash
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-monitor/scripts/bdpan_monitor.py update /开智/录屏整理 --name kaizhi-recordings --limit 10
```

查看树：

```bash
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-monitor/scripts/bdpan_monitor.py tree /开智/录屏整理 --name kaizhi-recordings --depth 1
```

---

## 五、常用命令

### 浏览

```bash
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/bypy-enhanced/scripts/bdpan_enhanced.py list /
```

### 对账

```bash
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-reconcile/scripts/bdpan_reconcile.py compare-remote /开智/录屏整理/视频整理 /开智/录屏整理/音频 --ignore-extension --output report.txt --json-output report.json
```

### 归档链

```bash
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-archive/scripts/bdpan_archive.py from-report report.json --source left --archive-root /归档整理 --output archive.json
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-verify/scripts/bdpan_verify.py manifest archive.json
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-apply/scripts/bdpan_apply.py manifest archive.json
```

---

## 六、常见问题

### 1. `快照不存在`

这不是程序异常，通常是你还没 `init` 建基线快照。

### 2. 树里目录大小是 `0.00 B`

通常说明 Linux 上还是旧版本脚本，或快照没刷新。  
先更新，再跑一次：

```bash
bdpan_monitor.py update ...
```

### 3. `baidupan-suite` 没被 Codex 识别

检查：

```bash
ls -l ~/.codex/skills/baidupan-suite
ls -l ~/tools/baidupan-tools/baidupan-suite/SKILL.md
```

并重新开一个 Codex 会话。
