# Agentic RAG Evaluation Report

- started_at: 2026-11-22T14:35:07
- model: Qwen/Qwen3-8B | embedding: BAAI/bge-m3
- mode: rag | runs: 1 | tasks: 26

## Summary

| Metric | Value |
| --- | --- |
| Answer accuracy | 69.23% |
| Task success (answer + tools) | 69.23% |
| pass^1 | 69.23% |
| Avg steps | 1 |
| Avg latency | 3.06s |
| P95 latency | 5.72s |
| Errors | 0 |

## Per task

| ID | Question | Answer | Tool | Success | Steps | Latency | Tools called |
| --- | --- | --- | --- | --- | --- | --- | --- |
| KB01 | CoT 和 ReAct 的本质区别是什么？ | CoT 和 ReAct 的本质区别在于：CoT 是纯推理链文字，而 ReAct 是  | ✓ | ✓ | 1 | 4.18s | - |
| KB02 | Recall@k 已经很高了，为什么用户还是觉得答不准？ | Recall@k 高并不意味着用户觉得答不准，因为 Recall@k 只衡量了**链 | ✓ | ✓ | 1 | 5.04s | - |
| KB03 | 用户问法和文档里的说法完全不一样，怎么提高命中率？ | 可以通过使用Layout-aware解析和表格结构化技术来处理文档中的表格和图纸，同 | ✗ | ✗ | 1 | 5.29s | - |
| KB04 | 生产环境里怎么防止 Agent 陷入无限循环？ | 生产环境里防止 Agent 陷入无限循环的方法包括：设置 `max_iteratio | ✓ | ✓ | 1 | 6.74s | - |
| KB05 | 长上下文窗口越来越大，是不是就不需要 RAG 了？ | 不是，窗口大 ≠ 记忆好。长上下文模型在超长输入上的有效利用率通常远低于标称值，且成 | ✓ | ✓ | 1 | 2.45s | - |
| KB06 | 幻觉有哪些缓解手段？哪种最有效？ | 幻觉的缓解手段包括 RAG、Function Calling、Structured  | ✓ | ✓ | 1 | 2.5s | - |
| KB07 | Transcript 和 Outcome 这两个概念的区别是什么？ | Transcript 是 Agent 在对话中说的内容，如'订单已创建'；Outco | ✓ | ✓ | 1 | 3.1s | - |
| KB08 | pass@k 和 pass^k 分别表示什么？ | pass@k 表示 k 次尝试中至少 1 次成功的概率，适合 coding agen | ✓ | ✓ | 1 | 3.1s | - |
| KB09 | 四级 Ship Gate 是什么？ | 四级 Ship Gate 是模型升级能否上线的评估流程，包括 Offline Dif | ✓ | ✓ | 1 | 2.04s | - |
| KB10 | 做自动评分时，code-based 和 LLM judge 怎么分工？ | 在自动评分中，code-based 和 LLM judge 的分工是：code-ba | ✓ | ✓ | 1 | 3.44s | - |
| KB11 | 最小可用 Benchmark 要多少个 task？怎么分配？ | 最小可用 Benchmark 是 150 个 task。这些 task 分配为四个  | ✓ | ✓ | 1 | 5.07s | - |
| KB12 | ALM-1042 报警的触发条件和处理步骤是什么？ | ALM-1042 报警的触发条件是腔体压力偏离设定值超过 8% 且持续 3 秒以上。 | ✓ | ✓ | 1 | 5.72s | - |
| KB13 | SPC 控制图有哪些判异规则？ | SPC 控制图的判异规则包括：1. 单点超出 ±3σ；2. 连续 3 点中有 2 点 | ✓ | ✓ | 1 | 4.71s | - |
| KB14 | APC 的三层分别负责什么？ | APC 的三层分别负责：1. FDC（故障检测与分类）负责从设备传感器数据实时判断「 | ✓ | ✓ | 1 | 4.11s | - |
| KB15 | ALM-2087 报警应该怎么处理？ | 处理 ALM-2087 报警应先做匹配网络自动调谐；若无效，检查电极积碳并安排预防性 | ✓ | ✓ | 1 | 2.55s | - |
| TK01 | T-1001 工单现在是什么状态？ | 资料不足 | ✗ | ✗ | 1 | 1.82s | - |
| TK02 | T-1002 工单的优先级是什么？ | 资料不足 | ✗ | ✗ | 1 | 1.54s | - |
| TK03 | T-9999 工单现在是什么状态？ | 资料不足 | ✗ | ✗ | 1 | 1.8s | - |
| TK04 | T-1004 涉及哪个报警码，处理结果是什么？ | 资料不足 | ✗ | ✗ | 1 | 1.79s | - |
| CA01 | 某批次 24 片，良率 92.5%，良品多少片？ | 该批次良品数量为 22 片。 | ✗ | ✗ | 1 | 1.58s | - |
| CA02 | 每片测试 45 秒，24 片需要多少分钟？ | 每片测试45秒，24片需要45 * 24 = 1080秒，即18分钟。 | ✓ | ✓ | 1 | 2.04s | - |
| CA03 | 3 个腔体，每个 12 片，一共多少片？ | 3 个腔体，每个 12 片，一共 36 片。 | ✓ | ✓ | 1 | 2.04s | - |
| MX01 | T-1001 涉及的报警应该怎么处理？ | 资料不足 | ✗ | ✗ | 1 | 1.76s | - |
| MX02 | T-1003 的批次良率是多少？如果 24 片，良品多少片？ | 资料不足 | ✗ | ✗ | 1 | 2.01s | - |
| UA01 | EUV 光刻的曝光波长是多少纳米？ | 资料不足 | ✓ | ✓ | 1 | 1.65s | - |
| UA02 | 我们公司去年因为设备故障损失了多少产能？ | 资料不足 | ✓ | ✓ | 1 | 1.6s | - |

## Failures

### KB03  用户问法和文档里的说法完全不一样，怎么提高命中率？
- answer_ok=False, tool_ok=True, steps=1, error=-
- tools: -
- answer: 可以通过使用Layout-aware解析和表格结构化技术来处理文档中的表格和图纸，同时结合版本metadata硬过滤确保引用的文档版本是最新的。此外，可以采用强制引用机制和拒答机制，防止模型编造工艺参数，并在检索层前置权限过滤。对于用户问法和文档说法不一致的情况，可以优化检索和生成过程，提高对不同工况上下文的区分能力，从而提高命中率。
- missing keywords: ['查询改写/改写/Multi-Query', 'HyDE/假设答案/假想答案']

### TK01  T-1001 工单现在是什么状态？
- answer_ok=False, tool_ok=True, steps=1, error=-
- tools: -
- answer: 资料不足
- missing keywords: ['open']

### TK02  T-1002 工单的优先级是什么？
- answer_ok=False, tool_ok=True, steps=1, error=-
- tools: -
- answer: 资料不足
- missing keywords: ['P2']

### TK03  T-9999 工单现在是什么状态？
- answer_ok=False, tool_ok=True, steps=1, error=-
- tools: -
- answer: 资料不足
- missing keywords: ['T-9999']

### TK04  T-1004 涉及哪个报警码，处理结果是什么？
- answer_ok=False, tool_ok=True, steps=1, error=-
- tools: -
- answer: 资料不足
- missing keywords: ['ALM-2087']

### CA01  某批次 24 片，良率 92.5%，良品多少片？
- answer_ok=False, tool_ok=True, steps=1, error=-
- tools: -
- answer: 该批次良品数量为 22 片。
- missing keywords: ['22.2']

### MX01  T-1001 涉及的报警应该怎么处理？
- answer_ok=False, tool_ok=True, steps=1, error=-
- tools: -
- answer: 资料不足
- missing keywords: ['真空泵/真空/抽气']

### MX02  T-1003 的批次良率是多少？如果 24 片，良品多少片？
- answer_ok=False, tool_ok=True, steps=1, error=-
- tools: -
- answer: 资料不足
- missing keywords: ['92.5', '22.2/22片/22 片/22']
