# 百度网盘总技能路由示例

## 浏览与传输

```bash
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/bypy-enhanced/scripts/bdpan_enhanced.py info
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/bypy-enhanced/scripts/bdpan_enhanced.py list /
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/bypy-enhanced/scripts/bdpan_enhanced.py tree /开智 -d 2
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/bypy-enhanced/scripts/bdpan_enhanced.py download /网盘/文件.txt ./downloads/
```

## 监视与结构比较

```bash
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-monitor/scripts/bdpan_monitor.py init /开智/录屏整理 --name kaizhi-recordings
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-monitor/scripts/bdpan_monitor.py compare /开智/录屏整理 视频整理 音频 --name kaizhi-recordings --ignore-extension --output compare.txt
```

## 对账与归档

```bash
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-reconcile/scripts/bdpan_reconcile.py compare-remote /开智/录屏整理/视频整理 /开智/录屏整理/音频 --ignore-extension --output report.txt --json-output report.json
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-archive/scripts/bdpan_archive.py from-report report.json --source left --archive-root /归档整理 --output archive.json
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-verify/scripts/bdpan_verify.py manifest archive.json
~/tools/baidupan-tools/.venv/bin/python ~/tools/baidupan-tools/baidupan-apply/scripts/bdpan_apply.py manifest archive.json
```
