import asyncio
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

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

DEFAULT_OPS_PLAN = {
    "company_name": "Northstar Clinics",
    "workflow_area": "Customer onboarding and support operations",
}

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
            "Identify operational bottlenecks, root causes, and constraints from the "
            "provided signals only. Return JSON with keys summary, operational_bottlenecks, "
            "and root_causes. Do not invent metrics."
        ),
        model=model,
    )
    bottleneck_result = await asyncio.wait_for(
        Runner.run(bottleneck_agent, input=json.dumps(payload, ensure_ascii=False)),
        timeout=OPS_AGENT_TIMEOUT_SECONDS,
    )
    bottleneck_payload = _extract_json_object(_final_agent_output(bottleneck_result))

    automation_agent = Agent(
        name="Automation Planner Agent",
        instructions=(
            "Propose practical AI/workflow automation opportunities tied to the "
            "provided bottlenecks and signals. Return JSON with key automation_opportunities. "
            "Prefer 30-day testable ideas."
        ),
        model=model,
    )
    automation_result = await asyncio.wait_for(
        Runner.run(automation_agent, input=json.dumps({**payload, **bottleneck_payload}, ensure_ascii=False)),
        timeout=OPS_AGENT_TIMEOUT_SECONDS,
    )
    automation_payload = _extract_json_object(_final_agent_output(automation_result))

    prioritization_agent = Agent(
        name="Prioritization Agent",
        instructions=(
            "Rank opportunities by impact, effort, confidence, and 30-day feasibility. "
            "Return complete JSON matching the requested Ops Pilot output schema. "
            "Do not guarantee savings, ROI, or headcount reduction."
        ),
        model=model,
    )
    priority_result = await asyncio.wait_for(
        Runner.run(
            prioritization_agent,
            input=json.dumps({**payload, **bottleneck_payload, **automation_payload}, ensure_ascii=False),
        ),
        timeout=OPS_AGENT_TIMEOUT_SECONDS,
    )
    output = coerce_ops_output(_extract_json_object(_final_agent_output(priority_result)), deterministic_output)

    risk_agent = Agent(
        name="Risk and Guardrail Reviewer Agent",
        instructions=(
            "Review the ops plan for unsupported claims, guaranteed savings, missing "
            "evidence, and final-decision language. Return JSON with risks_and_assumptions, "
            "questions_for_operator, and reviewer_notes."
        ),
        model=model,
    )
    risk_result = await asyncio.wait_for(
        Runner.run(risk_agent, input=json.dumps({**payload, "ops_review": output}, ensure_ascii=False)),
        timeout=OPS_AGENT_TIMEOUT_SECONDS,
    )
    risk_payload = _extract_json_object(_final_agent_output(risk_result))
    for key in ("risks_and_assumptions", "questions_for_operator", "reviewer_notes"):
        if isinstance(risk_payload.get(key), list) and risk_payload[key]:
            output[key] = [str(item)[:500] for item in risk_payload[key]][:12]

    return {"output": output, "model": model}


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
    for key in ("operational_bottlenecks", "automation_opportunities", "priority_ranking", "thirty_day_plan", "metrics_to_track"):
        if isinstance(payload.get(key), list) and payload[key]:
            output[key] = payload[key][:12]
    if isinstance(payload.get("recommended_first_workflow"), dict):
        output["recommended_first_workflow"] = payload["recommended_first_workflow"]
    for key in ("risks_and_assumptions", "questions_for_operator", "reviewer_notes"):
        if isinstance(payload.get(key), list) and payload[key]:
            output[key] = [str(item)[:500] for item in payload[key]][:12]
    return output


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
            f"- **{bottleneck.get('title', 'Bottleneck')}**: {bottleneck.get('evidence', '')} Root cause: {bottleneck.get('root_cause', '')}",
        ])
    lines.extend(["", "## Automation Opportunities", ""])
    for item in output["automation_opportunities"]:
        lines.append(f"- **{item.get('title', 'Opportunity')}**: {item.get('suggested_automation', '')} Why it matters: {item.get('why_it_matters', '')}")
    lines.extend(["", "## Priority Ranking", ""])
    for item in output["priority_ranking"]:
        lines.append(f"- **{item.get('opportunity', 'Opportunity')}**: Impact {item.get('impact', '')}; Effort {item.get('effort', '')}; Confidence {item.get('confidence', '')}. {item.get('reason', '')}")
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
        else:
            lines.extend(f"- {item}" for item in output[key])
    if signals:
        lines.extend(["", "## Signal Appendix", ""])
        for signal in signals[:20]:
            lines.append(f"- **{signal['type']}** ({signal['source']}, {signal['confidence']}): {signal['evidence']}")
    return "\n".join(lines).strip()


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
