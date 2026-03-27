from InsightEngine.pipelines.insight_pipeline import (
    build_insight_pipeline,
    render_report_markdown,
)


def main():
    print("=== Mini Bettafish - InsightEngine V2 ===")
    print("输入你的问题（例如：最近用户对产品有哪些主要吐槽和风险？），输入 'exit' 退出。\n")

    pipeline = build_insight_pipeline()

    while True:
        user_input = input("你：").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("再见 👋")
            break

        report = pipeline.invoke({"question": user_input})
        md = render_report_markdown(report)

        print("\n========= 【舆情洞察报告】 =========\n")
        print(md)
        print("\n====================================\n")


if __name__ == "__main__":
    main()
