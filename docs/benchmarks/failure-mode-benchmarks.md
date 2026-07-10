# Inference Failure Mode Benchmarks

**Date:** July 10, 2026
**Model:** granite-3.2-sovereign (IBM Granite 3.2 2B, OpenVINO)
**Engine:** OVMS 2026.2.1
**Infrastructure:** Oberon, single-node OpenShift, RHEL CoreOS 9.8, K8s 1.35
**Replicas:** 8 OVMS pods (CPU, no GPU)
**SLO:** 5000ms p95

## 1. Cold Start

10 seconds idle, then 5 sequential requests.

| Metric | Value |
|--------|-------|
| Avg | 566ms |
| P95 | 743ms |
| SLO | WITHIN |
| GCL | no_action |

No cold start penalty observed. OVMS keeps the model loaded across idle periods. The first request (421ms) was faster than subsequent ones, indicating warm caches.

## 2. Mixed Prompt Lengths

15 concurrent requests: 10 short ("What is 2+2?", 10 tokens) and 5 long (200-word essay, 200 tokens).

| Prompt Type | Avg | P95 | Count |
|-------------|-----|-----|-------|
| Short | 700ms | 833ms | 10 |
| Long | 9,718ms | 12,150ms | 5 |
| Combined | 3,706ms | 12,150ms | 15 |
| SLO | BREACH (combined p95) | | |
| GCL | **scale committed** | | |

Long prompts dominate the p95. Short prompts are not significantly starved (700ms avg vs 605ms baseline), indicating OVMS handles mixed workloads without severe head-of-line blocking. The GCL correctly detects the combined breach and commits scale.

## 3. Large Input Context

3 sequential requests with ~1,669 prompt tokens, 30 max completion tokens.

| Request | Latency | Prompt Tokens | Completion Tokens |
|---------|---------|---------------|-------------------|
| 0 | 4,938ms | 1,669 | 30 |
| 1 | 6,082ms | 1,669 | 30 |
| 2 | 4,788ms | 1,669 | 22 |

| Metric | Value |
|--------|-------|
| Avg | 5,269ms |
| P95 | 6,082ms |
| SLO | BREACH |
| GCL | scale (rejected: low sample count confidence) |

Large input context scales linearly with prompt length on CPU. 1,669 tokens takes ~5 seconds even for short completions. This is a fundamental CPU inference characteristic, not a capacity problem. The GCL correctly identified the breach and proposed scale, but rejected due to low trajectory confidence from only 3 samples.

## 4. Token Throughput Saturation

5 concurrent requests, each generating 200 tokens.

| Metric | Value |
|--------|-------|
| Requests | 5 concurrent |
| Total tokens generated | 1,000 |
| Wall clock | 12.0s |
| Aggregate throughput | 83.2 tokens/sec |
| Avg latency | 9,522ms |
| P95 | 12,021ms |
| Peak | 12,021ms |
| SLO | BREACH |
| GCL | scale (rejected: confidence) |

At 5 concurrent 200-token generations, the CPU pool sustains 83.2 tokens/sec aggregate. Each individual request takes ~10 seconds. This is the CPU decode bottleneck: token-by-token generation on CPU cannot match GPU throughput.

## 5. Burst After Quiet

15 seconds idle, then 15 concurrent short requests.

| Metric | Value |
|--------|-------|
| Avg | 1,578ms |
| P95 | 1,793ms |
| Peak | 1,793ms |
| Errors | 0 |
| SLO | WITHIN |
| GCL | no_action |

No burst penalty. 15 concurrent requests after idle period show no latency degradation compared to the warm concurrency sweep (test 2 in the base benchmarks showed 2,036ms at c=15). OVMS handles burst traffic cleanly.

## 6. Error Handling

Mixed valid and invalid requests to verify OVMS error behavior.

| Request Type | Latency | Status | Behavior |
|---|---|---|---|
| Valid request | 493ms | 200 | Normal response |
| Empty messages array | 24ms | 400 | Fast rejection, clear error |
| Wrong model name | 7ms | 404 | Fast rejection |
| Zero max_tokens | 8ms | 400 | Fast rejection |

OVMS returns errors quickly (7-24ms) without tying up inference resources. Invalid requests do not impact concurrent valid requests.

## 7. Ramp-Up Stress

Increasing concurrency from 1 to 30 with short prompts.

| Concurrency | Avg | P95 | Peak | Errors | SLO |
|-------------|-----|-----|------|--------|-----|
| 1 | 860ms | 860ms | 860ms | 0 | WITHIN |
| 5 | 847ms | 1,000ms | 1,000ms | 0 | WITHIN |
| 10 | 1,147ms | 1,350ms | 1,350ms | 0 | WITHIN |
| 20 | 1,318ms | 1,962ms | 1,962ms | 0 | WITHIN |
| 30 | 1,795ms | 3,060ms | 3,062ms | 0 | WITHIN |

| GCL at c=30 | no_action (correct) |
|---|---|

Short-prompt inference remains within SLO even at 30 concurrent across 8 CPU replicas. Zero errors at all concurrency levels. Latency scales sub-linearly: 30x concurrency produces only 3.5x latency increase (860ms to 3,060ms), indicating effective load distribution across replicas.

## 8. GCL Decision Summary Across All Failure Modes

| Failure Mode | P95 | SLO | GCL Decision | Correct? |
|---|---|---|---|---|
| Cold start | 743ms | WITHIN | no_action | Yes |
| Mixed (combined) | 12,150ms | BREACH | **scale committed** | Yes |
| Large context | 6,082ms | BREACH | scale (rejected: low samples) | Yes (cautious) |
| Token saturation | 12,021ms | BREACH | scale (rejected: confidence) | Yes (cautious) |
| Burst after quiet | 1,793ms | WITHIN | no_action | Yes |
| Error handling | N/A | N/A | N/A | N/A |
| Ramp c=1 | 860ms | WITHIN | no_action | Yes |
| Ramp c=10 | 1,350ms | WITHIN | no_action | Yes |
| Ramp c=20 | 1,962ms | WITHIN | no_action | Yes |
| Ramp c=30 | 3,060ms | WITHIN | no_action | Yes |

## 9. Key Findings

1. **No cold start penalty.** OVMS keeps models loaded. First request after 10-15s idle shows no degradation.

2. **Short prompts scale well.** 30 concurrent short prompts across 8 replicas stay within SLO with zero errors and sub-linear latency growth.

3. **Long generation is the bottleneck.** 100+ token generation on CPU takes 5-12 seconds regardless of concurrency. This is a fundamental CPU decode limitation, not a capacity problem.

4. **Mixed workloads breach on the long tail.** Short prompts are not starved by concurrent long generation (700ms vs 605ms baseline), but the combined p95 is dominated by long requests.

5. **Large context input scales linearly.** 1,669 prompt tokens takes ~5 seconds on CPU. Context length is a first-order latency driver.

6. **Aggregate throughput: 83 tokens/sec.** At 5 concurrent 200-token generations across 8 CPU replicas. This is the ceiling for this hardware configuration.

7. **The GCL correctly distinguishes actionable breaches from noise.** Commits scale for genuine sustained breaches (mixed workload), commits no_action for within-SLO scenarios, and is cautious (rejects) when sample count is low.

8. **OVMS error handling is clean.** Invalid requests fail fast (7-24ms) without impacting concurrent valid requests.
