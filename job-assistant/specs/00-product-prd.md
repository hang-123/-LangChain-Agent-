# 求职助手 PRD（阶段二）

## 1. 产品名称
Job Assistant

## 2. 产品目标
帮助求职者更高效地完成以下任务：
1. 上传简历 → 自动结构化画像
2. 输入岗位信息 → 智能岗位分析与合法性检测
3. 候选人 × 岗位匹配分析
4. 针对目标岗位优化简历
5. 个性化面试准备
6. 多 offer 对比分析
7. 投递流程管理（后期）

## 3. 目标用户
- 校招生

## 4. 当前阶段定义

### 阶段一（已完成）
围绕 `岗位理解 -> 匹配分析 -> 简历定制 -> 基础事实校验` 的小闭环，14节点固定线性图。
- 可选 RAG 岗位资料检索
- 可选 user_id 对话记忆

### 阶段二（当前交付范围）
围绕 `3 Agent + 7 Tool + 1 Gate + 6 Workflow` 的分层架构：
- Supervisor 智能路由（合并 IntentRouter）
- Tool 层确定性逻辑（MatchingEngine, ResumeTailor, OfferEvaluator 0 LLM）
- 统一 Gate 质量守门（合并 QualityGate + VerifierAgent）
- AnalysisAgent 深度分析（合并 QueryAgent + InsightAgent）
- ReportAgent 生成+自审（合并 ReportAgent + ReviewAgent）
- ResumeParser 文件入口（合并 ProfilePipeline）
- JobAnalyzer 岗位分析工具（合并 JIA + JDParser + LegitimacyScorer）
- 完整 STM/LTM 记忆系统

### 阶段三（后续扩展范围）
- ApplicationStore + wf_application_followup_v1（投递流程管理）

## 5. 核心场景

### 场景 A：岗位匹配分析
用户提供简历文件或结构化候选人信息 + 目标岗位信息，系统输出：
- 匹配分数（多维度）
- 优势、差距、风险提示
- 是否建议投递
- 岗位侧证据摘要（真实 JD / 公司画像 / 面经 / RAG 命中）
- 岗位合法性评估（是否为 ghost job）

### 场景 B：简历定制
用户已有匹配分析结果，系统输出：
- 针对岗位的简历摘要
- 项目描述优化建议
- 关键词覆盖建议
- 事实校验结果（通过 Gate）

### 场景 C：面试准备
系统基于简历和 JD 输出：
- 高频面试题（行为题 + 技术题 + 项目深挖题）
- 示例回答框架（背景-任务-方案-结果-复盘）
- 追问点
- 风险问题

### 场景 D：offer 对比
用户提供多个 offer 信息，系统输出：
- 10维度加权矩阵对比
- 各 offer 评分明细
- 排名与建议

### 场景 E：投递管理（阶段三）
系统记录投递状态、下一步动作、跟进提醒。

## 6. 非目标
当前版本不负责：
- 自动代投
- 编造项目经历
- 承诺 offer 概率
- 替用户作出最终职业选择
- 自动抓取所有招聘平台并大规模海投
- 自动生成最终排版好的 PDF / Word 简历模板

## 7. 成功指标
- 岗位匹配分析可解释且稳定
- 简历改写不虚构事实（fact_faithfulness = 100%）
- 用户能在 5 分钟内完成完整的匹配分析
- 用户认可输出结果"有帮助"的比例 > 70%
- Supervisor 路由准确率 > 90%
- Gate 能拦截所有虚构/越界输出

## 8. 核心约束
- 不允许虚构用户经历
- 不允许伪造数字成果
- 必须区分事实、推断、建议
- 信息不足时必须明确说"不足以判断"
- 岗位侧证据不得回写为候选人事实
- 工作流状态必须区分 background / working_set / artifacts / control / telemetry
- RAG 资料只作为岗位侧 evidence，不得进入 CandidateProfile 或 ResumeEvidence
- 对话记忆只允许保存摘要和 artifact 引用

## 9. 阶段二交付范围

### 包含
- 3 Agent: Supervisor, AnalysisAgent, ReportAgent
- 7 Tool: SearchOrchestrator, JobAnalyzer, MatchingEngine, ResumeTailor, ResumeParser, InterviewCoach, OfferEvaluator
- 1 Gate: 统一质量闸门 + 事实边界校验
- 6 Workflow: wf_match_v2, wf_resume_tailor_v2, wf_interview_prep_v2, wf_profile_bootstrap, wf_offer_compare, wf_application_followup_v1
- pgvector RAG 岗位资料检索 + 自动回写
- 完整 STM/LTM 记忆系统 + consolidation
- 所有 artifact 交付前经 Gate 校验
- career-ops 能力融入（ArchetypeDetector, LegitimacyScorer, OfferEvaluator）

### 不包含
- ApplicationStore 完整实现
- 完整聊天历史长期回放
- WorkflowState 真实分层迁移（保留兼容适配层）
- Interview Eval / Routing Eval 大规模评测
- 完整简历排版渲染
