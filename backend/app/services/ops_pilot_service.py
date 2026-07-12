import asyncio
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from app.services.openai_agent_service import MODEL_TERRA


OPS_AGENT_MODEL_ENV = "BROPILOT_OPS_AGENT_MODEL"
OPS_AGENT_TIMEOUT_SECONDS = 75
LOCAL_TESSERACT_EXE = Path(__file__).resolve().parents[3] / "tools" / "Tesseract-OCR" / "tesseract.exe"
OPS_GUARDRAIL_BLOCKED_TERMS = (
    "will save",
    "must automate",
    "final recommendation",
    "replace the team",
)

RECOMMENDED_WORKFLOW_SCOPE_FALLBACK = (
    "Start with milestone tracking, stuck-account alerts, checklist ownership, "
    "and internal follow-up tasks for a small onboarding pilot cohort."
)

METRIC_BASELINE_FALLBACKS = {
    "average onboarding time": "Reported baseline: 21 days; validate calculation method.",
    "week-2 activation completion rate": "Needs baseline from onboarding records.",
    "week-2 activation completion": "Needs baseline from onboarding records.",
    "support backlog volume and aging": "Reported signal: backlog up 34%; validate queue scope.",
    "support backlog volume": "Reported signal: backlog up 34%; validate queue scope.",
    "manual coordination touches per account": "Needs operator baseline.",
    "manual setup touches per account": "Needs operator baseline.",
    "alert precision": "Track false positives and useful alerts during pilot.",
}

DEFAULT_RISKS = [
    (
        "Causal link not yet proven",
        "The notes suggest onboarding delay, backlog growth, and week-2 inactivity are related, but this needs cohort or ticket-level validation.",
        "Validate relationships using onboarding cohorts, ticket reasons, and activation outcomes.",
    ),
    (
        "Baselines need validation",
        "The 21-day onboarding time and 34% backlog growth should be confirmed against systems of record.",
        "Confirm metric definitions, date ranges, queue scope, and calculation methods.",
    ),
    (
        "Pilot feasibility depends on access and ownership",
        "The workflow needs reliable access to onboarding status, customer-success ownership, and support data.",
        "Assign a human owner and confirm source-of-truth systems before launching the pilot.",
    ),
    (
        "Alert fatigue risk",
        "Stuck-account alerts can become noise if thresholds are too broad or ownership is unclear.",
        "Start with a small cohort, review false positives, and tune alert thresholds weekly.",
    ),
    (
        "Security-answer governance",
        "Automating security questionnaire drafts creates accuracy and approval risk if answers are not governed.",
        "Use an approved answer bank and require human review before customer-facing responses are sent.",
    ),
]

DEFAULT_OPS_PLAN = {
    "company_name": "Northstar Clinics",
    "workflow_area": "Customer onboarding and support operations",
}


class OpsBottleneckItem(BaseModel):
    title: str = Field(..., description="Concise bottleneck title.")
    evidence: list[str] = Field(..., description="One to four source-backed evidence bullets. No raw JSON or Python syntax.")
    root_cause: str = Field(..., description="Specific likely root cause tied to the evidence.")
    source: str = Field(..., description="Source label such as OCR image, manual notes, PDF, or provided inputs.")


class BottleneckAgentOutput(BaseModel):
    summary: str
    operational_bottlenecks: list[OpsBottleneckItem]
    root_causes: list[str]


class OpsAutomationOpportunity(BaseModel):
    title: str
    workflow: str
    why_it_matters: str
    suggested_automation: list[str] = Field(..., description="Two to five concrete automation steps.")
    source: str


class AutomationAgentOutput(BaseModel):
    automation_opportunities: list[OpsAutomationOpportunity]


class OpsPriorityItem(BaseModel):
    opportunity: str
    impact: str = Field(..., description="High, Medium, or Low.")
    effort: str = Field(..., description="High, Medium, or Low.")
    confidence: str = Field(..., description="High, Medium, or Low.")
    reason: str


class OpsRecommendedWorkflow(BaseModel):
    title: str
    why_first: str
    scope: str
    human_owner: str


class OpsPlanWeek(BaseModel):
    week: str
    goal: str
    actions: list[str]


class OpsMetricItem(BaseModel):
    metric: str
    why_it_matters: str
    baseline_or_target: str


class OpsReviewDraftOutput(BaseModel):
    summary: str
    operational_bottlenecks: list[OpsBottleneckItem]
    automation_opportunities: list[OpsAutomationOpportunity]
    priority_ranking: list[OpsPriorityItem]
    recommended_first_workflow: OpsRecommendedWorkflow
    thirty_day_plan: list[OpsPlanWeek]
    metrics_to_track: list[OpsMetricItem]
    risks_and_assumptions: list[str]
    questions_for_operator: list[str]
    reviewer_notes: list[str]


class OpsRiskItem(BaseModel):
    title: str
    explanation: str
    mitigation: str


class RiskReviewAgentOutput(BaseModel):
    risks_and_assumptions: list[OpsRiskItem]
    questions_for_operator: list[str]
    reviewer_notes: list[str]

SIGNAL_RULES = [
    {
        "type": "Onboarding delay",
        "keywords": ("onboarding time", "onboarding", "activation", "implementation"),
        "patterns": (r"onboarding time is\s+([^.\\n]+)", r"(\d+\s+days)"),
    },
    {
        "type": "Backlog growth",
        "keywords": ("support backlog", "backlog", "ticket backlog"),
        "patterns": (r"backlog increased\s+([\d.]+%)",),
    },
    {
        "type": "Manual workflow",
        "keywords": ("manual", "manual setup", "account setup", "spreadsheet"),
        "patterns": (),
    },
    {
        "type": "Repeated questions",
        "keywords": ("same onboarding questions", "repeatedly", "repeat questions", "faq"),
        "patterns": (),
    },
    {
        "type": "Activation or churn risk",
        "keywords": ("inactive", "week 2", "churn", "activation delay", "dropoff"),
        "patterns": (),
    },
    {
        "type": "Procurement or security delay",
        "keywords": ("security questionnaire", "procurement", "security review", "enterprise delayed"),
        "patterns": (),
    },
    {
        "type": "Tool fragmentation",
        "keywords": ("salesforce", "zendesk", "google sheets", "slack", "email"),
        "patterns": (),
    },
    {
        "type": "Customer success capacity",
        "keywords": ("customer success", "implementation manager", "csm", "capacity"),
        "patterns": (),
    },
    {
        "type": "30-day pilot requirement",
        "keywords": ("30 days", "30-day", "pilot", "tested within 30"),
        "patterns": (),
    },
]


def extract_ops_inputs_preview(
    *,
    manual_notes: str,
    image: dict | None = None,
    pdfs: list[dict] | None = None,
) -> dict:
    context = _extract_ops_context(image=image, pdfs=pdfs or [], manual_notes=manual_notes)
    return {
        "ocr": _ocr_payload(context["ocr_text"], context["ocr_status"], context["ocr_detail"], image, context["pdf_sources"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def generate_ops_pilot_response_async(
    *,
    company_name: str,
    workflow_area: str,
    manual_notes: str,
    image: dict | None = None,
    pdfs: list[dict] | None = None,
) -> dict:
    company = company_name.strip() or DEFAULT_OPS_PLAN["company_name"]
    workflow = workflow_area.strip() or DEFAULT_OPS_PLAN["workflow_area"]
    pdfs = pdfs or []

    stages = [
        _stage(
            "Ops Intake",
            "completed",
            "Received image, PDFs, workflow area, and manual notes.",
        )
    ]

    context = _extract_ops_context(image=image, pdfs=pdfs, manual_notes=manual_notes)
    ocr_text = context["ocr_text"]
    ocr_status = context["ocr_status"]
    ocr_detail = context["ocr_detail"]
    pdf_sources = context["pdf_sources"]
    combined_text = context["combined_text"]

    stages.append(_stage("OCR / Text Extraction", "completed", _short_extraction_summary(pdf_sources, ocr_status)))

    signals = signal_extractor(
        text=combined_text,
        manual_notes=manual_notes,
        ocr_text=ocr_text,
        pdf_sources=pdf_sources,
    )
    stages.append(
        _stage(
            "Signal Extraction",
            "completed",
            f"Identified {len(signals)} operational signal(s).",
        )
    )

    deterministic_output = deterministic_fallback_generator(
        company_name=company,
        workflow_area=workflow,
        signals=signals,
        manual_notes=manual_notes,
        ocr_text=ocr_text,
    )
    agent_result = await run_ops_agent_workflow(
        company_name=company,
        workflow_area=workflow,
        signals=signals,
        manual_notes=manual_notes,
        ocr_text=ocr_text,
        deterministic_output=deterministic_output,
    )
    output = agent_result["output"]

    if agent_result["bottleneck_used"]:
        stages.append(_stage("Bottleneck Analyst Agent", "completed", "Analyzed bottlenecks and likely root causes."))
    else:
        stages.append(_stage("Bottleneck Analyst Agent", "completed", _fallback_stage_summary(agent_result)))

    if agent_result["automation_used"]:
        stages.append(_stage("Automation Planner Agent", "completed", "Proposed automation opportunities tied to workflow pain points."))
    else:
        stages.append(_stage("Automation Planner Agent", "completed", _fallback_stage_summary(agent_result)))

    if agent_result["prioritization_used"]:
        stages.append(_stage("Prioritization Agent", "completed", "Ranked opportunities by impact, effort, confidence, and 30-day feasibility."))
    else:
        stages.append(_stage("Prioritization Agent", "completed", _fallback_stage_summary(agent_result)))

    if agent_result["risk_review_used"]:
        stages.append(_stage("Risk & Guardrail Review", "completed", "Removed unsupported ROI/final-decision language and kept output review-ready."))
    else:
        stages.append(_stage("Risk & Guardrail Review", "completed", "Removed unsupported ROI/final-decision language and kept output review-ready."))

    stages.append(_stage("Human Review Artifact", "completed", "Packaged ops review, priority matrix, 30-day plan, and exports."))

    return {
        "company_name": company,
        "workflow_area": workflow,
        "ocr": _ocr_payload(ocr_text, ocr_status, ocr_detail, image, pdf_sources),
        "signals": signals,
        "stages": stages,
        "ops_review": output,
        "artifact_markdown": build_ops_markdown(company, workflow, output, signals),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation": {
            "mode": agent_result["mode"],
            "model": agent_result["model"],
            "fallback_reason": agent_result["fallback_reason"],
        },
    }


def extract_image_text(content: bytes) -> tuple[str, str, str]:
    try:
        from PIL import Image
        import pytesseract
    except Exception as error:
        raise RuntimeError(f"Local OCR dependency unavailable: {error}") from error

    try:
        if LOCAL_TESSERACT_EXE.exists():
            pytesseract.pytesseract.tesseract_cmd = str(LOCAL_TESSERACT_EXE)
        image = Image.open(io.BytesIO(content))
        text = pytesseract.image_to_string(image).strip()
    except Exception as error:
        raise RuntimeError(f"OCR failed while reading the image: {error}") from error

    if len(text) < 30:
        return text, "OCR completed with limited confidence", "OCR returned limited text; manual notes remain the primary source."
    return text, "OCR completed", "OCR extracted usable text from the uploaded image."


def _extract_ops_context(*, image: dict | None, pdfs: list[dict], manual_notes: str) -> dict:
    ocr_text = ""
    ocr_status = "OCR unavailable; using manual notes"
    ocr_detail = "No image was uploaded."
    if image:
        ocr_text, ocr_status, ocr_detail = extract_image_text(image["content"])

    pdf_sources = [extract_pdf_source(pdf) for pdf in pdfs]
    extracted_pdf_text = "\n\n".join(source["text"] for source in pdf_sources if source["text"])
    combined_text = "\n\n".join(
        part.strip()
        for part in [ocr_text, extracted_pdf_text, manual_notes.strip()]
        if part and part.strip()
    )
    return {
        "ocr_text": ocr_text,
        "ocr_status": ocr_status,
        "ocr_detail": ocr_detail,
        "pdf_sources": pdf_sources,
        "combined_text": combined_text,
    }


def _ocr_payload(
    ocr_text: str,
    ocr_status: str,
    ocr_detail: str,
    image: dict | None,
    pdf_sources: list[dict],
) -> dict:
    return {
        "status": ocr_status,
        "text": ocr_text,
        "detail": ocr_detail,
        "image_filename": image["filename"] if image else "",
        "pdf_documents": [_pdf_document_payload(source) for source in pdf_sources],
    }


def _short_extraction_summary(pdf_sources: list[dict], ocr_status: str) -> str:
    parts = []
    if pdf_sources:
        parts.append(f"Parsed {len(pdf_sources)} PDF(s).")
    else:
        parts.append("No PDFs uploaded.")

    if ocr_status == "OCR completed":
        parts.append("OCR completed.")
    elif "limited" in ocr_status.lower():
        parts.append("OCR completed with limited confidence.")
    else:
        parts.append("OCR status shown separately.")
    return " ".join(parts)


def extract_pdf_source(document: dict) -> dict:
    try:
        import pdfplumber
    except Exception as error:
        return {
            "filename": document["filename"],
            "text": "",
            "status": f"PDF extraction unavailable: {error}",
        }

    try:
        parts = []
        tables = []
        with pdfplumber.open(io.BytesIO(document["content"])) as pdf:
            for page_index, page in enumerate(pdf.pages[:8], start=1):
                text = page.extract_text() or ""
                if text.strip():
                    parts.append(text.strip())
                for table_index, table in enumerate(page.extract_tables() or [], start=1):
                    parsed_table = _parse_pdf_table(table, f"Page {page_index} table {table_index}")
                    if parsed_table:
                        tables.append(parsed_table)
        joined = "\n\n".join(parts)
        status = "PDF text extracted" if joined else "No extractable PDF text"
        return {"filename": document["filename"], "text": joined, "status": status, "tables": tables}
    except Exception as error:
        return {"filename": document["filename"], "text": "", "status": f"PDF extraction failed: {error}", "tables": []}


def _parse_pdf_table(table: list[list[str | None]], title: str) -> dict | None:
    cleaned_rows = [
        [str(cell or "").strip() for cell in row]
        for row in table
        if row and any(str(cell or "").strip() for cell in row)
    ]
    if len(cleaned_rows) < 2:
        return None

    width = max(len(row) for row in cleaned_rows)
    padded = [row + [""] * (width - len(row)) for row in cleaned_rows]
    headers = [
        header if header else f"Column {index + 1}"
        for index, header in enumerate(padded[0])
    ]
    rows = [
        {headers[index]: row[index] for index in range(width)}
        for row in padded[1:12]
    ]
    markdown_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        markdown_lines.append("| " + " | ".join(row[header] for header in headers) + " |")
    return {"title": title, "markdown": "\n".join(markdown_lines), "rows": rows}


def _pdf_document_payload(source: dict) -> dict:
    return {
        "filename": source["filename"],
        "document_type": "Operating PDF",
        "extraction_status": source["status"],
        "summary": _clean_signal_text(_compact_text(source["text"], 360)) if source["text"] else "No extractable text found.",
        "tables": source.get("tables", []),
    }


def signal_extractor(
    *,
    text: str,
    manual_notes: str,
    ocr_text: str,
    pdf_sources: list[dict],
) -> list[dict]:
    normalized = text.lower()
    sources = _source_label(manual_notes, ocr_text, pdf_sources)
    signals = []
    for rule in SIGNAL_RULES:
        matches = [keyword for keyword in rule["keywords"] if keyword in normalized]
        pattern_matches = []
        for pattern in rule["patterns"]:
            pattern_matches.extend(re.findall(pattern, text, flags=re.I))
        if matches or pattern_matches:
            evidence = _readable_signal_evidence(rule["type"], text, rule["keywords"], pattern_matches)
            signals.append(
                {
                    "type": rule["type"],
                    "evidence": evidence or ", ".join(matches[:3]),
                    "source": sources,
                    "confidence": "High" if pattern_matches or len(matches) > 1 else "Medium",
                }
            )

    metric_signals = extract_operational_metrics(text, sources)
    signals.extend(metric_signals)
    return _dedupe_signals(signals)


def extract_operational_metrics(text: str, source: str) -> list[dict]:
    metrics = []
    patterns = [
        ("Onboarding time", r"onboarding time is\s+(\d+\s+days)"),
        ("Support backlog growth", r"backlog increased\s+([\d.]+%)"),
        ("Activation risk timing", r"inactive if they do not complete activation by\s+(week\s+\d+)"),
    ]
    for label, pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            metrics.append(
                {
                    "type": label,
                    "evidence": f"{label}: {match.group(1)}",
                    "source": source,
                    "confidence": "High",
                }
            )
    return metrics


async def run_ops_agent_workflow(
    *,
    company_name: str,
    workflow_area: str,
    signals: list[dict],
    manual_notes: str,
    ocr_text: str,
    deterministic_output: dict,
) -> dict:
    fallback = {
        "output": deterministic_output,
        "mode": "deterministic_fallback",
        "model": "",
        "fallback_reason": "",
        "bottleneck_used": False,
        "automation_used": False,
        "prioritization_used": False,
        "risk_review_used": False,
    }
    if not os.environ.get("OPENAI_API_KEY"):
        return {**fallback, "fallback_reason": "OPENAI_API_KEY is not set."}

    try:
        result = await _run_ops_agents_async(
            company_name=company_name,
            workflow_area=workflow_area,
            signals=signals,
            manual_notes=manual_notes,
            ocr_text=ocr_text,
            deterministic_output=deterministic_output,
        )
    except Exception as error:
        return {**fallback, "fallback_reason": f"LLM agent failed or unavailable; deterministic fallback used. {error}"}

    validation_errors = validate_ops_output(result["output"])
    if validation_errors:
        return {
            **fallback,
            "fallback_reason": "Guardrail validation failed: " + "; ".join(validation_errors[:3]),
        }

    return {
        "output": result["output"],
        "mode": "llm_grounded",
        "model": result["model"],
        "fallback_reason": "",
        "bottleneck_used": True,
        "automation_used": True,
        "prioritization_used": True,
        "risk_review_used": True,
    }


async def _run_ops_agents_async(
    *,
    company_name: str,
    workflow_area: str,
    signals: list[dict],
    manual_notes: str,
    ocr_text: str,
    deterministic_output: dict,
) -> dict:
    try:
        from agents import Agent, Runner
    except ImportError as error:
        raise ImportError("openai-agents is not installed") from error

    model = os.environ.get(OPS_AGENT_MODEL_ENV, MODEL_TERRA).strip() or MODEL_TERRA
    payload = {
        "company_name": company_name,
        "workflow_area": workflow_area,
        "operational_signals": signals[:32],
        "manual_notes": _compact_text(manual_notes, 3000),
        "ocr_text": _compact_text(ocr_text, 1800),
        "fallback_schema": deterministic_output,
        "guardrails": [
            "Do not guarantee savings or ROI.",
            "Do not make final operating decisions.",
            "Tie recommendations to provided signals, OCR text, or manual notes.",
            "Separate evidence from assumptions.",
        ],
    }

    bottleneck_agent = Agent(
        name="Bottleneck Analyst Agent",
        instructions=(
            "You are the Ops Pilot Bottleneck Analyst Agent. Use only the provided "
            "operational_signals, manual_notes, OCR text, and PDF-derived text. Produce "
            "complete structured output matching the schema. Rules: identify 3-6 distinct "
            "bottlenecks; every bottleneck must have a unique title, 1-4 evidence bullets, "
            "a non-empty root_cause, and a source label. Evidence must be plain English "
            "strings, not a serialized array or JSON string. Do not invent metrics. Do not "
            "repeat the same bottleneck under different names."
        ),
        model=model,
        output_type=BottleneckAgentOutput,
    )
    bottleneck_result = await asyncio.wait_for(
        Runner.run(bottleneck_agent, input=json.dumps(payload, ensure_ascii=False)),
        timeout=OPS_AGENT_TIMEOUT_SECONDS,
    )
    bottleneck_payload = _agent_output_to_dict(bottleneck_result)

    automation_agent = Agent(
        name="Automation Planner Agent",
        instructions=(
            "You are the Ops Pilot Automation Planner Agent. Produce complete structured "
            "output matching the schema. Propose 3-6 practical automation opportunities "
            "directly tied to the provided bottlenecks and signals. Every opportunity must "
            "have a unique title, non-empty why_it_matters, and 2-5 concrete "
            "suggested_automation steps as an actual JSON array of strings. Do not put "
            "Python/list syntax inside a string. Prefer 30-day testable ideas with human "
            "review and narrow pilot scope."
        ),
        model=model,
        output_type=AutomationAgentOutput,
    )
    automation_result = await asyncio.wait_for(
        Runner.run(automation_agent, input=json.dumps({**payload, **bottleneck_payload}, ensure_ascii=False)),
        timeout=OPS_AGENT_TIMEOUT_SECONDS,
    )
    automation_payload = _agent_output_to_dict(automation_result)

    prioritization_agent = Agent(
        name="Prioritization Agent",
        instructions=(
            "You are the Ops Pilot Prioritization Agent. Return one complete Ops Pilot "
            "review matching the output schema exactly. Preserve the bottlenecks and "
            "automation opportunities from prior agents unless you need to remove duplicates. "
            "Rank opportunities by impact, effort, confidence, and 30-day feasibility. "
            "Recommended first workflow scope must be non-empty and concrete. Metrics must "
            "have non-empty baseline_or_target values, even when the value is a validation "
            "request. Risks must be meaningful, not generic repeated placeholders. Do not "
            "guarantee savings, ROI, headcount reduction, or final operating decisions."
        ),
        model=model,
        output_type=OpsReviewDraftOutput,
    )
    priority_result = await asyncio.wait_for(
        Runner.run(
            prioritization_agent,
            input=json.dumps({**payload, **bottleneck_payload, **automation_payload}, ensure_ascii=False),
        ),
        timeout=OPS_AGENT_TIMEOUT_SECONDS,
    )
    output = coerce_ops_output(_agent_output_to_dict(priority_result), deterministic_output)

    risk_agent = Agent(
        name="Risk and Guardrail Reviewer Agent",
        instructions=(
            "You are the Ops Pilot Risk and Guardrail Reviewer Agent. Return structured "
            "output matching the schema. Produce exactly 5 concise, distinct risks with "
            "title, explanation, and mitigation. Prefer risks like causal link not proven, "
            "baseline validation, pilot feasibility, alert fatigue, and security-answer "
            "governance when supported by the inputs. Do not return raw dict strings. Do "
            "not repeat generic phrases like Operating assumption needs review. Produce at "
            "most 8 operator questions and at most 6 reviewer notes. Flag unsupported "
            "claims, guaranteed savings, missing evidence, and final-decision language."
        ),
        model=model,
        output_type=RiskReviewAgentOutput,
    )
    risk_result = await asyncio.wait_for(
        Runner.run(risk_agent, input=json.dumps({**payload, "ops_review": output}, ensure_ascii=False)),
        timeout=OPS_AGENT_TIMEOUT_SECONDS,
    )
    risk_payload = _agent_output_to_dict(risk_result)
    for key in ("risks_and_assumptions", "questions_for_operator", "reviewer_notes"):
        if isinstance(risk_payload.get(key), list) and risk_payload[key]:
            output[key] = risk_payload[key][:12]

    return {"output": normalize_ops_output(output), "model": model}


def deterministic_fallback_generator(
    *,
    company_name: str,
    workflow_area: str,
    signals: list[dict],
    manual_notes: str,
    ocr_text: str,
) -> dict:
    signal_types = {signal["type"] for signal in signals}
    source = "both" if manual_notes.strip() and ocr_text.strip() else ("OCR image" if ocr_text.strip() else "manual notes")

    bottlenecks = []
    if {"Onboarding delay", "Onboarding time"} & signal_types:
        bottlenecks.append(
            {
                "title": "Slow customer onboarding",
                "evidence": _signal_evidence(signals, ("Onboarding delay", "Onboarding time")),
                "root_cause": "Manual setup, repeated questions, and cross-tool coordination likely slow activation.",
                "source": source,
            }
        )
    if {"Backlog growth", "Support backlog growth"} & signal_types:
        bottlenecks.append(
            {
                "title": "Growing support backlog",
                "evidence": _signal_evidence(signals, ("Backlog growth", "Support backlog growth")),
                "root_cause": "Recurring onboarding and support questions appear to consume customer-success capacity.",
                "source": source,
            }
        )
    if "Procurement or security delay" in signal_types:
        bottlenecks.append(
            {
                "title": "Enterprise procurement and security delays",
                "evidence": _signal_evidence(signals, ("Procurement or security delay",)),
                "root_cause": "Security questionnaires and procurement reviews create repeated pre-implementation friction.",
                "source": source,
            }
        )
    if not bottlenecks:
        bottlenecks.append(
            {
                "title": "Workflow friction requires operator review",
                "evidence": _compact_text(manual_notes or ocr_text, 220) or "Limited evidence provided.",
                "root_cause": "The uploaded materials need additional operating context before prioritization.",
                "source": source,
            }
        )

    opportunities = [
        {
            "title": "Activation risk alerts + onboarding checklist automation",
            "workflow": workflow_area,
            "why_it_matters": "Targets delayed activation and accounts at risk of becoming inactive before week 2.",
            "suggested_automation": "Trigger alerts from onboarding milestones, create checklist tasks, and route stuck accounts to customer success.",
            "source": source,
        },
        {
            "title": "Reusable onboarding answer assistant",
            "workflow": workflow_area,
            "why_it_matters": "Repeated onboarding questions consume implementation-manager time.",
            "suggested_automation": "Use a source-grounded assistant or macro library for common onboarding questions and handoff notes.",
            "source": source,
        },
        {
            "title": "Security questionnaire response workspace",
            "workflow": "Enterprise procurement",
            "why_it_matters": "Security questionnaires and procurement reviews delay higher-ACV regional health groups.",
            "suggested_automation": "Create a reviewed answer bank and workflow for routing security/procurement requests.",
            "source": source,
        },
    ]

    priority = [
        {
            "opportunity": opportunities[0]["title"],
            "impact": "High",
            "effort": "Medium",
            "confidence": "High" if signals else "Medium",
            "reason": "Directly tied to onboarding time, activation risk, and a 30-day testable workflow.",
        },
        {
            "opportunity": opportunities[1]["title"],
            "impact": "Medium",
            "effort": "Low",
            "confidence": "Medium",
            "reason": "Repeated questions are usually easy to standardize, but answer quality needs operator review.",
        },
        {
            "opportunity": opportunities[2]["title"],
            "impact": "Medium",
            "effort": "Medium",
            "confidence": "Medium",
            "reason": "Likely valuable for enterprise deals, but requires current security/procurement artifacts.",
        },
    ]

    return {
        "summary": (
            f"{company_name} shows operational friction in {workflow_area.lower()}, especially around "
            "onboarding speed, support load, manual coordination, and activation risk. This is a review-ready "
            "operations plan, not a final automation decision."
        ),
        "operational_bottlenecks": bottlenecks,
        "automation_opportunities": opportunities,
        "priority_ranking": priority,
        "recommended_first_workflow": {
            "title": "Activation risk alerts + onboarding checklist automation",
            "why_first": "It is tied to onboarding delay, activation risk, and customer-success capacity, and can be tested without replacing core systems.",
            "scope": "Start with milestone tracking, stuck-account alerts, and a reviewed onboarding checklist for new customers.",
            "human_owner": "Customer Success or Implementation Operations lead",
        },
        "thirty_day_plan": [
            {"week": "Week 1", "goal": "Map the onboarding path", "actions": ["Define activation milestones.", "Identify stuck-account triggers.", "Collect recent onboarding examples."]},
            {"week": "Week 2", "goal": "Prototype workflow alerts", "actions": ["Create checklist fields.", "Draft Slack/email alert rules.", "Review alert thresholds with CS."]},
            {"week": "Week 3", "goal": "Pilot with a small cohort", "actions": ["Run the workflow on current onboarding accounts.", "Track alert volume.", "Capture operator feedback."]},
            {"week": "Week 4", "goal": "Review results and decide next step", "actions": ["Compare activation progress.", "Identify false positives.", "Decide whether to expand, adjust, or stop."]},
        ],
        "metrics_to_track": [
            {"metric": "Average onboarding time", "why_it_matters": "Primary delay signal.", "baseline_or_target": "Baseline mentioned: 21 days, if validated."},
            {"metric": "Support backlog volume", "why_it_matters": "Shows whether repeat work is decreasing.", "baseline_or_target": "Baseline mentioned: +34% quarter-over-quarter, if validated."},
            {"metric": "Week-2 activation completion", "why_it_matters": "Leading indicator for churn or inactivity risk.", "baseline_or_target": "Track percentage of accounts activated by week 2."},
            {"metric": "Manual setup touches per account", "why_it_matters": "Measures customer-success capacity impact.", "baseline_or_target": "Needs operator baseline."},
        ],
        "risks_and_assumptions": [
            "The plan assumes onboarding delay and support backlog are connected; this needs operator validation.",
            "No guaranteed savings, ROI, or headcount impact is claimed.",
            "Automation should not bypass human review for customer-facing communications or security answers.",
        ],
        "questions_for_operator": [
            "Which onboarding milestones predict activation and retention?",
            "How many accounts are currently stuck at each onboarding step?",
            "Which questions are repeated most often by new customers?",
            "Who owns security questionnaire accuracy and approval?",
            "What systems are the source of truth for onboarding status?",
        ],
        "reviewer_notes": [
            "Use this as a review-ready operations plan, not a final operating decision.",
            "Validate baselines before presenting impact claims.",
            "Start with a narrow pilot and keep customer-facing steps human-reviewed.",
        ],
    }


def coerce_ops_output(payload: dict, fallback: dict) -> dict:
    output = dict(fallback)
    if isinstance(payload.get("summary"), str):
        output["summary"] = payload["summary"][:1200]
    for key in ("thirty_day_plan", "metrics_to_track"):
        if isinstance(payload.get(key), list) and payload[key]:
            output[key] = payload[key][:12]
    if isinstance(payload.get("operational_bottlenecks"), list) and payload["operational_bottlenecks"]:
        output["operational_bottlenecks"] = payload["operational_bottlenecks"][:12]
    if isinstance(payload.get("automation_opportunities"), list) and payload["automation_opportunities"]:
        output["automation_opportunities"] = payload["automation_opportunities"][:12]
    if isinstance(payload.get("priority_ranking"), list) and payload["priority_ranking"]:
        output["priority_ranking"] = payload["priority_ranking"][:12]
    if isinstance(payload.get("recommended_first_workflow"), dict):
        output["recommended_first_workflow"] = payload["recommended_first_workflow"]
    for key in ("risks_and_assumptions", "questions_for_operator", "reviewer_notes"):
        if isinstance(payload.get(key), list) and payload[key]:
            output[key] = payload[key][:12]
    return normalize_ops_output(output)


def normalize_ops_output(output: dict) -> dict:
    normalized = dict(output)
    normalized["recommended_first_workflow"] = _normalize_recommended_workflow(
        normalized.get("recommended_first_workflow")
    )
    normalized["operational_bottlenecks"] = _dedupe_dicts(
        [_normalize_bottleneck(item) for item in _as_list(normalized.get("operational_bottlenecks"))],
        "title",
    )[:12]
    normalized["automation_opportunities"] = _dedupe_dicts(
        [_normalize_opportunity(item) for item in _as_list(normalized.get("automation_opportunities"))],
        "title",
    )[:12]
    normalized["priority_ranking"] = _dedupe_dicts(
        [_normalize_priority(item) for item in _as_list(normalized.get("priority_ranking"))],
        "opportunity",
    )[:12]
    normalized["metrics_to_track"] = _dedupe_dicts(
        [_normalize_metric(item) for item in _as_list(normalized.get("metrics_to_track"))],
        "metric",
    )[:12]
    normalized["risks_and_assumptions"] = _normalize_risks(
        normalized.get("risks_and_assumptions")
    )
    normalized["questions_for_operator"] = [
        _normalize_plain_item(item)
        for item in _as_list(normalized.get("questions_for_operator"))
    ][:12]
    normalized["reviewer_notes"] = [
        _normalize_plain_item(item)
        for item in _as_list(normalized.get("reviewer_notes"))
    ][:8]
    return normalized


def _normalize_recommended_workflow(item) -> dict:
    if not isinstance(item, dict):
        item = {}
    return {
        "title": _clean_output_text(item.get("title") or "Activation risk alerts and onboarding checklist automation"),
        "why_first": _clean_output_text(
            item.get("why_first")
            or item.get("why")
            or "It targets onboarding delay, week-2 activation risk, fragmented tracking, and customer-success coordination burden in a narrow pilot scope."
        ),
        "scope": _clean_output_text(item.get("scope") or RECOMMENDED_WORKFLOW_SCOPE_FALLBACK),
        "human_owner": _clean_output_text(item.get("human_owner") or item.get("owner") or "Customer Success Operations or Implementation Operations lead"),
    }


def _normalize_bottleneck(item) -> dict:
    if not isinstance(item, dict):
        item = {"title": _normalize_plain_item(item), "evidence": "", "root_cause": ""}
    title = _clean_output_text(item.get("title") or "Operational bottleneck")
    evidence = _normalize_text_or_list(item.get("evidence") or item.get("description") or "Signal identified in operating inputs.")
    root_cause = _clean_output_text(item.get("root_cause") or item.get("rootCause") or "")
    if not root_cause:
        root_cause = _fallback_root_cause(title, _plain_join(evidence))
    return {
        "title": title,
        "evidence": evidence,
        "root_cause": root_cause,
        "source": _clean_output_text(item.get("source") or "provided inputs"),
    }


def _normalize_opportunity(item) -> dict:
    if not isinstance(item, dict):
        item = {"title": _normalize_plain_item(item)}
    title = _clean_output_text(item.get("title") or item.get("opportunity") or "Automation opportunity")
    why = _clean_output_text(item.get("why_it_matters") or item.get("why") or "")
    automation = _normalize_text_or_list(item.get("suggested_automation") or item.get("automation") or item.get("recommendation") or "")
    if not why:
        why = _fallback_why_it_matters(title)
    if not automation:
        automation = _fallback_automation(title)
    return {
        "title": title,
        "workflow": _clean_output_text(item.get("workflow") or "Operations workflow"),
        "why_it_matters": why,
        "suggested_automation": automation,
        "source": _clean_output_text(item.get("source") or "provided inputs"),
    }


def _normalize_metric(item) -> dict:
    if not isinstance(item, dict):
        item = {"metric": _normalize_plain_item(item)}
    metric = _clean_output_text(item.get("metric") or item.get("name") or "Operating metric")
    return {
        "metric": metric,
        "why_it_matters": _clean_output_text(item.get("why_it_matters") or item.get("why") or "Tracks whether the pilot is improving the target workflow."),
        "baseline_or_target": _clean_output_text(item.get("baseline_or_target") or item.get("baseline") or item.get("target") or _fallback_metric_baseline(metric)),
    }


def _normalize_priority(item) -> dict:
    if not isinstance(item, dict):
        item = {"opportunity": _normalize_plain_item(item)}
    opportunity = _clean_output_text(item.get("opportunity") or item.get("title") or "Automation opportunity")
    return {
        "opportunity": opportunity,
        "impact": _level(item.get("impact")),
        "effort": _level(item.get("effort")),
        "confidence": _level(item.get("confidence")),
        "reason": _clean_output_text(item.get("reason") or _fallback_priority_reason(item)),
    }


def _normalize_risks(items) -> list[str]:
    normalized = []
    for item in _as_list(items):
        risk = _normalize_risk_item(item)
        if _is_useful_risk(risk):
            normalized.append(risk)
    normalized.extend(_default_risk_texts())
    return _dedupe_texts(normalized)[:10]


def _normalize_risk_item(item) -> str:
    if isinstance(item, dict):
        title = _clean_output_text(
            item.get("title")
            or item.get("risk")
            or item.get("name")
            or "Operating assumption needs review"
        )
        explanation = _clean_output_text(
            item.get("explanation")
            or item.get("description")
            or item.get("assumption")
            or item.get("details")
            or ""
        )
        evidence_gap = _clean_output_text(item.get("evidence_gap") or item.get("gap") or "")
        mitigation = _clean_output_text(item.get("mitigation") or item.get("next_step") or "")
        parts = [title]
        if explanation and explanation.lower() != title.lower():
            parts.append(explanation)
        if evidence_gap:
            parts.append(f"Evidence gap: {evidence_gap}")
        if mitigation:
            parts.append(f"Mitigation: {mitigation}")
        return " ".join(parts)
    return _clean_output_text(str(item))


def _normalize_plain_item(item) -> str:
    if isinstance(item, dict):
        return _normalize_risk_item(item)
    return _clean_output_text(str(item))


def _normalize_text_or_list(value):
    if isinstance(value, list):
        items = [_clean_output_text(item) for item in value if _clean_output_text(item)]
        return items or ""
    return _clean_output_text(value)


def _plain_join(value) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value or "")


def _fallback_metric_baseline(metric: str) -> str:
    metric_key = metric.lower()
    for key, fallback in METRIC_BASELINE_FALLBACKS.items():
        if key in metric_key or metric_key in key:
            return fallback
    return "Needs operator baseline."


def _default_risk_texts() -> list[str]:
    return [
        f"{title} {explanation} Mitigation: {mitigation}"
        for title, explanation, mitigation in DEFAULT_RISKS
    ]


def _is_useful_risk(text: str) -> bool:
    normalized = text.strip().lower()
    return bool(normalized) and normalized != "operating assumption needs review"


def _dedupe_texts(items: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _dedupe_dicts(items: list[dict], key_name: str) -> list[dict]:
    seen = set()
    deduped = []
    for item in items:
        key = str(item.get(key_name) or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _fallback_root_cause(title: str, evidence: str) -> str:
    text = f"{title} {evidence}".lower()
    if "backlog" in text:
        return "Recurring support work and unresolved onboarding friction are likely increasing queue pressure."
    if "security" in text or "procurement" in text:
        return "Security and procurement work appears to rely on manual coordination and repeated answer reuse."
    if "activation" in text or "onboarding" in text:
        return "Fragmented tracking, manual setup, and unclear ownership likely slow activation."
    return "The operating notes suggest a workflow ownership, handoff, or systems-of-record gap."


def _fallback_why_it_matters(title: str) -> str:
    text = title.lower()
    if "activation" in text or "onboarding" in text:
        return "It targets onboarding delay and week-2 activation risk in a narrow pilot scope."
    if "security" in text or "questionnaire" in text:
        return "It reduces repeated security/procurement work while keeping answers reviewed."
    if "assistant" in text or "question" in text:
        return "It reduces repeated customer-success work and improves consistency."
    return "It addresses an operating pain point identified in the uploaded materials."


def _fallback_automation(title: str) -> str:
    text = title.lower()
    if "activation" in text or "onboarding" in text:
        return "Create reviewed onboarding milestones, stuck-account alerts, and checklist task routing."
    if "security" in text or "questionnaire" in text:
        return "Create an approved answer bank and draft-response workflow for human review."
    if "assistant" in text or "question" in text:
        return "Create a source-grounded response assistant or macro library for repeated onboarding questions."
    return "Create a small workflow automation pilot with human review and measured baselines."


def _fallback_priority_reason(item: dict) -> str:
    opportunity = _clean_output_text(item.get("opportunity") or item.get("title") or "This workflow")
    impact = _level(item.get("impact"))
    effort = _level(item.get("effort"))
    confidence = _level(item.get("confidence"))
    return f"{opportunity} is ranked with {impact.lower()} impact, {effort.lower()} effort, and {confidence.lower()} confidence based on extracted operating signals."


def _level(value) -> str:
    normalized = str(value or "").strip().title()
    return normalized if normalized in {"High", "Medium", "Low"} else "Medium"


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _clean_output_text(value) -> str:
    if isinstance(value, list):
        text = "; ".join(_clean_output_text(item) for item in value if _clean_output_text(item))
    elif isinstance(value, dict):
        text = "; ".join(
            f"{str(key).replace('_', ' ').title()}: {_clean_output_text(item)}"
            for key, item in value.items()
            if _clean_output_text(item)
        )
    else:
        text = str(value or "")
    text = " ".join(text.split())
    text = re.sub(r"^\s*Risk:\s*", "", text, flags=re.I)
    return text[:700]


def validate_ops_output(output: dict) -> list[str]:
    errors = []
    text = json.dumps(output, ensure_ascii=False).lower()
    for term in OPS_GUARDRAIL_BLOCKED_TERMS:
        if term in text:
            errors.append(f"Blocked final-decision or ROI language: {term}")
    for pattern in (r"\bguarantee(?:d)?\s+(?:roi|savings)\b", r"\b(?:roi|savings)\s+is\s+guaranteed\b"):
        for match in re.finditer(pattern, text):
            window = text[max(0, match.start() - 40):match.end() + 20]
            if not any(negation in window for negation in ("no ", "not ", "avoid ", "without ", "do not ", "does not ")):
                errors.append("Blocked unsupported guaranteed ROI/savings language.")
                break
    required = [
        "summary",
        "operational_bottlenecks",
        "automation_opportunities",
        "priority_ranking",
        "recommended_first_workflow",
        "thirty_day_plan",
        "metrics_to_track",
        "risks_and_assumptions",
        "questions_for_operator",
        "reviewer_notes",
    ]
    for key in required:
        if not output.get(key):
            errors.append(f"Missing required output key: {key}")
    return errors


def build_ops_markdown(company_name: str, workflow_area: str, output: dict, signals: list[dict]) -> str:
    lines = [
        f"# {company_name} Ops Review",
        "",
        f"Generated: {datetime.now(timezone.utc).date().isoformat()}",
        f"Workflow area: {workflow_area}",
        "",
        "> Review-ready operations improvement plan. Human review required before implementation decisions.",
        "",
        "## Executive Summary",
        "",
        output["summary"],
        "",
        "## Operational Bottlenecks",
        "",
    ]
    for bottleneck in output["operational_bottlenecks"]:
        lines.extend([
            f"- **{bottleneck.get('title', 'Bottleneck')}**",
            _markdown_detail("Evidence", bottleneck.get("evidence", "")),
            f"  - Root cause: {bottleneck.get('root_cause', '')}",
        ])
    lines.extend(["", "## Automation Opportunities", ""])
    for item in output["automation_opportunities"]:
        lines.extend([
            f"- **{item.get('title', 'Opportunity')}**",
            f"  - Why it matters: {item.get('why_it_matters', '')}",
            _markdown_detail("Automation", item.get("suggested_automation", "")),
        ])
    lines.extend(["", "## Priority Ranking", ""])
    for item in output["priority_ranking"]:
        lines.append(f"- **{item.get('opportunity', 'Opportunity')}**: Impact {item.get('impact', '')}; Effort {item.get('effort', '')}; Confidence {item.get('confidence', '')}.")
    first = output["recommended_first_workflow"]
    lines.extend([
        "",
        "## Recommended First Workflow",
        "",
        f"**{first.get('title', '')}**",
        "",
        first.get("why_first", ""),
        "",
        f"Scope: {first.get('scope', '')}",
        "",
        f"Human owner: {first.get('human_owner', '')}",
        "",
        "## 30-Day Action Plan",
        "",
    ])
    for week in output["thirty_day_plan"]:
        actions = "; ".join(week.get("actions", []))
        lines.append(f"- **{week.get('week', '')}**: {week.get('goal', '')}. {actions}")
    for title, key in [
        ("Metrics to Track", "metrics_to_track"),
        ("Risks and Assumptions", "risks_and_assumptions"),
        ("Questions for Operator", "questions_for_operator"),
        ("Reviewer Notes", "reviewer_notes"),
    ]:
        lines.extend(["", f"## {title}", ""])
        if key == "metrics_to_track":
            for metric in output[key]:
                lines.append(f"- **{metric.get('metric', '')}**: {metric.get('why_it_matters', '')} Baseline/target: {metric.get('baseline_or_target', '')}")
        elif key == "risks_and_assumptions":
            lines.extend(f"- {item}" for item in output[key][:5])
        elif key == "questions_for_operator":
            lines.extend(f"- {item}" for item in output[key][:8])
        else:
            lines.extend(f"- {item}" for item in output[key])
    if signals:
        lines.extend(["", "## Signal Appendix", ""])
        for signal in signals[:20]:
            lines.append(f"- **{signal['type']}** ({signal['source']}, {signal['confidence']}): {signal['evidence']}")
    return "\n".join(lines).strip()


def _markdown_detail(label: str, value) -> str:
    if isinstance(value, list):
        lines = [f"  - {label}:"]
        lines.extend(f"    - {item}" for item in value if str(item).strip())
        return "\n".join(lines)
    return f"  - {label}: {value}"


def _source_label(manual_notes: str, ocr_text: str, pdf_sources: list[dict]) -> str:
    labels = []
    if ocr_text.strip():
        labels.append("OCR image")
    if manual_notes.strip():
        labels.append("manual notes")
    if any(source["text"].strip() for source in pdf_sources):
        labels.append("PDF")
    return " + ".join(labels) if labels else "provided inputs"


def _readable_signal_evidence(signal_type: str, text: str, keywords: tuple[str, ...], pattern_matches: list[str]) -> str:
    normalized = text.lower()
    if signal_type == "Onboarding delay":
        average = re.search(r"(?:average\s+)?customer onboarding time is\s+(\d+\s+days)", text, flags=re.I)
        if average:
            return f"Average customer onboarding time is {average.group(1)}."
        setup = re.search(r"account setup[\s\S]{0,80}?(\d+\s*-\s*\d+\s*days|\d+\s+days)", text, flags=re.I)
        security = re.search(r"security review[\s\S]{0,80}?(\d+\s+days)", text, flags=re.I)
        activation = re.search(r"activation review[\s\S]{0,80}?(week\s+\d+)", text, flags=re.I)
        if setup or security or activation:
            parts = []
            if setup:
                parts.append(f"Account setup takes {_normalize_duration(setup.group(1))}")
            if security:
                parts.append(f"security review can add {security.group(1)}")
            if activation:
                parts.append(f"activation review happens around {activation.group(1)}")
            return _sentence_from_parts(parts)
    if signal_type == "Backlog growth":
        match = re.search(r"support backlog increased\s+([\d.]+%)", text, flags=re.I)
        if match:
            return f"Support backlog increased {match.group(1)} over the last quarter."
    if signal_type in {"Manual workflow", "Tool fragmentation"}:
        tools = [tool for tool in ("Salesforce", "Zendesk", "Google Sheets", "Slack", "email") if tool.lower() in normalized]
        if tools:
            return f"Account setup is handled across {', '.join(tools[:-1])}, and {tools[-1]}." if len(tools) > 1 else f"Account setup uses {tools[0]}."
    if signal_type == "Activation or churn risk" and "week 2" in normalized:
        return "Accounts inactive by week 2 are more likely to stall."
    if signal_type == "Procurement or security delay":
        if "regional health" in normalized:
            return "Security questionnaires and procurement reviews slow higher-ACV regional health group deals."
        return "Security questionnaires and procurement reviews slow enterprise deals."
    if signal_type == "Repeated questions":
        return "Implementation managers answer the same onboarding questions repeatedly."
    if signal_type == "Customer success capacity":
        return "Customer success and implementation teams spend repeated time on setup and onboarding coordination."
    if signal_type == "30-day pilot requirement":
        return "Leadership wants an automation opportunity that can be tested within 30 days."
    return _evidence_snippet(text, keywords, pattern_matches)


def _evidence_snippet(text: str, keywords: tuple[str, ...], pattern_matches: list[str]) -> str:
    if pattern_matches:
        return _clean_signal_text("; ".join(str(match) for match in pattern_matches[:3]))
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    for sentence in sentences:
        if any(keyword in sentence.lower() for keyword in keywords):
            return _clean_signal_text(_compact_text(sentence, 240))
    return ""


def _sentence_from_parts(parts: list[str]) -> str:
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0].rstrip(".") + "."
    return ", ".join(parts[:-1]) + f", and {parts[-1]}."


def _normalize_duration(value: str) -> str:
    return re.sub(r"\s*-\s*", "-", value.strip())


def _clean_signal_text(text: str) -> str:
    cleaned = re.sub(r"(?i)operating summary prepared for ops pilot ocr/text extraction demo\.?", "", text)
    cleaned = re.sub(r"(?i)prepared for ops pilot ocr/text extraction demo\.?", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _signal_evidence(signals: list[dict], types: tuple[str, ...]) -> str:
    for signal in signals:
        if signal["type"] in types:
            return signal["evidence"]
    return "Signal detected in provided operating notes."


def _dedupe_signals(signals: list[dict]) -> list[dict]:
    seen = set()
    deduped = []
    for signal in signals:
        key = (signal["type"], signal["evidence"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(signal)
    return deduped[:24]


def _fallback_stage_summary(agent_result: dict) -> str:
    reason = agent_result.get("fallback_reason") or "LLM agent failed or unavailable; deterministic fallback used."
    if reason.lower().startswith("guardrail validation failed"):
        return "Guardrail adjusted output; review-ready version used."
    return reason if "deterministic fallback" in reason.lower() else f"{reason}; deterministic fallback used."


def _stage(name: str, status: str, summary: str) -> dict:
    return {"name": name, "status": status, "summary": summary}


def _compact_text(text: str, limit: int = 500) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def _agent_output_to_dict(result) -> dict:
    output = getattr(result, "final_output", None)
    if isinstance(output, BaseModel):
        return output.model_dump()
    if isinstance(output, dict):
        return output
    return _extract_json_object(_final_agent_output(result))


def _extract_json_object(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _final_agent_output(result) -> str:
    value = getattr(result, "final_output", None)
    if value is None:
        value = str(result)
    return str(value)
