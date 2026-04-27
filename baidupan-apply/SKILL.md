---
name: baidupan-apply
description: 百度网盘执行器技能。对 manifest 做预览、确认执行和结果日志输出，第一版支持 archive_remote、mkdir_remote、move_remote、rename_remote。
---

# 百度网盘执行器技能

这个技能负责把前面规划好的 manifest 真正落地。默认只预览，不执行。

## 命令入口

```bash
python ./baidupan-apply/scripts/bdpan_apply.py manifest plan.json
python ./baidupan-apply/scripts/bdpan_apply.py manifest plan.json --execute --yes --log apply-log.json
```

## 当前支持的动作

- `archive_remote`
- `mkdir_remote`
- `move_remote`
- `rename_remote`

## 约束

- 默认预览
- 只有显式传入 `--execute --yes` 才执行
- 删除类动作必须先转成 `archive_remote`
