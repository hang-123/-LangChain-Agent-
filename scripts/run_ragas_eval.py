#!/usr/bin/env python3
"""RAGAS 自动化评估脚本 — BettaFish RAG 系统

评估 RAG 检索+生成质量，覆盖 4 个核心指标:
  - Context Precision  — 检索到的文档中有多少是真正相关的
  - Context Recall     — 应该检索到的相关文档，实际召回了多少
  - Faithfulness       — 生成的回答中有多少能从上下文中找到支撑
  - Answer Relevancy   — 回答是否紧扣问题

用法:
    python scripts/run_ragas_eval.py              # 单次评估
    python scripts/run_ragas_eval.py --compare     # 对比两次评估结果
    python scripts/run_ragas_eval.py --output logs/ragas/  # 指定输出目录

依赖:
    pip install ragas datasets langchain-openai
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


# ─── Golden Dataset ──────────────────────────────────────────────

GOLDEN_QA_PAIRS: list[dict[str, Any]] = [
    {
        "query": "字节跳动 后端开发工程师 面试准备",
        "expected_answer": "字节跳动后端面试通常包括算法题（LeetCode中等难度为主）、系统设计（分布式缓存、消息队列）、项目深挖（简历上的技术栈和架构决策）和基础知识（操作系统、网络、数据库）。推荐准备方向：1) 刷LeetCode Hot 100 2) 复习MySQL索引和事务 3) 准备一个系统设计案例（如设计一个短链接服务）",
    },
    {
        "query": "阿里巴巴 Java开发 技术栈要求",
        "expected_answer": "阿里巴巴Java开发岗位通常要求：掌握Java并发编程（线程池、锁机制、JUC包）、JVM调优（GC策略、内存模型）、Spring全家桶（Boot、Cloud、Security）、MySQL分库分表、Redis集群方案、消息队列（RocketMQ/Kafka）。加分项：熟悉阿里云产品、有开源项目贡献、了解DDD领域驱动设计。",
    },
    {
        "query": "腾讯 前端开发 React 面试题",
        "expected_answer": "腾讯前端面试重点考察：React核心原理（虚拟DOM、Fiber架构、Hooks实现机制）、性能优化（memo、useMemo、lazy loading）、状态管理方案选型（Redux vs Zustand vs Jotai）、CSS布局方案（Flexbox、Grid）、前端工程化（Webpack/Vite配置、CI/CD）。可能会有现场coding环节。",
    },
    {
        "query": "美团 数据开发 面试经验",
        "expected_answer": "美团数据开发面试通常分为：SQL编程（窗口函数、复杂JOIN）、数据仓库建模（星型/雪花模型、维度建模）、大数据组件（Hadoop生态、Spark调优、Flink实时计算）、数据治理和质量管理。行为面试会考察项目中的难点和解决方案。",
    },
    {
        "query": "拼多多 算法工程师 面试流程",
        "expected_answer": "拼多多算法面试一般包括：1) 手撕代码（中等难度算法题）2) 机器学习基础（LR、决策树、XGBoost原理）3) 业务场景题（推荐系统冷启动、A/B测试设计）4) 项目经历和论文深挖。技术面通常3-4轮，最后可能有HR面谈薪资和入职时间。",
    },
    {
        "query": "字节跳动 产品经理 面试准备",
        "expected_answer": "字节产品经理面试侧重：产品sense（竞品分析、用户研究）、数据分析能力（SQL取数、指标拆解）、项目推动能力（跨团队协作案例）、逻辑思维（估算题、case题）。常见的面试题包括'你最喜欢的产品是什么'和'设计一个新功能'。",
    },
    {
        "query": "百度 自动驾驶感知算法 岗位要求",
        "expected_answer": "百度自动驾驶感知算法岗要求：SLAM算法、3D点云处理（PCL、Open3D）、深度学习模型部署（TensorRT、ONNX）、多传感器融合（相机+激光雷达+毫米波雷达）。发表过顶会论文（CVPR/ICCV/ECCV）是重要加分项。",
    },
    {
        "query": "华为 鸿蒙开发 技术面试",
        "expected_answer": "华为鸿蒙开发面试涉及：ArkTS语言特性、组件化开发（ArkUI框架）、分布式软总线、一次开发多端部署。底层能力考察包括操作系统基础、跨进程通信、设备驱动适配。华为注重候选人的学习能力和技术钻研深度。",
    },
    {
        "query": "小红书 推荐系统 面试经验",
        "expected_answer": "小红书推荐系统面试重点：推荐算法全链路（召回→粗排→精排→重排）、特征工程（用户画像、内容理解）、模型优化（冷启动、多样性、时效性）、A/B实验平台设计。对内容理解和多模态有一定要求。",
    },
    {
        "query": "快手 短视频推荐 C++开发",
        "expected_answer": "快手C++开发面试主要考：C++11/14/17特性（智能指针、移动语义、lambda）、STL源码级理解（vector扩容、map底层）、多线程编程（锁、条件变量、无锁队列）、内存管理（内存池、RAII）、Linux系统编程（epoll、信号处理）。",
    },
]


# ─── RAGAS Evaluation ────────────────────────────────────────────


async def run_single_query(
    query: str,
    *,
    top_k: int = 6,
) -> dict[str, Any]:
    """Execute a single RAG query and return results for RAGAS."""
    from api.core.rag_store import build_rag_store, search_rag_sources

    profile = {}  # Empty profile for pure RAG eval
    hits, failures = await search_rag_sources(
        query=query, profile=profile, top_k=top_k
    )

    contexts = [hit.chunk.text for hit in hits]
    urls = [hit.chunk.url for hit in hits]
    scores = [hit.score for hit in hits]

    return {
        "query": query,
        "contexts": contexts,
        "urls": urls,
        "retrieval_scores": scores,
        "failures": failures,
        "hit_count": len(hits),
    }


async def run_ragas_eval(
    qa_pairs: list[dict[str, Any]],
    *,
    top_k: int = 6,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Run full RAGAS evaluation on a set of QA pairs.

    Returns evaluation report with 4 metrics.
    """
    print(f"🔍 开始 RAGAS 评估: {len(qa_pairs)} 组 Query...")
    print()

    retrieval_results: list[dict[str, Any]] = []
    ragas_inputs: list[dict[str, str | list[str]]] = []

    for i, qa in enumerate(qa_pairs, 1):
        query = qa["query"]
        expected = qa.get("expected_answer", "")

        print(f"  [{i}/{len(qa_pairs)}] {query[:50]}...")
        result = await run_single_query(query, top_k=top_k)
        retrieval_results.append(result)

        contexts = result["contexts"]
        if not contexts:
            print(f"         ⚠ 无检索结果")
            continue

        # Generate answer using LLM (faithfulness check needs this)
        answer = await _generate_answer(query, contexts)

        ragas_inputs.append({
            "question": query,
            "answer": answer,
            "contexts": contexts,
            "ground_truth": expected,
        })

    print()
    print(f"📊 检索统计: 平均命中 {sum(r['hit_count'] for r in retrieval_results) / len(retrieval_results):.1f} 条/query")

    # RAGAS metrics
    ragas_scores: dict[str, float] = {}
    try:
        ragas_scores = await _compute_ragas_metrics(ragas_inputs)
    except Exception as exc:
        print(f"  ⚠ RAGAS 指标计算失败: {exc}")

    # Build report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_queries": len(qa_pairs),
        "queries_with_results": len(ragas_inputs),
        "avg_hit_count": (
            sum(r["hit_count"] for r in retrieval_results) / len(retrieval_results)
            if retrieval_results else 0
        ),
        "ragas_metrics": ragas_scores,
        "per_query": [
            {
                "query": r["query"],
                "hit_count": r["hit_count"],
                "top_score": max(r["retrieval_scores"]) if r["retrieval_scores"] else 0,
                "urls": r["urls"][:3],
            }
            for r in retrieval_results
        ],
    }

    # Print summary
    print()
    print("=" * 60)
    print("  RAGAS 评估报告")
    print("=" * 60)
    for metric, value in ragas_scores.items():
        print(f"  {metric:<25s}: {value:.4f}")
    print("=" * 60)

    # Save report
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(
            output_dir,
            f"ragas_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n📁 报告已保存: {report_path}")

    return report


async def _generate_answer(query: str, contexts: list[str]) -> str:
    """Generate an answer from retrieved contexts using the configured LLM."""
    if not contexts:
        return ""

    try:
        from api.core.llm import get_chat_model

        context_text = "\n\n---\n\n".join(
            f"[{i}] {ctx[:500]}" for i, ctx in enumerate(contexts[:5])
        )
        prompt = f"""Based on the following retrieved information, answer the query concisely.

Query: {query}

Retrieved Contexts:
{context_text}

Provide a comprehensive but concise answer. Only use facts from the contexts.
If the contexts don't contain enough information, say so honestly.

Answer:"""

        model = get_chat_model(temperature=0.1)
        response = await model.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)
    except Exception:
        return ""


async def _compute_ragas_metrics(
    eval_data: list[dict[str, str | list[str]]],
) -> dict[str, float]:
    """Compute RAGAS metrics from evaluation data.

    Requires: pip install ragas datasets
    """
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            context_precision,
            context_recall,
            faithfulness,
            answer_relevancy,
        )
    except ImportError:
        print("  ⚠ ragas/datasets 未安装，请先 pip install ragas datasets")
        return {}

    if not eval_data:
        return {}

    # Convert to RAGAS format
    ds = Dataset.from_list(eval_data)  # type: ignore

    try:
        scores = evaluate(
            ds,
            metrics=[
                context_precision,
                context_recall,
                faithfulness,
                answer_relevancy,
            ],
        )
        return {
            "context_precision": float(scores.get("context_precision", 0)),
            "context_recall": float(scores.get("context_recall", 0)),
            "faithfulness": float(scores.get("faithfulness", 0)),
            "answer_relevancy": float(scores.get("answer_relevancy", 0)),
        }
    except Exception as exc:
        print(f"  RAGAS evaluate 异常: {exc}")
        return {}


# ─── Compare Mode ────────────────────────────────────────────────


def compare_reports(report_paths: list[str]) -> str:
    """Compare two RAGAS evaluation reports and generate a diff."""
    reports = []
    for path in report_paths:
        with open(path, encoding="utf-8") as f:
            reports.append(json.load(f))

    lines = ["# RAGAS 评估对比报告\n"]
    lines.append(f"基线: {reports[0].get('timestamp', 'N/A')}")
    lines.append(f"对比: {reports[1].get('timestamp', 'N/A')}")
    lines.append("")

    metrics0 = reports[0].get("ragas_metrics", {})
    metrics1 = reports[1].get("ragas_metrics", {})

    lines.append("| 指标 | 基线 | 对比 | 变化 |")
    lines.append("|------|------|------|------|")
    for metric in ["context_precision", "context_recall", "faithfulness", "answer_relevancy"]:
        v0 = metrics0.get(metric, 0)
        v1 = metrics1.get(metric, 0)
        delta = v1 - v0
        direction = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        lines.append(f"| {metric} | {v0:.4f} | {v1:.4f} | {direction} {delta:+.4f} |")

    report = "\n".join(lines)
    print(report)
    return report


# ─── CLI ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="RAGAS RAG 评估")
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("BASELINE", "TREATMENT"),
        help="对比两个评估报告 JSON",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="logs/ragas",
        help="输出目录 (默认: logs/ragas)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=6,
        help="检索返回数 (默认: 6)",
    )
    args = parser.parse_args()

    if args.compare:
        compare_reports(args.compare)
        return

    asyncio.run(
        run_ragas_eval(
            GOLDEN_QA_PAIRS,
            top_k=args.top_k,
            output_dir=args.output,
        )
    )


if __name__ == "__main__":
    main()
