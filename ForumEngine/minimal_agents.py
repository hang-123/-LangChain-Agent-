from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Iterable, List, Tuple
from urllib import error, request


SMALL_TALK_EXACT = {
    "你好",
    "您好",
    "hi",
    "hello",
    "嗨",
    "在吗",
    "在不在",
    "早上好",
    "中午好",
    "下午好",
    "晚上好",
    "谢谢",
    "感谢",
}

CAREER_KEYWORDS = {
    "实习",
    "秋招",
    "春招",
    "校招",
    "求职",
    "岗位",
    "公司",
    "面试",
    "简历",
    "投递",
    "jd",
    "后端",
    "前端",
    "平台",
    "数据",
    "算法",
    "开发",
    "准备",
    "offer",
}


def detect_query_mode(query: str) -> str:
    text = query.strip().lower()
    compact = text.replace(" ", "")
    if compact in SMALL_TALK_EXACT:
        return "smalltalk"
    if any(keyword in compact for keyword in CAREER_KEYWORDS):
        return "career"
    if len(compact) <= 6:
        return "smalltalk"
    return "career"


def build_smalltalk_reply(query: str) -> str:
    text = query.strip()
    normalized = text.lower().replace(" ", "")
    if normalized in {"你好", "您好", "hi", "hello", "嗨"}:
        return "你好，我在。你可以直接告诉我目标岗位、公司，或者你想准备的面试方向。"
    if normalized in {"在吗", "在不在"}:
        return "在。你可以直接输入岗位、公司、面试题准备目标，我会按求职研究助手的模式帮你整理。"
    if normalized in {"谢谢", "感谢"}:
        return "不客气。你可以继续发岗位、公司或面试准备问题。"
    return "我在。你可以直接说岗位、公司、实习方向，或者你想准备的面试问题。"


def _extract_company_and_role(query: str) -> Tuple[str, str]:
    text = query.strip()
    company = "目标公司"
    role = "目标岗位"

    company_markers = ["字节", "阿里", "腾讯", "小红书", "美团", "京东", "百度", "华为", "快手", "滴滴"]
    role_markers = ["后端", "平台", "数据", "算法", "测试", "客户端", "前端", "运维", "SRE", "开发"]

    for marker in company_markers:
        if marker in text:
            company = marker
            break

    for marker in role_markers:
        if marker in text:
            role = marker
            break

    return company, role


def _skills_for_role(role: str) -> List[str]:
    if "后端" in role or "开发" in role:
        return ["Python 或 Java 基础", "数据库与 SQL", "缓存、消息队列、接口设计", "稳定性与性能优化"]
    if "平台" in role or "SRE" in role or "运维" in role:
        return ["Linux 与网络基础", "监控告警与自动化", "容器与云平台", "稳定性治理"]
    if "数据" in role:
        return ["SQL 与数据建模", "ETL/数据链路", "Python", "指标体系与数据质量"]
    if "前端" in role or "客户端" in role:
        return ["JavaScript/TypeScript", "框架基础", "性能优化", "交互与工程化"]
    return ["计算机基础", "项目表达", "岗位相关技术栈", "沟通协作"]


@dataclass
class MinimalAgentResult:
    report_markdown: str
    metadata: dict = field(default_factory=dict)


def _detail_config(template_id: str | None) -> dict:
    template = (template_id or "default").strip()
    if template == "executive":
        return {
            "template_id": "executive",
            "label": "简洁",
            "list_limit": 2,
            "report_lines": "brief",
            "summary_instruction": "Keep the output concise. Prefer 2 short bullets per section.",
        }
    if template == "analysis":
        return {
            "template_id": "analysis",
            "label": "详细",
            "list_limit": 5,
            "report_lines": "detailed",
            "summary_instruction": "Provide richer detail. Prefer 4 to 5 bullets per section when useful.",
        }
    return {
        "template_id": "default",
        "label": "标准",
        "list_limit": 3,
        "report_lines": "standard",
        "summary_instruction": "Keep a balanced level of detail. Prefer 3 bullets per section.",
    }


class MinimalLLMClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("QUERY_ENGINE_API_KEY", "").strip()
        self.base_url = os.getenv("QUERY_ENGINE_BASE_URL", "").strip()
        self.model_name = os.getenv("QUERY_ENGINE_MODEL_NAME", "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and self.base_url and self.model_name)

    def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        text = self.chat_text(system_prompt, user_prompt)
        return _extract_json_block(text)

    def chat_text(self, system_prompt: str, user_prompt: str) -> str:
        if not self.enabled:
            raise RuntimeError("LLM client is not configured.")

        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model_name,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=60) as response:
                response_body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"LLM HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"LLM connection failed: {exc}") from exc

        data = json.loads(response_body)
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"LLM response missing choices: {data}")

        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
            )
        raise RuntimeError(f"LLM response missing message content: {data}")


def _extract_json_block(text: str) -> dict:
    content = text.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if len(lines) >= 3:
            content = "\n".join(lines[1:-1]).strip()
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"JSON block not found in model output: {text}")
    return json.loads(content[start : end + 1])


class MinimalQueryAgent:
    def __init__(self) -> None:
        self.llm = MinimalLLMClient()

    def run(
        self,
        query: str,
        template_id: str | None = None,
        save_report: bool = True,
    ) -> MinimalAgentResult:
        detail_cfg = _detail_config(template_id)
        if self.llm.enabled:
            try:
                profile = self._analyze_with_llm(query, detail_cfg)
                profile["generation_mode"] = "llm"
                profile["detail_level"] = detail_cfg["label"]
                markdown = self._format_profile(profile, detail_cfg)
                return MinimalAgentResult(report_markdown=markdown, metadata=profile)
            except Exception as exc:
                fallback = self._build_rule_based_profile(query, detail_cfg)
                fallback["llm_error"] = str(exc)
                fallback["generation_mode"] = "fallback"
                fallback["detail_level"] = detail_cfg["label"]
                return MinimalAgentResult(
                    report_markdown=self._format_profile(fallback, detail_cfg),
                    metadata=fallback,
                )

        profile = self._build_rule_based_profile(query, detail_cfg)
        profile["generation_mode"] = "fallback"
        profile["detail_level"] = detail_cfg["label"]
        return MinimalAgentResult(
            report_markdown=self._format_profile(profile, detail_cfg),
            metadata=profile,
        )

    def _analyze_with_llm(self, query: str, detail_cfg: dict) -> dict:
        system_prompt = (
            "You are a career research analyst. "
            "Extract structured intent from a candidate query. "
            "Return JSON only with keys: company, role, candidate_goal, focus_points, likely_questions, prep_actions."
        )
        user_prompt = (
            f"Candidate query: {query}\n"
            "Requirements:\n"
            "- company and role should be short strings\n"
            f"- focus_points, likely_questions, prep_actions should each contain 2 to {detail_cfg['list_limit']} Chinese bullet-style strings\n"
            "- if information is missing, infer conservatively from the query\n"
            f"- {detail_cfg['summary_instruction']}\n"
            "- output valid JSON only"
        )
        profile = self.llm.chat_json(system_prompt, user_prompt)
        return {
            "company": str(profile.get("company") or "目标公司"),
            "role": str(profile.get("role") or "目标岗位"),
            "candidate_goal": str(profile.get("candidate_goal") or query),
            "focus_points": _normalize_string_list(profile.get("focus_points"), detail_cfg["list_limit"]),
            "likely_questions": _normalize_string_list(profile.get("likely_questions"), detail_cfg["list_limit"]),
            "prep_actions": _normalize_string_list(profile.get("prep_actions"), detail_cfg["list_limit"]),
        }

    def _build_rule_based_profile(self, query: str, detail_cfg: dict) -> dict:
        company, role = _extract_company_and_role(query)
        core_skills = _skills_for_role(role)
        return {
            "company": company,
            "role": role,
            "candidate_goal": query,
            "focus_points": [
                f"{role} 岗位通常重视工程基础、项目表达和实际落地能力。",
                f"如果目标公司是 {company}，面试中通常会关注业务理解和岗位匹配动机。",
                *core_skills[:3],
            ][: detail_cfg["list_limit"]],
            "likely_questions": [
                "为什么选择这个岗位和这家公司？",
                "你最匹配这个岗位的项目经历是什么？",
                "如果重构你做过的一个模块，你会如何权衡性能、复杂度和可维护性？",
            ][: detail_cfg["list_limit"]],
            "prep_actions": [
                "准备 2 个最能体现岗位匹配度的项目案例。",
                "把项目整理成 STAR 或 背景-目标-行动-结果-反思 结构。",
                "针对公司业务和岗位技术栈准备 3 个高质量反问。",
            ][: detail_cfg["list_limit"]],
        }

    def _format_profile(self, profile: dict, detail_cfg: dict) -> str:
        markdown = "\n".join(
            [
                f"## 目标画像",
                f"- 公司线索：{profile['company']}",
                f"- 岗位线索：{profile['role']}",
                f"- 候选人目标：{profile['candidate_goal']}",
                f"- 输出等级：{detail_cfg['label']}",
                "",
                "## 岗位关键信息提炼",
                *(f"- {item}" for item in profile["focus_points"]),
                "",
                "## 高概率追问",
                *(f"- {item}" for item in profile["likely_questions"]),
                "",
                "## 建议先做的准备动作",
                *(f"- {item}" for item in profile["prep_actions"]),
            ]
        )
        if profile.get("llm_error"):
            markdown += (
                "\n\n> 注：本次结果已回退到本地规则模式，"
                f"原因：{profile['llm_error']}"
            )
        return markdown


class MinimalInsightAgent:
    def __init__(self) -> None:
        self.llm = MinimalLLMClient()

    def run(
        self,
        query: str,
        query_profile: dict | None = None,
        template_id: str | None = None,
        memory_context: str | None = None,
    ) -> MinimalAgentResult:
        detail_cfg = _detail_config(template_id)
        profile = query_profile or {}
        company = str(profile.get("company") or _extract_company_and_role(query)[0])
        role = str(profile.get("role") or _extract_company_and_role(query)[1])

        if self.llm.enabled:
            try:
                insight = self._analyze_with_llm(
                    query,
                    company,
                    role,
                    profile,
                    detail_cfg,
                    memory_context=memory_context,
                )
                if memory_context:
                    insight["memory_context_used"] = True
                insight["generation_mode"] = "llm"
                insight["detail_level"] = detail_cfg["label"]
                return MinimalAgentResult(
                    report_markdown=self._format_insight(insight, detail_cfg),
                    metadata=insight,
                )
            except Exception as exc:
                fallback = self._build_rule_based_insight(query, company, role, profile, detail_cfg)
                fallback["llm_error"] = str(exc)
                if memory_context:
                    fallback["memory_context_used"] = True
                fallback["generation_mode"] = "fallback"
                fallback["detail_level"] = detail_cfg["label"]
                return MinimalAgentResult(
                    report_markdown=self._format_insight(fallback, detail_cfg),
                    metadata=fallback,
                )

        fallback = self._build_rule_based_insight(query, company, role, profile, detail_cfg)
        if memory_context:
            fallback["memory_context_used"] = True
        fallback["generation_mode"] = "fallback"
        fallback["detail_level"] = detail_cfg["label"]
        return MinimalAgentResult(
            report_markdown=self._format_insight(fallback, detail_cfg),
            metadata=fallback,
        )

    def _analyze_with_llm(
        self,
        query: str,
        company: str,
        role: str,
        query_profile: dict,
        detail_cfg: dict,
        memory_context: str | None = None,
    ) -> dict:
        system_prompt = (
            "You are an interview preparation strategist. "
            "Given a candidate goal and upstream query analysis, produce structured interview-prep guidance. "
            "Return JSON only with keys: candidate_risks, prep_strategy, project_angles, interviewer_focus."
        )
        user_prompt = (
            f"Candidate query: {query}\n"
            f"Company: {company}\n"
            f"Role: {role}\n"
            f"Upstream profile: {json.dumps(query_profile, ensure_ascii=False)}\n"
            f"Reference memory: {memory_context or 'None'}\n"
            "Requirements:\n"
            f"- each field should be a list of 2 to {detail_cfg['list_limit']} Chinese strings\n"
            "- candidate_risks: likely weak spots or missing preparation\n"
            "- prep_strategy: concrete preparation actions\n"
            "- project_angles: how to present project experience\n"
            "- interviewer_focus: what interviewers will likely probe\n"
            "- prioritize the current query over reference memory\n"
            f"- {detail_cfg['summary_instruction']}\n"
            "- output valid JSON only"
        )
        payload = self.llm.chat_json(system_prompt, user_prompt)
        return {
            "company": company,
            "role": role,
            "candidate_risks": _normalize_string_list(payload.get("candidate_risks"), detail_cfg["list_limit"]),
            "prep_strategy": _normalize_string_list(payload.get("prep_strategy"), detail_cfg["list_limit"]),
            "project_angles": _normalize_string_list(payload.get("project_angles"), detail_cfg["list_limit"]),
            "interviewer_focus": _normalize_string_list(payload.get("interviewer_focus"), detail_cfg["list_limit"]),
        }

    def _build_rule_based_insight(
        self,
        query: str,
        company: str,
        role: str,
        query_profile: dict,
        detail_cfg: dict,
    ) -> dict:
        focus_points = _normalize_string_list(query_profile.get("focus_points"), detail_cfg["list_limit"])[:2]
        return {
            "company": company,
            "role": role,
            "candidate_risks": [
                f"{role} 场景下如果没有准备可量化项目成果，容易在追问时显得空泛。",
                f"如果对 {company} 的业务和岗位动机解释不具体，匹配度会被打折。",
                "如果项目回答只讲做了什么，不讲取舍与复盘，容易被继续深挖。",
            ][: detail_cfg["list_limit"]],
            "prep_strategy": [
                *(focus_points or ["优先准备与岗位最相关的 2 个技术点。"]),
                "准备一版 60 秒回答和一版 3 分钟项目展开稿。",
                "针对岗位关键词建立自己的问答索引。",
            ][: detail_cfg["list_limit"]],
            "project_angles": [
                "优先讲你负责过的核心模块，而不是泛泛介绍整个项目。",
                "每个案例至少准备一个技术难点、一个权衡决策、一个结果指标。",
                "回答时把行动、结果和复盘串起来，减少流水账叙述。",
            ][: detail_cfg["list_limit"]],
            "interviewer_focus": [
                "项目中你的真实职责与边界是什么？",
                "为什么这样设计，而不是另一种方案？",
                "上线后如何看待性能、稳定性和可维护性？",
            ][: detail_cfg["list_limit"]],
        }

    def _format_insight(self, insight: dict, detail_cfg: dict) -> str:
        markdown = "\n".join(
            [
                "## 候选人洞察",
                f"- 输出等级：{detail_cfg['label']}",
                *(f"- {item}" for item in insight["candidate_risks"]),
                "",
                "## 准备策略",
                *(f"- {item}" for item in insight["prep_strategy"]),
                "",
                "## 面试官高频关注点",
                *(f"- {item}" for item in insight["interviewer_focus"]),
            ]
        )
        if insight.get("llm_error"):
            markdown += (
                "\n\n> 注：本次洞察已回退到本地规则模式，"
                f"原因：{insight['llm_error']}"
            )
        return markdown


class MinimalReportAgent:
    def __init__(self) -> None:
        self.llm = MinimalLLMClient()

    def run(
        self,
        query: str,
        sources: Iterable[Tuple[str, str]],
        template_id: str | None = None,
        save_report: bool = True,
        memory_context: str | None = None,
    ) -> MinimalAgentResult:
        detail_cfg = _detail_config(template_id)
        company, role = _extract_company_and_role(query)
        sections = []
        for label, content in sources:
            sections.append(f"### {label}\n\n{content}")
        compiled_sources = "\n\n".join(sections)

        template_label = {
            "executive": "面试速览版",
            "analysis": "深度研究版",
        }.get(template_id or "default", "求职行动版")

        if self.llm.enabled:
            try:
                markdown = self._generate_with_llm(
                    query,
                    template_label,
                    compiled_sources,
                    detail_cfg,
                    memory_context=memory_context,
                )
                return MinimalAgentResult(
                    report_markdown=markdown,
                    metadata={
                        "generation_mode": "llm",
                        "detail_level": detail_cfg["label"],
                        "memory_context_used": bool(memory_context),
                    },
                )
            except Exception as exc:
                fallback_markdown = self._build_fallback_markdown(
                    query,
                    company,
                    role,
                    template_label,
                    compiled_sources,
                    detail_cfg,
                    llm_error=str(exc),
                )
                return MinimalAgentResult(
                    report_markdown=fallback_markdown,
                    metadata={
                        "llm_error": str(exc),
                        "generation_mode": "fallback",
                        "detail_level": detail_cfg["label"],
                        "memory_context_used": bool(memory_context),
                    },
                )

        markdown = self._build_fallback_markdown(
            query,
            company,
            role,
            template_label,
            compiled_sources,
            detail_cfg,
        )
        return MinimalAgentResult(
            report_markdown=markdown,
            metadata={
                "generation_mode": "fallback",
                "detail_level": detail_cfg["label"],
                "memory_context_used": bool(memory_context),
            },
        )

    def _generate_with_llm(
        self,
        query: str,
        template_label: str,
        compiled_sources: str,
        detail_cfg: dict,
        memory_context: str | None = None,
    ) -> str:
        system_prompt = (
            "You are a senior career coach and interview strategist. "
            "Write a Chinese markdown report for internship/job preparation. "
            "Use concrete, concise, high-signal language. "
            "Sections must be: "
            "## 一、岗位与公司概览 "
            "## 二、岗位能力要求拆解 "
            "## 三、潜在面试问题预测 "
            "## 四、回答准备建议 "
            "## 五、候选人行动清单 "
            "Do not mention that you are an AI. "
        )
        user_prompt = (
            f"用户问题：{query}\n"
            f"报告模板：{template_label}\n"
            f"输出等级：{detail_cfg['label']}\n"
            f"参考历史：{memory_context or 'None'}\n"
            "请基于下面的中间结果，生成一份自然、具体、适合面试准备的中文 Markdown 报告。\n"
            "如果参考历史与当前问题冲突，请以当前问题为准。\n"
            f"篇幅要求：{detail_cfg['summary_instruction']}\n"
            "中间结果如下：\n"
            f"{compiled_sources}"
        )
        text = self.llm.chat_text(system_prompt, user_prompt).strip()
        if not text.startswith("# "):
            text = f"# {query} 求职研究报告\n\n{text}"
        return text

    def _build_fallback_markdown(
        self,
        query: str,
        company: str,
        role: str,
        template_label: str,
        compiled_sources: str,
        detail_cfg: dict,
        llm_error: str | None = None,
    ) -> str:
        question_limit = 2 if detail_cfg["template_id"] == "executive" else 3 if detail_cfg["template_id"] == "default" else 4
        markdown = "\n".join(
            [
                f"# {query} 求职研究报告",
                "",
                f"> 模板：{template_label}",
                f"> 输出等级：{detail_cfg['label']}",
                "",
                "## 一、岗位与公司概览",
                f"- 目标公司：{company}",
                f"- 目标岗位：{role}",
                "- 建议围绕岗位职责、技术栈、业务背景和面试准备四个维度展开。",
                "",
                "## 二、岗位能力要求拆解",
                f"- {role} 类岗位通常要求候选人具备扎实基础、工程实现能力和良好的项目表达。",
                "- 面试准备时，优先把简历项目映射到岗位 JD 中反复出现的关键词。",
                "",
                "## 三、潜在面试问题预测",
                "- 你最匹配这个岗位的项目经历是什么？",
                "- 你如何设计并优化一个关键模块？",
                *(
                    ["- 面对线上故障、性能瓶颈或需求变化时，你会怎么处理？"]
                    if question_limit >= 3
                    else []
                ),
                *(
                    ["- 如果重新设计其中一个模块，你会如何权衡性能、复杂度和可维护性？"]
                    if question_limit >= 4
                    else []
                ),
                "",
                "## 四、回答准备建议",
                "- 准备 1 段 60 秒自我介绍和 2 段 3 分钟项目展开稿。",
                "- 每个项目至少准备一个技术难点、一个取舍决策、一个复盘点。",
                *(
                    ["- 针对目标公司准备 3 个高质量反问，体现业务理解和岗位兴趣。"]
                    if detail_cfg["template_id"] != "executive"
                    else []
                ),
                "",
                "## 五、候选人行动清单",
                "- 对照岗位要求查缺补漏，补齐最弱的 1-2 个知识点。",
                "- 做一次模拟面试，重点演练项目追问和开放题。",
                *(
                    ["- 记录本次报告中的关键词，形成自己的面试准备索引。"]
                    if detail_cfg["template_id"] != "executive"
                    else []
                ),
                "",
                "## 六、Agent 中间结果",
                compiled_sources or "暂无中间结果。",
            ]
        )
        if llm_error:
            markdown += f"\n\n> 注：最终报告已回退到本地模板模式，原因：{llm_error}"
        return markdown


def _normalize_string_list(value: object, limit: int = 5) -> List[str]:
    if not isinstance(value, list):
        return []
    items: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return items[:limit]
