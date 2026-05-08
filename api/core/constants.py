from __future__ import annotations

from api.core.settings import get_settings


MAX_RETRIES = get_settings().max_retries

# ── Phase 2: Forbidden phrases for Gate ──
FORBIDDEN_PHRASES = [
    "精通", "擅长", "一定过筛", "保证录取", "百分百匹配",
    "完美候选人", "顶级", "绝对优势", "无可挑剔",
]

# ── Phase 2: Archetype keywords for deterministic detection ──
ARCHETYPE_KEYWORDS: dict[str, list[str]] = {
    "AI Platform / LLMOps": ["evals", "production ai", "observability", "llmops", "mlops", "model serving", "inference", "ai infrastructure", "向量数据库", "模型部署"],
    "Agentic / Automation": ["multi-agent", "agent", "automation", "workflow", "tool use", "function calling", "agentic", "编排", "智能体"],
    "Technical AI PM": ["ai product", "ai pm", "product manager", "technical product", "产品经理", "需求分析"],
    "AI Solutions Architect": ["solutions architect", "solution architecture", "presales", "架构师", "解决方案"],
    "AI Forward Deployed": ["forward deployed", "customer success", "integration", "implementation", "客户成功", "交付"],
    "AI Transformation": ["transformation", "change management", "ai strategy", "digital transformation", "数字化转型", "ai转型"],
}

# ── Phase 2: Tailor keywords for resume tailoring ──
TAILOR_KEYWORDS = [
    "Java", "Go", "Python", "C++", "Redis", "MySQL", "Kafka",
    "Spring", "Spring Boot", "HTTP", "RPC", "微服务", "分布式",
    "高并发", "系统设计", "Docker", "Kubernetes", "CI/CD", "AWS",
    "Azure", "GCP", "TensorFlow", "PyTorch", "LLM", "RAG",
]

# ── Phase 2 intents ──
PHASE2_INTENTS = [
    "general", "tech_coding", "salary_culture", "match",
    "resume_tailor", "interview_prep", "offer_compare", "profile_bootstrap",
]

# ── Phase 2 workflows ──
WORKFLOW_IDS = [
    "wf_match_v2",
    "wf_resume_tailor_v2",
    "wf_interview_prep_v2",
    "wf_profile_bootstrap",
    "wf_offer_compare",
    "wf_application_followup_v1",
]

NODE_START_MESSAGES = {
    # Phase 2 Agent nodes
    "Supervisor": "正在识别意图并选择工作流...",
    "AnalysisAgent": "正在进行深度分析与风险评估...",
    "ReportAgent": "正在生成结构化报告...",
    # Phase 2 Tool nodes
    "SearchOrchestrator": "正在全网检索 JD、面经和公司画像...",
    "JobAnalyzer": "正在分析岗位需求与合法性...",
    "MatchingEngine": "正在执行候选人-岗位匹配...",
    "ResumeTailor": "正在生成简历定制建议...",
    "ResumeParser": "正在解析简历文件...",
    "InterviewCoach": "正在生成面试准备材料...",
    "OfferEvaluator": "正在对比多个 offer...",
    # Phase 2 Gate
    "Gate": "正在执行质量闸门检查...",
    # Legacy (Phase 1 compatibility)
    "IntentRouterNode": "正在识别任务意图并进行确定性分流...",
    "SearchAgent": "正在全网检索最新 JD、薪资线索和真实面经证据...",
    "JobIntelligenceAgent": "正在融合外部证据生成岗位快照与证据包...",
    "MatchingAgent": "正在基于候选人画像与岗位快照进行匹配分析...",
    "ResumeTailorAgent": "正在基于匹配结果生成简历定制计划与事实校验...",
    "QueryAgent": "正在提取核心考察点、技术栈与面试画像...",
    "InsightAgent": "正在诊断候选人风险点并生成面试官追问...",
    "QualityGate": "正在执行成稿前质量闸门检查...",
    "ReviewAgent": "正在进行质量审查与自纠错判定...",
    "ArchetypeDetector": "正在检测岗位原型分类...",
    "LegitimacyScorer": "正在评估岗位合法性...",
    "OfferEvaluator": "正在对比多个 offer...",
    "MemoryRetrievalNode": "正在加载历史记忆...",
}
