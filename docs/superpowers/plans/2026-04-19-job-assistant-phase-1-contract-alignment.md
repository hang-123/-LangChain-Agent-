# Job Assistant Phase 1 Contract Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the repository's architecture docs, `job-assistant` specs, and Python artifact contracts around the approved hybrid `Agent + Service + Artifact` design without changing the production graph yet.

**Architecture:** This phase is a contract-first slice. It adds the missing architecture documents, updates spec boundaries to match the approved design, and introduces the new shared artifact models in `api/core/contracts.py` with tests. The existing research graph remains the runtime path for now; this phase prepares the interfaces the next refactor phases will implement.

**Tech Stack:** Markdown specs, Pydantic models, pytest, PowerShell/git, existing `api/core/contracts.py`

---

## Scope Split

The approved design spans multiple independent subsystems, so execution should be split into separate plans:

1. **This plan:** Phase 1 contract alignment
2. **Future plan:** Phase 2 job intelligence refactor
3. **Future plan:** Phase 3 workflow integration
4. **Future plan:** Phase 4 application workflow integration

This document covers only Phase 1 because it produces a clean, testable contract baseline on its own.

## File Structure

### Create

- `docs/architecture/overview.md` — top-level system boundary and hybrid architecture summary
- `docs/architecture/data-flow.md` — candidate track, job track, decision track, verification track
- `docs/architecture/agent-topology.md` — Agent/Service/Artifact topology and dependency map
- `docs/superpowers/plans/2026-04-19-job-assistant-phase-1-contract-alignment.md` — this plan
- `job-assistant/specs/17-verifier-agent.md` — verifier capability spec
- `tests/test_job_assistant_contracts.py` — regression coverage for new artifact models

### Modify

- `job-assistant/specs/00-product-prd.md` — expand product positioning to research-enhanced assistant
- `job-assistant/specs/02-domain-model.md` — add `ExternalEvidencePack`, `JobSnapshot`, `VerificationReport`
- `job-assistant/specs/10-supervisor-agent.md` — upgrade from lightweight router to orchestration coordinator
- `job-assistant/specs/11-profile-agent.md` — convert to pipeline-oriented spec
- `job-assistant/specs/12-jd-analyst-agent.md` — evolve into `JobIntelligenceAgent`
- `job-assistant/specs/13-matching-agent.md` — consume `JobSnapshot`
- `job-assistant/specs/14-resume-tailor-agent.md` — clarify external evidence usage boundary
- `job-assistant/specs/15-interview-coach-agent.md` — narrow scope to prep-pack generation
- `job-assistant/specs/16-workflow-agent.md` — rewrite as artifact-driven orchestration
- `api/core/contracts.py` — add the new shared artifact models

## Task 1: Add Architecture Source-Of-Truth Docs

**Files:**
- Create: `docs/architecture/overview.md`
- Create: `docs/architecture/data-flow.md`
- Create: `docs/architecture/agent-topology.md`

- [ ] **Step 1: Verify the architecture directory does not exist yet**

Run:

```powershell
Get-ChildItem -Path 'docs/architecture'
```

Expected: PowerShell reports `Cannot find path`, which confirms the docs are still missing.

- [ ] **Step 2: Create `docs/architecture/overview.md` with the approved system shape**

Write:

```markdown
# Job Assistant Architecture Overview

## Summary

Job Assistant uses a hybrid `Agent + Service + Artifact` architecture.

- Agents handle synthesis, prioritization, and controlled generation.
- Services and pipelines handle deterministic extraction, persistence, and state transitions.
- Shared artifacts are the only cross-boundary collaboration contract.

## Primary Runtime Shape

- `SupervisorAgent`
- `JobIntelligenceAgent`
- `MatchingAgent`
- `ResumeTailorAgent`
- `InterviewCoachAgent`
- `VerifierAgent`
- `ProfilePipeline`
- `ApplicationWorkflowService`
- `ApplicationStore`

## Architectural Rules

1. Candidate facts only come from resume evidence or explicit user input.
2. Job-side reasoning may use manual JD data and external evidence.
3. User-visible outputs must pass verifier checks before delivery.
4. The existing BettaFish research graph is a subsystem under `JobIntelligenceAgent`, not the product backbone.
```

- [ ] **Step 3: Create `docs/architecture/data-flow.md` with the three-track flow**

Write:

```markdown
# Job Assistant Data Flow

## Candidate Track

`ResumeAsset -> ProfilePipeline -> CandidateProfile + ResumeEvidence`

## Job Track

`raw_jd_text + target_company + target_role -> JobIntelligenceAgent -> JobPosting + JobRequirement + ExternalEvidencePack -> JobSnapshot`

## Decision Track

`CandidateProfile + ResumeEvidence + JobSnapshot -> MatchingAgent -> MatchAssessment`

Downstream consumers:

- `ResumeTailorAgent -> ResumeTailoringPlan + ResumeVersion`
- `InterviewCoachAgent -> InterviewPrepPack`
- `ApplicationWorkflowService -> ApplicationRecord`

## Verification Track

`user-visible artifact -> VerifierAgent -> approve | downgrade | reject`
```

- [ ] **Step 4: Create `docs/architecture/agent-topology.md` with Agent vs Service boundaries**

Write:

```markdown
# Job Assistant Agent Topology

## Agents

- `SupervisorAgent`: orchestration and response assembly
- `JobIntelligenceAgent`: job-side fact synthesis and evidence enhancement
- `MatchingAgent`: candidate/job comparison
- `ResumeTailorAgent`: resume tailoring plan and version generation
- `InterviewCoachAgent`: interview preparation pack generation
- `VerifierAgent`: fact boundary and evidence verification

## Services And Pipelines

- `ProfilePipeline`: resume parsing and evidence extraction
- `ApplicationWorkflowService`: application state transitions and reminders
- `ApplicationStore`: application persistence

## Collaboration Contract

All cross-boundary communication happens through shared artifacts instead of raw prompt context.
```

- [ ] **Step 5: Validate the new docs contain the expected headings**

Run:

```powershell
rg -n "Job Assistant Architecture Overview|Job Assistant Data Flow|Job Assistant Agent Topology" docs/architecture
```

Expected:

```text
docs/architecture/overview.md:1:# Job Assistant Architecture Overview
docs/architecture/data-flow.md:1:# Job Assistant Data Flow
docs/architecture/agent-topology.md:1:# Job Assistant Agent Topology
```

- [ ] **Step 6: Commit the architecture docs**

Run:

```bash
git add docs/architecture/overview.md docs/architecture/data-flow.md docs/architecture/agent-topology.md
git commit -m "docs: add phase 1 job assistant architecture docs"
```

## Task 2: Update Product And Domain Specs

**Files:**
- Modify: `job-assistant/specs/00-product-prd.md`
- Modify: `job-assistant/specs/02-domain-model.md`

- [ ] **Step 1: Add the research-enhanced positioning to the PRD**

Update `job-assistant/specs/00-product-prd.md` so the product goal and MVP language include external job evidence enhancement:

```markdown
## 2. 产品目标
帮助求职者更高效地完成以下任务：
1. 理解自身优势与岗位要求的匹配程度
2. 结合真实 JD、公司画像和面经信号做更稳健的岗位判断
3. 针对目标岗位优化简历
4. 生成面试准备材料
5. 追踪投递流程并给出下一步建议

## 4. 核心场景
### 场景 A：岗位匹配分析
用户上传简历并粘贴 JD，或仅提供目标公司与岗位，系统输出：
- 匹配分数
- 优势
- 差距
- 风险提示
- 是否建议投递
- 岗位侧证据摘要（真实 JD / 公司画像 / 面经）
```

- [ ] **Step 2: Add the new job-side and verification artifacts to the domain model**

Insert these sections into `job-assistant/specs/02-domain-model.md` after `JobRequirement` and before `MatchAssessment`:

~~~~markdown
### 2.6 ExternalEvidencePack
岗位侧外部证据集合，用于承接真实 JD、公司画像、团队线索与面经证据。

```json
{
  "evidence_pack_id": "jep_001",
  "job_id": "job_001",
  "sources": [
    {
      "source_id": "src_001",
      "source_type": "job_board",
      "title": "后端开发实习生",
      "url": "https://example.com/job/1",
      "snippet": "熟悉 MySQL、Redis、消息队列",
      "freshness_score": 92,
      "confidence": 0.88,
      "evidence_class": "real_jd"
    }
  ],
  "company_signals": ["交易中台", "高并发服务"],
  "interview_signals": ["项目深挖", "缓存设计"],
  "risk_flags": ["团队方向存在多来源混合，需要保守判断"]
}
```

### 2.7 JobSnapshot
面向下游匹配和生成任务的岗位快照，由手动 JD 解析结果和外部证据包共同组成。

```json
{
  "job_snapshot_id": "js_001",
  "job_id": "job_001",
  "job_posting": {},
  "job_requirements": [],
  "external_evidence_pack_id": "jep_001",
  "evidence_quality": {
    "freshness": 88,
    "coverage": 0.81,
    "ambiguity_notes": ["团队归属仍有轻微歧义"]
  }
}
```

### 2.12 VerificationReport
交付前验证结果，记录是否放行、降级或打回。

```json
{
  "verification_id": "ver_001",
  "artifact_type": "resume_version",
  "artifact_id": "resume_v_001",
  "status": "passed",
  "issues": [],
  "checked_rules": [
    "candidate_fact_boundary",
    "evidence_coverage",
    "recommendation_clarity"
  ],
  "created_at": "2026-04-19T10:00:00Z"
}
```
~~~~

- [ ] **Step 3: Update the relationship and invariant sections**

Replace the end-of-file relationship and invariant bullets with:

```markdown
## 4. 实体关系
- 一个 `JobPosting` 可以拆解为多条 `JobRequirement`，并可关联一个 `ExternalEvidencePack`。
- 一个 `JobSnapshot` 聚合一个 `JobPosting`、多条 `JobRequirement` 与一个 `ExternalEvidencePack`。
- 一次 `MatchAssessment` 绑定一个候选人和一个 `JobSnapshot`。
- 一个 `VerificationReport` 绑定一个待交付 artifact，并记录放行或打回结果。

## 5. 领域不变量
- 系统不得把 `ExternalEvidencePack` 中的岗位线索写回候选人事实。
- `JobSnapshot` 必须保留岗位侧证据质量或歧义说明。
- `VerificationReport.status` 为 `rejected` 时，对应 artifact 不得直接交付用户。
```

- [ ] **Step 4: Validate that the PRD and domain model mention the new artifacts**

Run:

```powershell
rg -n "ExternalEvidencePack|JobSnapshot|VerificationReport|岗位侧证据摘要" job-assistant/specs/00-product-prd.md job-assistant/specs/02-domain-model.md
```

Expected:

```text
job-assistant/specs/00-product-prd.md:...
job-assistant/specs/02-domain-model.md:...
```

- [ ] **Step 5: Commit the product and domain spec updates**

Run:

```bash
git add job-assistant/specs/00-product-prd.md job-assistant/specs/02-domain-model.md
git commit -m "docs: align product and domain specs with phase 1 architecture"
```

## Task 3: Realign Capability Specs Around Agent And Service Boundaries

**Files:**
- Modify: `job-assistant/specs/10-supervisor-agent.md`
- Modify: `job-assistant/specs/11-profile-agent.md`
- Modify: `job-assistant/specs/12-jd-analyst-agent.md`
- Modify: `job-assistant/specs/13-matching-agent.md`
- Modify: `job-assistant/specs/14-resume-tailor-agent.md`
- Modify: `job-assistant/specs/15-interview-coach-agent.md`
- Modify: `job-assistant/specs/16-workflow-agent.md`
- Create: `job-assistant/specs/17-verifier-agent.md`

- [ ] **Step 1: Rewrite `10-supervisor-agent.md` as an orchestration coordinator**

Replace the responsibility and output sections with:

~~~~markdown
## 2. 职责
- 识别用户意图并选择工作流。
- 判断哪些 artifact 缺失。
- 编排 `ProfilePipeline`、`JobIntelligenceAgent`、`MatchingAgent`、`ResumeTailorAgent`、`InterviewCoachAgent`、`VerifierAgent`。
- 汇总结构化产物并组织最终响应。

## 5. 输出
```json
{
  "intent": "match_resume_to_job",
  "workflow_id": "wf_match_v2",
  "required_capabilities": [
    "ProfilePipeline",
    "JobIntelligenceAgent",
    "MatchingAgent",
    "VerifierAgent"
  ],
  "missing_artifacts": [],
  "response_contract": {
    "facts": [],
    "inferences": [],
    "actions": []
  }
}
```
~~~~

- [ ] **Step 2: Convert `11-profile-agent.md` into a pipeline-oriented spec**

Rename the title and replace the first half of the file with:

```markdown
# Profile Pipeline 规范

## 1. 目标
把候选人的原始简历与补充输入整理成稳定、可复用的 `CandidateProfile` 和 `ResumeEvidence`。

## 2. 组成
- `ResumeParser`：抽取简历原文与 section
- `ProfileNormalizer`：标准化教育、经历、技能字段
- `ProfileValidator`：校验事实边界、完整度和警告

## 3. 非目标
- 不做自由推理式职业判断
- 不根据岗位侧证据补写候选人事实
```

- [ ] **Step 3: Evolve `12-jd-analyst-agent.md` into `JobIntelligenceAgent`**

Replace the title and goal with:

```markdown
# Job Intelligence Agent 规范

## 1. 目标
把原始 JD 与外部岗位证据融合为可供匹配、简历优化、面试准备共用的岗位快照。

## 2. 职责
- 解析原始 JD 为 `JobPosting` 与 `JobRequirement`
- 调用外部证据增强能力生成 `ExternalEvidencePack`
- 输出 `JobSnapshot`
- 标注证据时效、覆盖度与歧义风险
```

- [ ] **Step 4: Update matching, resume, interview, and workflow specs to consume the new artifacts**

Apply the following replacements:

```markdown
`job-assistant/specs/13-matching-agent.md`
- 输入改为 `candidate_profile + resume_evidence + job_snapshot`
- 输出说明保留 `MatchAssessment`

`job-assistant/specs/14-resume-tailor-agent.md`
- 增加规则：可使用 `ExternalEvidencePack` 调整表达重心，但不得把岗位证据伪装成候选人事实

`job-assistant/specs/15-interview-coach-agent.md`
- 增加边界：只生成准备包，不负责长对话 mock interview

`job-assistant/specs/16-workflow-agent.md`
- 编排对象改为 `ProfilePipeline + JobIntelligenceAgent + MatchingAgent + VerifierAgent`
- 增加 artifact 恢复说明：失败时按 artifact 粒度恢复，而不是重跑全链路
```

- [ ] **Step 5: Add the verifier capability spec**

Create `job-assistant/specs/17-verifier-agent.md`:

~~~~markdown
# Verifier Agent 规范

## 1. 目标
在任何用户可见输出交付前，检查事实边界、证据覆盖、冲突与降级条件。

## 2. 输入
```json
{
  "artifact_type": "resume_version",
  "artifact": {},
  "candidate_profile": {},
  "resume_evidence": [],
  "job_snapshot": {}
}
```

## 3. 输出
```json
{
  "verification_report": {},
  "decision": "passed",
  "required_regeneration": []
}
```

## 4. 核心规则
- 不允许把岗位证据写成候选人事实
- 主要结论必须带 artifact 级依据
- 证据冲突时必须输出冲突说明
- 证据弱时允许降级，不允许伪装成高置信度输出
```
~~~~

- [ ] **Step 6: Validate the capability spec vocabulary**

Run:

```powershell
rg -n "ProfilePipeline|JobIntelligenceAgent|VerifierAgent|JobSnapshot" job-assistant/specs/10-supervisor-agent.md job-assistant/specs/11-profile-agent.md job-assistant/specs/12-jd-analyst-agent.md job-assistant/specs/13-matching-agent.md job-assistant/specs/14-resume-tailor-agent.md job-assistant/specs/15-interview-coach-agent.md job-assistant/specs/16-workflow-agent.md job-assistant/specs/17-verifier-agent.md
```

Expected: every file returns at least one match relevant to the new boundary.

- [ ] **Step 7: Commit the capability spec realignment**

Run:

```bash
git add job-assistant/specs/10-supervisor-agent.md job-assistant/specs/11-profile-agent.md job-assistant/specs/12-jd-analyst-agent.md job-assistant/specs/13-matching-agent.md job-assistant/specs/14-resume-tailor-agent.md job-assistant/specs/15-interview-coach-agent.md job-assistant/specs/16-workflow-agent.md job-assistant/specs/17-verifier-agent.md
git commit -m "docs: realign job assistant capability specs"
```

## Task 4: Add The New Artifact Models To `api/core/contracts.py`

**Files:**
- Modify: `api/core/contracts.py`
- Test: `tests/test_job_assistant_contracts.py`

- [ ] **Step 1: Write the failing contract tests first**

Create `tests/test_job_assistant_contracts.py`:

```python
from __future__ import annotations

from api.core.contracts import (
    ExternalEvidenceItem,
    ExternalEvidencePack,
    JobSnapshot,
    VerificationIssue,
    VerificationReport,
)


def test_external_evidence_pack_accepts_mixed_job_sources():
    pack = ExternalEvidencePack(
        evidence_pack_id="jep_001",
        job_id="job_001",
        sources=[
            ExternalEvidenceItem(
                source_id="src_001",
                source_type="job_board",
                title="后端开发实习生",
                url="https://example.com/job",
                snippet="熟悉 Redis、MySQL",
                freshness_score=92,
                confidence=0.88,
                evidence_class="real_jd",
            )
        ],
        company_signals=["交易中台"],
        interview_signals=["缓存设计"],
        risk_flags=["方向混合"],
    )

    assert pack.sources[0].evidence_class == "real_jd"
    assert pack.company_signals == ["交易中台"]


def test_job_snapshot_references_evidence_pack_and_quality_notes():
    snapshot = JobSnapshot(
        job_snapshot_id="js_001",
        job_id="job_001",
        job_posting={},
        job_requirements=[],
        external_evidence_pack_id="jep_001",
        evidence_quality={"freshness": 88, "coverage": 0.81, "ambiguity_notes": ["团队归属存在歧义"]},
    )

    assert snapshot.external_evidence_pack_id == "jep_001"
    assert snapshot.evidence_quality["freshness"] == 88


def test_verification_report_keeps_rule_level_failures():
    report = VerificationReport(
        verification_id="ver_001",
        artifact_type="resume_version",
        artifact_id="resume_v_001",
        status="rejected",
        issues=[
            VerificationIssue(
                rule_code="candidate_fact_boundary",
                severity="high",
                message="岗位证据被写成候选人事实",
            )
        ],
        checked_rules=["candidate_fact_boundary"],
        created_at="2026-04-19T10:00:00Z",
    )

    assert report.status == "rejected"
    assert report.issues[0].rule_code == "candidate_fact_boundary"
```

- [ ] **Step 2: Run the new test file and confirm the imports fail**

Run:

```bash
pytest tests/test_job_assistant_contracts.py -q
```

Expected: FAIL with `ImportError` or `AttributeError` because the new models do not exist yet.

- [ ] **Step 3: Add the new models to `api/core/contracts.py`**

Append these models near the other Pydantic contracts:

```python
class ExternalEvidenceItem(BaseModel):
    source_id: str
    source_type: str = Field(..., description="来源类型，如 job_board、company_site、interview_note。")
    title: str = Field(default="无标题")
    url: str = Field(default="")
    snippet: str = Field(default="")
    freshness_score: int = Field(default=0, ge=0, le=100)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_class: str = Field(default="", description="证据类别，如 real_jd、company_context、interview_signal。")


class ExternalEvidencePack(BaseModel):
    evidence_pack_id: str
    job_id: str
    sources: list[ExternalEvidenceItem] = Field(default_factory=list)
    company_signals: list[str] = Field(default_factory=list)
    interview_signals: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class JobSnapshot(BaseModel):
    job_snapshot_id: str
    job_id: str
    job_posting: dict[str, Any] = Field(default_factory=dict)
    job_requirements: list[dict[str, Any]] = Field(default_factory=list)
    external_evidence_pack_id: str = ""
    evidence_quality: dict[str, Any] = Field(default_factory=dict)


class VerificationIssue(BaseModel):
    rule_code: str
    severity: Literal["low", "medium", "high"] = "medium"
    message: str


class VerificationReport(BaseModel):
    verification_id: str
    artifact_type: str
    artifact_id: str
    status: Literal["passed", "downgraded", "rejected"] = "passed"
    issues: list[VerificationIssue] = Field(default_factory=list)
    checked_rules: list[str] = Field(default_factory=list)
    created_at: str
```

- [ ] **Step 4: Run the new contract tests and confirm they pass**

Run:

```bash
pytest tests/test_job_assistant_contracts.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Run one existing contract-adjacent regression test**

Run:

```bash
pytest tests/test_eval_harness.py -q
```

Expected: existing harness tests still pass, showing the new models did not break current contracts.

- [ ] **Step 6: Commit the contract model additions**

Run:

```bash
git add api/core/contracts.py tests/test_job_assistant_contracts.py
git commit -m "feat: add phase 1 job assistant artifact contracts"
```

## Task 5: Final Phase 1 Review And Handoff

**Files:**
- Modify: `docs/architecture/overview.md`
- Modify: `docs/architecture/data-flow.md`
- Modify: `docs/architecture/agent-topology.md`
- Modify: `job-assistant/specs/00-product-prd.md`
- Modify: `job-assistant/specs/02-domain-model.md`
- Modify: `job-assistant/specs/10-supervisor-agent.md`
- Modify: `job-assistant/specs/11-profile-agent.md`
- Modify: `job-assistant/specs/12-jd-analyst-agent.md`
- Modify: `job-assistant/specs/13-matching-agent.md`
- Modify: `job-assistant/specs/14-resume-tailor-agent.md`
- Modify: `job-assistant/specs/15-interview-coach-agent.md`
- Modify: `job-assistant/specs/16-workflow-agent.md`
- Modify: `job-assistant/specs/17-verifier-agent.md`
- Modify: `api/core/contracts.py`
- Test: `tests/test_job_assistant_contracts.py`

- [ ] **Step 1: Run the complete Phase 1 verification set**

Run:

```bash
pytest tests/test_job_assistant_contracts.py tests/test_eval_harness.py -q
```

Expected:

```text
....                                                                    [100%]
```

- [ ] **Step 2: Verify the architecture vocabulary is consistent across docs and specs**

Run:

```powershell
rg -n "Agent \+ Service \+ Artifact|JobIntelligenceAgent|ProfilePipeline|VerifierAgent|JobSnapshot|ExternalEvidencePack" docs/architecture job-assistant/specs docs/superpowers/specs/2026-04-19-job-assistant-agent-architecture-design.md
```

Expected: the same core terms appear consistently across the architecture docs, approved design spec, and updated `job-assistant` specs.

- [ ] **Step 3: Review for accidental over-agentification**

Manually confirm these exact statements are true:

```text
ProfilePipeline is documented as a pipeline/service, not a free-form Agent.
ApplicationWorkflowService is documented as a service, not an Agent.
InterviewCoachAgent is limited to prep-pack generation boundaries.
The existing BettaFish research graph is positioned as a JobIntelligence subsystem.
```

- [ ] **Step 4: Commit the final cleanup if any wording changes were needed**

Run:

```bash
git add docs/architecture job-assistant/specs api/core/contracts.py tests/test_job_assistant_contracts.py
git commit -m "chore: finalize phase 1 contract alignment review"
```

## Self-Review Checklist

### Spec coverage

This plan covers the approved spec sections as follows:

- hybrid architecture shape -> Tasks 1, 3
- shared artifacts -> Tasks 2, 4
- data flow -> Task 1
- verifier rules -> Tasks 3, 4
- documentation strategy -> Tasks 1, 2, 3
- contract-first rollout -> Tasks 4, 5

Phase 2-4 implementation work is intentionally excluded and split into later plans.

### Red-Flag Scan

The plan avoids unfinished draft markers, vague cross-references, and generic testing instructions without examples.

### Type consistency

The new contract names used across the plan are consistent:

- `ExternalEvidenceItem`
- `ExternalEvidencePack`
- `JobSnapshot`
- `VerificationIssue`
- `VerificationReport`
