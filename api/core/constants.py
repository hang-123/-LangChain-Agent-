from __future__ import annotations

from api.core.settings import get_settings


MAX_RETRIES = get_settings().max_retries

NODE_START_MESSAGES = {
    "IntentRouterNode": "🧭 正在识别任务意图并进行确定性分流...",
    "SearchAgent": "🔍 正在全网检索最新 JD、薪资线索和真实面经证据...",
    "QueryAgent": "🧠 正在提取核心考察点、技术栈与面试画像...",
    "InsightAgent": "🎯 正在诊断候选人风险点并生成面试官追问...",
    "QualityGate": "🛡️ 正在执行成稿前质量闸门检查...",
    "ReportAgent": "📝 正在基于真实 context 撰写专属求职研究报告...",
    "ReviewAgent": "⚖️ 正在进行质量审查与自纠错判定...",
}
