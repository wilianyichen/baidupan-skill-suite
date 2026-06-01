---
name: baidupan-index
description: 百度网盘索引技能。把本地目录或网盘目录导出为离线索引，支持 query、stats、export，减少重复扫描。
---

# 百度网盘索引技能

## 命令入口

```bash
python ./baidupan-index/scripts/bdpan_index.py build-local ./local-dir --output local-index.json
python ./baidupan-index/scripts/bdpan_index.py build-remote /网盘/目录 --include-dirs --output remote-index.json
python ./baidupan-index/scripts/bdpan_index.py query remote-index.json 关键字 --limit 50
python ./baidupan-index/scripts/bdpan_index.py stats remote-index.json
```

## 说明

- `build-remote` 现优先复用 `xpan/multimedia?method=listall` 做流式远端扫描，减少逐目录 DFS 请求
- 远端索引条目会携带 `relative_path / absolute_path / type / size / mtime / fs_id / category / suffix`
- 目录项的 `size` 不是递归累计大小；目录总大小请用 `bypy-enhanced du`
