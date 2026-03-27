# run_insight_v3.py
from InsightEngine.agent import InsightAgent


def main():
    print("=== InsightEngineLC - V3 多节点工作流 ===")
    print("输入你的问题（例如：最近产品有哪些主要吐槽和风险？），输入 'exit' 退出。\n")

    agent = InsightAgent()

    while True:
        q = input("你：").strip()
        if not q:
            continue
        if q.lower() in {"exit", "quit"}:
            print("再见 👋")
            break

        state = agent.run(q)

        print("\n====== 【结构化字段预览】 ======")
        print("关键词：", state.keywords)
        print("情感分布：", state.sentiment_breakdown)
        if state.report:
            print("主要关注点：", state.report.main_concerns[:3])
        print("================================\n")

        print("====== 【Markdown 报告】 ======")
        print(state.markdown_report)
        print("================================\n")


if __name__ == "__main__":
    main()
