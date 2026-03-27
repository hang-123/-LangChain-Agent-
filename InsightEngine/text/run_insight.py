from InsightEngine.agent import build_insight_agent

def main():
    print("=== Mini Bettafish (Insight Agent) ===")
    print("输入你的问题（例如：最近用户最关心什么？），输入 'exit' 退出。\n")

    agent = build_insight_agent()

    while True:
        user_input = input("你：").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("再见 👋")
            break

        # 关键：LangChain 1.0 的 agent 接口用 messages 作为状态
        result = agent.invoke(
            {
                "messages": [
                    {"role": "user", "content": user_input}
                ]
            }
        )

        # result 是整个状态 dict，我们拿最后一条消息出来
        last_msg = result["messages"][-1]
        content = last_msg.content if hasattr(last_msg, "content") else last_msg["content"]

        print("\n【分析报告】")
        print(content)
        print("\n" + "-" * 60 + "\n")


if __name__ == "__main__":
    main()