---
name: baidupan-batch-runner
description: 百度网盘批处理清单工具。对多个 manifest 做汇总、合并、runbook 渲染，当前不执行实际变更。
---

# 百度网盘批处理清单工具

## 命令入口

```bash
python ./baidupan-batch-runner/scripts/bdpan_batch_runner.py summary plan1.json plan2.json
python ./baidupan-batch-runner/scripts/bdpan_batch_runner.py merge merged.json plan1.json plan2.json
python ./baidupan-batch-runner/scripts/bdpan_batch_runner.py runbook merged.json --output runbook.txt
```
