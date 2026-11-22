# Agentic RAG Evaluation Report

- started_at: 2026-11-22T14:37:19
- model: Qwen/Qwen3-8B | embedding: BAAI/bge-m3
- mode: agent | runs: 1 | tasks: 26

## Summary

| Metric | Value |
| --- | --- |
| Answer accuracy | 92.31% |
| Task success (answer + tools) | 92.31% |
| Tool selection | 100.00% |
| pass^1 | 92.31% |
| Avg steps | 2.15 |
| Avg latency | 7.78s |
| P95 latency | 12.43s |
| Errors | 0 |

## Per task

| ID | Question | Answer | Tool | Success | Steps | Latency | Tools called |
| --- | --- | --- | --- | --- | --- | --- | --- |
| KB01 | CoT 和 ReAct 的本质区别是什么？ | CoT 和 ReAct 的本质区别如下： 1. CoT 是纯推理链，而 ReAct  | ✓ | ✓ | 2 | 10.17s | search_kb |
| KB02 | Recall@k 已经很高了，为什么用户还是觉得答不准？ | Recall@k 高但用户仍觉得答不准的可能原因包括： 1. 链路的每一步是否正确（ | ✓ | ✓ | 2 | 7.97s | search_kb |
| KB03 | 用户问法和文档里的说法完全不一样，怎么提高命中率？ | 提高任务与文档匹配度的命中率，可以采取以下方法： 1. 使用查询改写技术，将用户口语 | ✓ | ✓ | 2 | 10.9s | search_kb |
| KB04 | 生产环境里怎么防止 Agent 陷入无限循环？ | 防止 Agent 陷入无限循环的方法包括： 1. 设置 `max_iteration | ✓ | ✓ | 2 | 9.87s | search_kb |
| KB05 | 长上下文窗口越来越大，是不是就不需要 RAG 了？ | 长上下文窗口和 RAG 是互补而非替代的关系。即使窗口较大，仍需通过 RAG 精准控 | ✗ | ✗ | 2 | 7.17s | search_kb |
| KB06 | 幻觉有哪些缓解手段？哪种最有效？ | 幻觉的缓解手段包括：1. RAG（将真实资料塞进上下文）；2. Function C | ✓ | ✓ | 2 | 8.78s | search_kb |
| KB07 | Transcript 和 Outcome 这两个概念的区别是什么？ | 1. Transcript 是 Agent 在对话中表达的内容，如'订单已创建'。  | ✓ | ✓ | 3 | 9.8s | search_kb, search_kb |
| KB08 | pass@k 和 pass^k 分别表示什么？ | 1. pass@k 表示 k 次尝试中至少 1 次成功的概率，适合 coding a | ✓ | ✓ | 2 | 6.64s | search_kb |
| KB09 | 四级 Ship Gate 是什么？ | 四级 Ship Gate 是模型升级上线的四个阶段，具体包括： 1. Offline | ✓ | ✓ | 2 | 9.27s | search_kb |
| KB10 | 做自动评分时，code-based 和 LLM judge 怎么分工？ | 1. code-based 负责检查技术性问题，如推荐的商品是否存在、价格是否符合预 | ✓ | ✓ | 2 | 9.47s | search_kb |
| KB11 | 最小可用 Benchmark 要多少个 task？怎么分配？ | 最小可用 Benchmark 需要 150 个 task，分配方法如下： 1. 50 | ✓ | ✓ | 2 | 12.43s | search_kb |
| KB12 | ALM-1042 报警的触发条件和处理步骤是什么？ | ALM-1042 报警的触发条件是：腔体压力偏离设定值超过 8% 且持续 3 秒以上 | ✓ | ✓ | 2 | 9.29s | search_kb |
| KB13 | SPC 控制图有哪些判异规则？ | SPC 控制图的判异规则包括： 1. 单点超出 ±3σ。 2. 连续 3 点中有 2 | ✓ | ✓ | 2 | 9.05s | search_kb |
| KB14 | APC 的三层分别负责什么？ | APC 的三层分别负责： 1. **FDC（故障检测与分类）**：从设备传感器数据实 | ✓ | ✓ | 2 | 8.39s | search_kb |
| KB15 | ALM-2087 报警应该怎么处理？ | 处理 ALM-2087 报警（射频反射功率过高）的步骤如下： 1. 先做匹配网络自动 | ✓ | ✓ | 2 | 6.95s | search_kb |
| TK01 | T-1001 工单现在是什么状态？ | 工单 T-1001 的状态是 open，优先级为 P1，由设备工程师负责。相关报警为 | ✓ | ✓ | 2 | 4.94s | lookup_ticket |
| TK02 | T-1002 工单的优先级是什么？ | 工单 T-1002 的优先级是 P2。 | ✓ | ✓ | 2 | 4.17s | lookup_ticket |
| TK03 | T-9999 工单现在是什么状态？ | 未找到工单 T-9999 的相关信息。 | ✓ | ✓ | 2 | 3.99s | lookup_ticket |
| TK04 | T-1004 涉及哪个报警码，处理结果是什么？ | 任务 T-1004 涉及的报警码是 ALM-2087，处理结果为：匹配网络重新调谐后 | ✓ | ✓ | 2 | 5.51s | lookup_ticket |
| CA01 | 某批次 24 片，良率 92.5%，良品多少片？ | 达到最大步数，未能完成。 | ✗ | ✗ | 3 | 10.93s | calculator |
| CA02 | 每片测试 45 秒，24 片需要多少分钟？ | 24 片测试需要 18 分钟。 | ✓ | ✓ | 2 | 4.35s | calculator |
| CA03 | 3 个腔体，每个 12 片，一共多少片？ | 三个腔体，每个12片，一共36片。 | ✓ | ✓ | 2 | 3.57s | calculator |
| MX01 | T-1001 涉及的报警应该怎么处理？ | 处理 ALM-1042 腔体压力异常的步骤如下： 1. 暂停当前批次（lot），记录 | ✓ | ✓ | 3 | 12.52s | lookup_ticket, search_kb |
| MX02 | T-1003 的批次良率是多少？如果 24 片，良品多少片？ | 批次良率为 92.5%，24 片中良品数量为 22 片（四舍五入） | ✓ | ✓ | 3 | 7.06s | lookup_ticket, calculator |
| UA01 | EUV 光刻的曝光波长是多少纳米？ | 资料不足 | ✓ | ✓ | 2 | 4.96s | search_kb |
| UA02 | 我们公司去年因为设备故障损失了多少产能？ | 资料不足 | ✓ | ✓ | 2 | 4.08s | search_kb |

## Failures

### KB05  长上下文窗口越来越大，是不是就不需要 RAG 了？
- answer_ok=False, tool_ok=True, steps=2, error=-
- tools: ['search_kb']
- answer: 长上下文窗口和 RAG 是互补而非替代的关系。即使窗口较大，仍需通过 RAG 精准控制上下文内容，以避免 Lost in the Middle 和上下文腐化问题。
- missing keywords: ['成本/费用/价格']

### CA01  某批次 24 片，良率 92.5%，良品多少片？
- answer_ok=False, tool_ok=True, steps=3, error=-
- tools: ['calculator']
- answer: 达到最大步数，未能完成。
- missing keywords: ['22.2']
