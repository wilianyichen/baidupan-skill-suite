---
name: baidupan-index
description: 百度网盘索引技能。把本地目录或网盘目录导出为离线索引，支持 query、stats、export，减少重复扫描。
---

# 百度网盘索引技能

## 命令入口

```bash
python ./baidupan-index/scripts/bdpan_index.py build-local ./local-dir --output local-index.json
python ./baidupan-index/scripts/bdpan_index.py build-remote /网盘/目录 --output remote-index.json
python ./baidupan-index/scripts/bdpan_index.py query remote-index.json 关键字 --limit 50
python ./baidupan-index/scripts/bdpan_index.py stats remote-index.json
```
