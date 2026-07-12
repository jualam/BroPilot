import asyncio
import io
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from app.services.openai_agent_service import MODEL_LUNA, MODEL_TERRA


MEMO_AGENT_MODEL_ENV = "BROPILOT_MEMO_AGENT_MODEL"
MEMO_AGENT_TIMEOUT_SECONDS = 90
MEMO_GUARDRAIL_BLOCKED_TERMS = (
    "we recommend investing",
    "recommend investing",
    "approve the investment",
    "reject the investment",
    "pass on the investment",
    "buy the company",
)


MEMO_SECTIONS = [
    "Executive Summary",
    "Company Overview",
    "Product / Value Proposition",
    "Market and Customer Thesis",
    "Traction and Financial Signals",
    "Go-to-Market Motion",
    "Competitive Landscape",
]

DOCUMENT_TYPES = [
    ("Pitch Deck", ("pitch", "deck", "investor", "fundraise", "vision")),
    ("Financial Summary", ("arr", "revenue", "gross margin", "ebitda", "burn", "runway")),
    ("Customer Notes", ("customer", "churn", "retention", "nps", "renewal")),
    ("Risk Review", ("risk review", "implementation risk", "operational risk", "diligence implication", "mitigation", "implementation scalability", "ehr integration effort", "services-heavy onboarding")),
    ("Market Research", ("market", "tam", "sam", "competition", "segment")),
    ("Product Overview", ("product", "platform", "workflow", "feature", "integration")),
    ("Sales/GTM Notes", ("sales", "pipeline", "gtm", "go-to-market", "quota", "conversion")),
]

CATEGORY_KEYWORDS = {
    "Financials": ("arr", "revenue", "gross margin", "acv", "cac", "payback", "rule of 40"),
    "Customer Validation": ("customer", "retention", "renewal", "nps", "feedback", "objection"),
    "Traction": ("growth", "pipeline", "expansion", "customers", "logo"),
    "Product": ("product", "platform", "workflow", "feature", "integration"),
    "Market": ("market", "tam", "sam", "segment", "industry", "clinics", "practices"),
    "GTM": ("sales", "gtm", "go-to-market", "pipeline", "conversion", "sales cycle", "onboarding"),
    "Risk": ("risk", "churn", "dependency", "competition", "burn", "delay", "missing", "not provided"),
}

RISK_KEYWORDS = {
    "Top 5 customer concentration": ("top 5 customer", "customer concentration", "concentration"),
    "EHR integration complexity": ("ehr", "integration", "mapping"),
    "Implementation scalability / services dependency": ("implementation", "onboarding", "professional services", "services-heavy"),
    "Longer regional health group sales cycles": ("sales cycle", "regional", "procurement", "security review"),
    "Missing CAC payback": ("cac payback", "sales efficiency"),
    "Audited financials not provided": ("audited financials", "audit"),
    "Competitive pressure": ("competition", "competitor", "crowded", "pricing pressure"),
    "Financial visibility risk": ("burn", "runway", "margin", "cash", "forecast"),
}

TABLE_METRIC_KEYWORDS = (
    "arr",
    "revenue",
    "customers",
    "customer",
    "acv",
    "gross margin",
    "net revenue retention",
    "retention",
    "revenue mix",
    "sales cycle",
    "concentration",
    "segment",
    "share",
)


def generate_memo_pilot_response(
    *,
    documents: list[dict],
    manual_notes: str,
    company_name: str,
    sector: str,
) -> dict:
    return asyncio.run(
        generate_memo_pilot_response_async(
            documents=documents,
            manual_notes=manual_notes,
            company_name=company_name,
            sector=sector,
        )
    )


def extract_memo_pilot_preview(*, documents: list[dict], manual_notes: str) -> dict:
    processed_documents, _all_sources = _extract_sources_and_documents(documents, manual_notes)
    return {
        "documents": processed_documents,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_sources_and_documents(documents: list[dict], manual_notes: str) -> tuple[list[dict], list[dict]]:
    processed_documents = []
    all_sources = []
    for document in documents:
        extracted_text, tables, status = extract_pdf_content(document["content"])
        source = {
            "filename": document["filename"],
            "text": extracted_text,
            "tables": tables,
            "document_type": detect_document_type(extracted_text, document["filename"]),
            "extraction_status": status,
            "summary": summarize_text(extracted_text) if extracted_text else "No extractable text found.",
        }
        processed_documents.append(
            {
                "filename": source["filename"],
                "document_type": source["document_type"],
                "extraction_status": source["extraction_status"],
                "summary": _document_summary(source),
                "tables": tables,
            }
        )
        all_sources.append(source)

    if manual_notes.strip():
        all_sources.append(
            {
                "filename": "Manual notes",
                "text": manual_notes.strip(),
                "tables": [],
                "document_type": "Manual Notes",
                "extraction_status": "provided",
                "summary": summarize_text(manual_notes),
            }
        )

    return processed_documents, all_sources


async def generate_memo_pilot_response_async(
    *,
    documents: list[dict],
    manual_notes: str,
    company_name: str,
    sector: str,
) -> dict:
    stages = []
    stages.append(_stage(
        "Document Intake",
        "completed",
        f"Deterministic intake received {len(documents)} document(s), company metadata, and manual notes.",
    ))

    processed_documents, all_sources = _extract_sources_and_documents(documents, manual_notes)
    stages.append(_stage("Text Extraction", "completed", _text_extraction_summary(processed_documents, manual_notes)))

    evidence = extract_evidence(all_sources)
    stages.append(_stage(
        "Evidence Extraction",
        "completed",
        f"Deterministic evidence builder extracted {len(evidence)} source-backed evidence item(s).",
    ))

    deterministic_plan = plan_memo(evidence, company_name, sector)
    deterministic_memo = draft_memo(evidence, deterministic_plan, company_name, sector)
    deterministic_memo["key_risks"] = detect_risks(evidence)
    deterministic_memo["missing_evidence"], deterministic_memo["diligence_questions"] = review_evidence_gaps(evidence)
    deterministic_memo["reviewer_notes"] = reviewer_notes(evidence, processed_documents)

    charts = build_charts(evidence, deterministic_memo)
    memo_result = await run_memo_agent_workflow(
        evidence=evidence,
        manual_notes=manual_notes,
        company_name=company_name,
        sector=sector,
        charts=charts,
        deterministic_memo=deterministic_memo,
    )

    if memo_result["planner_used"]:
        stages.append(_stage("Memo Planner", "completed", "AI-assisted planner mapped source-backed evidence into memo sections."))
    else:
        stages.append(_stage("Memo Planner", "completed", "Deterministic planner mapped source-backed evidence into memo sections."))

    if memo_result["draft_used"]:
        stages.append(_stage("Draft Generator", "completed", "LLM memo agent generated the draft using structured evidence, source names, and manual notes."))
    else:
        stages.append(_stage("Draft Generator", "completed", "Fallback memo generated from deterministic evidence pipeline."))

    if memo_result["risk_review_used"]:
        stages.append(_stage("Risk Checker", "completed", "Hybrid rules + AI review checked risks, assumptions, missing support, and unsupported claims."))
    else:
        stages.append(_stage("Risk Checker", "completed", f"Deterministic risk rules identified {len(memo_result['memo']['key_risks'])} risk or assumption item(s)."))

    guardrail_summary = memo_result["guardrail_summary"]
    stages.append(_stage("Evidence Gap Review", "completed", guardrail_summary))

    memo = memo_result["memo"]
    artifact_markdown = build_markdown_artifact(memo, evidence, company_name, sector)
    stages.append(_stage("Human Review Artifact", "completed", "Deterministic exporter packaged markdown, evidence appendix, reviewer notes, and PDF-ready output."))

    return {
        "documents": processed_documents,
        "evidence": evidence,
        "stages": stages,
        "memo": memo,
        "charts": charts,
        "artifact_markdown": artifact_markdown,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "memo_generation": {
            "mode": memo_result["mode"],
            "model": memo_result["model"],
            "fallback_reason": memo_result["fallback_reason"],
        },
    }


def extract_pdf_text(content: bytes) -> tuple[str, str]:
    text, _tables, status = extract_pdf_content(content)
    return text, status


async def run_memo_agent_workflow(
    *,
    evidence: list[dict],
    manual_notes: str,
    company_name: str,
    sector: str,
    charts: dict,
    deterministic_memo: dict,
) -> dict:
    fallback = {
        "memo": deterministic_memo,
        "mode": "deterministic_fallback",
        "model": "",
        "fallback_reason": "",
        "planner_used": False,
        "draft_used": False,
        "risk_review_used": False,
        "guardrail_summary": "Deterministic fallback used.",
    }
    if not os.environ.get("OPENAI_API_KEY"):
        return {**fallback, "fallback_reason": "OPENAI_API_KEY is not set."}

    try:
        result = await _run_memo_agents_async(
            evidence=evidence,
            manual_notes=manual_notes,
            company_name=company_name,
            sector=sector,
            charts=charts,
            deterministic_memo=deterministic_memo,
        )
    except Exception as error:
        return {**fallback, "fallback_reason": f"LLM memo agent failed: {error}"}

    validation_errors = _validate_llm_memo(result["memo"], evidence, deterministic_memo)
    if validation_errors:
        return {
            **fallback,
            "fallback_reason": "Guardrail validation failed: " + "; ".join(validation_errors[:3]),
            "guardrail_summary": "LLM output failed guardrails; deterministic fallback used.",
        }

    return {
        "memo": result["memo"],
        "mode": "llm_grounded",
        "model": result["model"],
        "fallback_reason": "",
        "planner_used": True,
        "draft_used": True,
        "risk_review_used": True,
        "guardrail_summary": "Deterministic guardrail validation completed. LLM output passed source-grounding and no-recommendation checks.",
    }


async def _run_memo_agents_async(
    *,
    evidence: list[dict],
    manual_notes: str,
    company_name: str,
    sector: str,
    charts: dict,
    deterministic_memo: dict,
) -> dict:
    try:
        from agents import Agent, Runner
    except ImportError as error:
        raise ImportError("openai-agents is not installed") from error

    model = _memo_agent_model()
    payload = _memo_agent_payload(
        evidence=evidence,
        manual_notes=manual_notes,
        company_name=company_name,
        sector=sector,
        charts=charts,
        deterministic_memo=deterministic_memo,
    )

    planner = Agent(
        name="Memo Planner Agent",
        instructions=(
            "You are the Memo Planner Agent for BroPilot Workbench. Use only the "
            "provided structured evidence, source names, chart metrics, detected risks, "
            "missing evidence, and manual notes. Return compact JSON with key "
            "'section_plan'. Do not invent facts."
        ),
        model=model,
    )
    plan_result = await asyncio.wait_for(
        Runner.run(planner, input=json.dumps(payload, ensure_ascii=False)),
        timeout=MEMO_AGENT_TIMEOUT_SECONDS,
    )
    section_plan = _extract_json_object(_final_agent_output(plan_result))

    draft_agent = Agent(
        name="Memo Draft Agent",
        instructions=(
            "You are the Memo Draft Agent for BroPilot Workbench. Draft a concise, "
            "professional diligence memo using only the provided structured evidence "
            "and section plan. Do not make a final investment recommendation. Do not "
            "invent facts. Major claims should mention source document names when possible. "
            "Return JSON only with top-level key 'memo' matching the requested schema."
        ),
        model=model,
    )
    draft_prompt = json.dumps({**payload, "section_plan": section_plan}, ensure_ascii=False)
    draft_result = await asyncio.wait_for(
        Runner.run(draft_agent, input=draft_prompt),
        timeout=MEMO_AGENT_TIMEOUT_SECONDS,
    )
    draft_payload = _extract_json_object(_final_agent_output(draft_result))
    memo = _coerce_memo_shape(draft_payload.get("memo") or draft_payload, deterministic_memo)

    risk_agent = Agent(
        name="Risk Review Agent",
        instructions=(
            "You are the Risk Review Agent for BroPilot Workbench. Review the memo "
            "against the provided evidence. Improve key risks, missing evidence, "
            "diligence questions, and reviewer notes while staying source-grounded. "
            "Do not recommend invest/pass/buy/approve/reject. Return JSON only with "
            "keys: key_risks, missing_evidence, diligence_questions, reviewer_notes."
        ),
        model=model,
    )
    risk_prompt = json.dumps({**payload, "draft_memo": memo}, ensure_ascii=False)
    risk_result = await asyncio.wait_for(
        Runner.run(risk_agent, input=risk_prompt),
        timeout=MEMO_AGENT_TIMEOUT_SECONDS,
    )
    risk_payload = _extract_json_object(_final_agent_output(risk_result))
    for key in ("key_risks", "missing_evidence", "diligence_questions", "reviewer_notes"):
        if isinstance(risk_payload.get(key), list) and risk_payload[key]:
            memo[key] = [str(item)[:500] for item in risk_payload[key]][:12]

    return {"memo": memo, "model": model}


def _memo_agent_model() -> str:
    return os.environ.get(MEMO_AGENT_MODEL_ENV, MODEL_TERRA).strip() or MODEL_TERRA


def _memo_agent_payload(
    *,
    evidence: list[dict],
    manual_notes: str,
    company_name: str,
    sector: str,
    charts: dict,
    deterministic_memo: dict,
) -> dict:
    compact_evidence = [
        {
            "fact": item.get("fact", ""),
            "source_document": item.get("source_document", ""),
            "category": item.get("category", ""),
            "support_level": item.get("support_level", ""),
            "evidence_type": item.get("evidence_type", ""),
        }
        for item in evidence[:36]
    ]
    return {
        "company_name": company_name.strip() or "Company",
        "sector": sector.strip() or "Not provided",
        "structured_evidence": compact_evidence,
        "manual_notes": _compact_text(manual_notes, limit=2500),
        "charts": charts,
        "detected_risks": deterministic_memo.get("key_risks", []),
        "missing_evidence": deterministic_memo.get("missing_evidence", []),
        "draft_schema": {
            "memo": {
                "executive_summary": "string",
                "company_overview": "string",
                "product_value_proposition": "string",
                "market_customer_thesis": "string",
                "traction_financial_signals": "string",
                "gtm_motion": "string",
                "competitive_landscape": "string",
                "key_risks": ["string"],
                "missing_evidence": ["string"],
                "diligence_questions": ["string"],
                "reviewer_notes": ["string"],
            }
        },
        "guardrails": [
            "Use only uploaded documents, extracted evidence, and manual notes.",
            "Do not invent facts.",
            "Do not make a final investment recommendation.",
            "If competitors or win/loss data are missing, say that instead of inventing competitors.",
            "Mention source document names for major metrics or claims when possible.",
        ],
    }


def extract_pdf_content(content: bytes) -> tuple[str, list[dict], str]:
    plumber_text, tables = _extract_with_pdfplumber(content)
    if plumber_text or tables:
        combined_text = _clean_extracted_text(plumber_text)
        status = "text and tables extracted" if tables else "text extracted"
        return combined_text, tables, status

    pypdf_text = _extract_with_pypdf(content)
    if pypdf_text:
        return _clean_extracted_text(pypdf_text), [], "text extracted"

    fallback_text = _extract_pdf_text_fallback(content)
    if fallback_text:
        return fallback_text, [], "limited text extracted"

    return "", [], "no extractable text"


def _extract_with_pdfplumber(content: bytes) -> tuple[str, list[dict]]:
    try:
        import pdfplumber
    except ImportError:
        return "", []

    text_parts = []
    tables = []
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text:
                    text_parts.append(page_text)

                for table_index, table in enumerate(page.extract_tables() or [], start=1):
                    rows = _normalize_table(table)
                    if len(rows) < 2:
                        continue
                    tables.append(
                        {
                            "title": f"Page {page_index} Table {table_index}",
                            "markdown": _table_to_markdown(rows),
                            "rows": _table_to_rows(rows),
                        }
                    )
    except Exception:
        return "", []

    return _compact_whitespace("\n".join(text_parts)), tables


def _extract_with_pypdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            return ""

    try:
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def _final_agent_output(result: object) -> str:
    value = getattr(result, "final_output", result)
    return str(value)


def _extract_json_object(value: str) -> dict:
    text = value.strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Agent did not return JSON.")
    parsed = json.loads(text[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("Agent JSON was not an object.")
    return parsed


def _coerce_memo_shape(candidate: dict, fallback: dict) -> dict:
    text_keys = [
        "executive_summary",
        "company_overview",
        "product_value_proposition",
        "market_customer_thesis",
        "traction_financial_signals",
        "gtm_motion",
        "competitive_landscape",
    ]
    list_keys = ["key_risks", "missing_evidence", "diligence_questions", "reviewer_notes"]
    memo = {}
    for key in text_keys:
        value = candidate.get(key)
        memo[key] = _compact_text(value, limit=1800) if value else fallback.get(key, "")
    for key in list_keys:
        value = candidate.get(key)
        if isinstance(value, list) and value:
            memo[key] = [_compact_text(item, limit=500) for item in value][:12]
        else:
            memo[key] = list(fallback.get(key, []))
    return memo


def _validate_llm_memo(memo: dict, evidence: list[dict], fallback: dict) -> list[str]:
    errors = []
    joined = " ".join(str(value) for value in memo.values()).lower()
    if any(term in joined for term in MEMO_GUARDRAIL_BLOCKED_TERMS):
        errors.append("Final investment recommendation language detected.")
    for term in (" invest ", " pass ", " buy ", " approve ", " reject "):
        if term in f" {joined} ":
            errors.append(f"Blocked decision term detected: {term.strip()}.")
            break

    required_text = [
        "executive_summary",
        "company_overview",
        "traction_financial_signals",
        "competitive_landscape",
    ]
    for key in required_text:
        if not str(memo.get(key, "")).strip():
            errors.append(f"Missing memo section: {key}.")

    if not memo.get("missing_evidence") and fallback.get("missing_evidence"):
        errors.append("Missing evidence was dropped.")

    source_names = {
        str(item.get("source_document", "")).strip()
        for item in evidence
        if str(item.get("source_document", "")).strip()
    }
    financial_section = str(memo.get("traction_financial_signals", ""))
    if any(token in financial_section.lower() for token in ("arr", "revenue", "margin", "retention")):
        if source_names and not any(source in financial_section for source in source_names):
            errors.append("Financial claims lack source document names.")
    return errors


def _compact_text(value: object, limit: int = 1200) -> str:
    text = _compact_whitespace(str(value or ""))
    return text[:limit].rstrip()


def _extract_pdf_text_fallback(content: bytes) -> str:
    decoded = content.decode("latin-1", errors="ignore")
    candidates = re.findall(r"\(([^()]{3,})\)", decoded)
    if not candidates:
        candidates = re.findall(r"<([0-9A-Fa-f\s]{8,})>", decoded)

    text_parts = []
    for candidate in candidates[:400]:
        if re.fullmatch(r"[0-9A-Fa-f\s]+", candidate):
            try:
                candidate = bytes.fromhex(candidate).decode("latin-1", errors="ignore")
            except ValueError:
                continue
        cleaned = _compact_whitespace(candidate)
        if _looks_like_text(cleaned):
            text_parts.append(cleaned)

    return _compact_whitespace(" ".join(text_parts))[:18000]


def detect_document_type(text: str, filename: str) -> str:
    haystack = f"{filename} {text}".lower()
    best_type = "Unknown"
    best_score = 0
    for document_type, keywords in DOCUMENT_TYPES:
        score = sum(1 for keyword in keywords if keyword in haystack)
        if score > best_score:
            best_type = document_type
            best_score = score

    return best_type


def summarize_text(text: str) -> str:
    sentences = [
        sentence for sentence in _sentences(text)
        if not _is_low_value_evidence(sentence)
    ]
    if not sentences:
        return "No extractable summary available."
    return _compact_whitespace(" ".join(sentences[:2]))[:320]


def extract_evidence(sources: list[dict]) -> list[dict]:
    evidence = []
    seen = set()
    for source in sources:
        for table_item in _extract_table_evidence(source):
            key = (table_item["source_document"], table_item["fact"].lower())
            if key in seen:
                continue
            seen.add(key)
            evidence.append(table_item)

        for sentence in _sentences(source["text"])[:80]:
            if _is_low_value_evidence(sentence) or _looks_like_broken_table_fragment(sentence, source):
                continue
            category = categorize_sentence(sentence)
            if category == "General" and len(sentence) < 80:
                continue
            key = (source["filename"], sentence.lower())
            if key in seen:
                continue
            seen.add(key)
            evidence.append(
                {
                    "fact": sentence,
                    "source_document": source["filename"],
                    "category": category,
                    "support_level": support_level(sentence, source["document_type"]),
                    "evidence_type": "text",
                }
            )

    ranked = sorted(evidence, key=_evidence_score, reverse=True)
    return ranked[:36]


def categorize_sentence(sentence: str) -> str:
    lowered = sentence.lower()
    scores = {
        category: sum(1 for keyword in keywords if keyword in lowered)
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    category, score = max(scores.items(), key=lambda item: item[1])
    return category if score else "General"


def support_level(sentence: str, document_type: str) -> str:
    lowered = sentence.lower()
    if any(token in lowered for token in ("arr", "$", "%", "revenue", "customer")):
        return "High"
    if document_type in {"Financial Summary", "Customer Notes", "Manual Notes"}:
        return "Medium"
    return "Directional"


def plan_memo(evidence: list[dict], company_name: str, sector: str) -> dict:
    by_category = defaultdict(list)
    for item in evidence:
        by_category[item["category"]].append(item)
    return {
        "company_name": company_name.strip() or "Company",
        "sector": sector.strip() or "Not provided",
        "by_category": by_category,
    }


def draft_memo(evidence: list[dict], plan: dict, company_name: str, sector: str) -> dict:
    name = company_name.strip() or "the company"
    sector_text = sector.strip() or "the relevant market"
    financial_signals = _financial_signal_sentences(evidence)
    revenue_mix = _revenue_mix_sentences(evidence)
    risk_preview = _risk_preview(evidence)

    return {
        "executive_summary": (
            f"{name} operates in {_sector_descriptor(sector_text)}, based on the uploaded materials. "
            "The materials support a review-ready diligence draft across product, market, financial performance, GTM motion, and risk. "
            f"{_join_sentences(financial_signals[:2])} "
            f"{risk_preview} This draft does not make an investment recommendation."
        ),
        "company_overview": _section_from_ranked_evidence(
            evidence,
            ["Product", "Market", "GTM"],
            ["pitch", "deck", "summary"],
            f"{name} operates in {sector_text}; additional company overview support should be requested.",
        ),
        "product_value_proposition": _section_from_ranked_evidence(
            evidence,
            ["Product", "Customer Validation"],
            ["pitch", "customer"],
            "Product evidence is limited in the uploaded materials.",
        ),
        "market_customer_thesis": _compose_market_customer_thesis(evidence, revenue_mix),
        "traction_financial_signals": _compose_financial_section(financial_signals, revenue_mix),
        "gtm_motion": _section_from_ranked_evidence(
            evidence,
            ["GTM", "Customer Validation", "Risk"],
            ["pitch", "customer", "manual"],
            "Go-to-market motion requires additional evidence.",
        ),
        "competitive_landscape": _compose_competitive_landscape(evidence),
        "key_risks": [],
        "missing_evidence": [],
        "diligence_questions": [],
        "reviewer_notes": [],
    }


def detect_risks(evidence: list[dict]) -> list[str]:
    risks = []
    text = " ".join(item["fact"] for item in evidence).lower()
    for risk, keywords in RISK_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            risks.append(risk)
    if not risks:
        risks.append("Risk profile is under-supported by the uploaded materials.")
    return risks[:6]


def review_evidence_gaps(evidence: list[dict]) -> tuple[list[str], list[str]]:
    text = " ".join(item["fact"] for item in evidence).lower()
    missing = []
    expected = {
        "CAC payback by segment": ("cac payback", "payback"),
        "Audited financials": ("audited financials", "audit"),
        "Cohort retention or logo retention": ("cohort retention", "logo retention"),
        "Implementation margin or services margin": ("implementation margin", "services margin"),
        "Detailed churn reasons": ("churn reason", "churn reasons"),
        "Competitive win/loss data": ("win/loss", "win rate", "loss data"),
        "Customer concentration detail": ("customer concentration", "top 5 customer"),
        "Gross margin bridge": ("gross margin bridge",),
        "Sales efficiency by segment": ("sales efficiency", "cac by segment"),
        "Market size / TAM support": ("tam", "market size"),
    }
    for gap, keywords in expected.items():
        if not any(keyword in text for keyword in keywords):
            missing.append(gap)

    if not missing:
        missing.append("Management references or source documents for the most important claims")

    questions = _build_diligence_questions(evidence, missing)
    return missing[:10], questions[:12]


def reviewer_notes(evidence: list[dict], documents: list[dict]) -> list[str]:
    notes = [
        "Human review required before use in any investment process.",
        "Facts are limited to uploaded documents and manual notes.",
    ]
    limited_statuses = {"limited text extracted", "no extractable text"}
    if any(document["extraction_status"] in limited_statuses for document in documents):
        notes.append("Some documents had limited extraction; scanned PDFs may require OCR.")
    if not evidence:
        notes.append("No strong evidence was extracted; memo should be treated as a shell draft.")
    return notes


def build_charts(evidence: list[dict], memo: dict) -> dict:
    return {
        "arr_growth": extract_arr_growth(evidence),
        "evidence_completeness": evidence_completeness(evidence),
        "risk_priority": build_risk_priority(evidence, memo),
    }


def extract_arr_growth(evidence: list[dict]) -> list[dict]:
    points = []
    table_pattern = re.compile(r"(20\d{2}(?:\s+Projection)?|20\d{2})=([\$]?\s?[\d,.]+(?:\.\d+)?\s?(?:m|mm|million|k)?)", re.I)
    for item in evidence:
        metric_label = _table_metric_label(item["fact"])
        if not metric_label or not _is_arr_metric_label(metric_label):
            continue
        for year_label, value_text in table_pattern.findall(item["fact"]):
            parsed = _parse_money_value(value_text)
            if parsed:
                points.append(
                    {
                        "year": year_label,
                        "arr": parsed,
                        "display_value": _format_compact_currency(parsed),
                    }
                )
        if points:
            break
    return sorted(points, key=lambda point: re.search(r"20\d{2}", point["year"]).group(0) if re.search(r"20\d{2}", point["year"]) else point["year"])


def evidence_completeness(evidence: list[dict]) -> list[dict]:
    weights = Counter()
    for item in evidence:
        categories = {item["category"], *_evidence_secondary_categories(item)}
        for category in categories:
            weights[category] += 2 if item.get("evidence_type") == "table_row" else 1
    categories = ["Product", "Market", "Traction", "Financials", "GTM", "Risk", "Customer Validation"]
    text = " ".join(item["fact"] for item in evidence).lower()
    return [
        {"category": category, "score": _category_coverage_score(category, weights.get(category, 0), text)}
        for category in categories
    ]


def _category_coverage_score(category: str, weight: int, evidence_text: str) -> int:
    if weight <= 0:
        return 0
    score = min(84, 30 + weight * 9)
    coverage_boosts = {
        "Traction": (
            (("arr", "revenue growth"), 7),
            (("customers", "customer count"), 6),
            (("net revenue retention", "gross retention", "retention"), 6),
            (("gross margin", "margin"), 4),
            (("growth", "projection"), 4),
        ),
        "Financials": (
            (("arr",), 5),
            (("acv",), 5),
            (("gross margin",), 5),
            (("net revenue retention", "nrr"), 5),
            (("gross retention",), 5),
            (("share of", "revenue mix"), 4),
            (("concentration",), 4),
        ),
    }
    for keywords, boost in coverage_boosts.get(category, ()):
        if any(keyword in evidence_text for keyword in keywords):
            score += boost
    gap_penalties = {
        "Product": (
            (("technical architecture", "architecture"), 8),
            (("implementation repeatability", "repeatable"), 8),
            (("integration depth", "integration"), 6),
        ),
        "Market": (
            (("tam", "market size"), 12),
            (("market growth",), 8),
            (("competitor", "competition", "win/loss"), 8),
        ),
        "Traction": (
            (("cohort retention", "logo retention"), 10),
            (("churn reason", "churn reasons"), 8),
            (("cac payback", "payback"), 8),
        ),
        "Financials": (
            (("cac payback", "payback"), 10),
            (("audited financials", "audit"), 10),
            (("gross margin bridge",), 8),
            (("sales efficiency",), 8),
        ),
        "GTM": (
            (("sales efficiency", "cac"), 8),
            (("win rate", "conversion"), 8),
            (("pipeline",), 6),
        ),
        "Risk": (
            (("risk", "concentration", "missing", "not provided", "delay", "complexity"), 0),
            (("mitigation", "action plan"), 8),
        ),
        "Customer Validation": (
            (("customer notes", "customer feedback", "positive feedback", "objection"), 0),
            (("cohort", "retention by cohort"), 8),
            (("nps", "reference"), 6),
        ),
    }
    for keywords, penalty in gap_penalties.get(category, ()):
        if not any(keyword in evidence_text for keyword in keywords):
            score -= penalty
    return max(20, min(94, score))


def build_risk_priority(evidence: list[dict], memo: dict) -> list[dict]:
    rules = [
        ("Top 5 customer concentration", ("top 5 customer", "customer concentration", "concentration"), 90),
        ("EHR integration complexity", ("ehr", "integration", "mapping"), 86),
        ("Implementation scalability / services dependency", ("professional services", "services-heavy", "onboarding", "implementation timeline"), 82),
        ("Longer regional health group sales cycles", ("regional", "sales cycle", "procurement", "security review"), 76),
        ("Missing CAC payback", ("cac payback", "payback not provided"), 72),
        ("Audited financials not provided", ("audited financials", "audit"), 68),
        ("Margin pressure from services-heavy onboarding", ("professional services", "implementation margin", "services-heavy"), 62),
    ]
    risk_items = []
    for label, keywords, base_score in rules:
        matches = [
            item for item in evidence
            if any(keyword in item["fact"].lower() for keyword in keywords)
        ]
        if matches:
            strongest = max(matches, key=lambda item: _risk_match_score(label, item))
            risk_items.append(
                {
                    "risk": label,
                    "score": base_score,
                    "reason": _risk_reason(label, strongest, evidence),
                    "source": strongest["source_document"],
                }
            )
    if risk_items:
        return risk_items[:6]
    return [
        {"risk": risk, "score": max(45, 90 - index * 12), "reason": "Generated from extracted risk evidence.", "source": ""}
        for index, risk in enumerate(memo["key_risks"][:5])
    ]


def build_markdown_artifact(memo: dict, evidence: list[dict], company_name: str, sector: str) -> str:
    title = f"{company_name.strip() or 'Company'} Diligence Memo Draft"
    lines = [
        f"# {title}",
        "",
        f"Generated: {datetime.now(timezone.utc).date().isoformat()}",
        f"Sector: {sector.strip() or 'Not provided'}",
        "",
        "> Review-ready diligence memo draft generated from uploaded documents and user-provided notes. Human review required before use in any investment process.",
        "",
    ]
    section_keys = [
        ("Executive Summary", "executive_summary"),
        ("Company Overview", "company_overview"),
        ("Product / Value Proposition", "product_value_proposition"),
        ("Market and Customer Thesis", "market_customer_thesis"),
        ("Traction and Financial Signals", "traction_financial_signals"),
        ("Go-to-Market Motion", "gtm_motion"),
        ("Competitive Landscape", "competitive_landscape"),
    ]
    for title, key in section_keys:
        lines.extend([f"## {title}", "", memo[key], ""])
    for title, key in [
        ("Key Risks", "key_risks"),
        ("Missing Evidence", "missing_evidence"),
        ("Diligence Questions", "diligence_questions"),
        ("Reviewer Notes", "reviewer_notes"),
    ]:
        lines.extend([f"## {title}", ""])
        lines.extend(f"- {item}" for item in memo[key])
        lines.append("")
    if evidence:
        lines.extend(["## Evidence Appendix", ""])
        lines.extend(
            f"- **{item['category']}** ({item['source_document']}, {item['support_level']}): {item['fact']}"
            for item in evidence[:20]
        )
        lines.append("")
    return "\n".join(lines).strip()


def _section_from_evidence(evidence: list[dict], categories: list[str], fallback: str) -> str:
    selected = [item for item in evidence if item["category"] in categories][:3]
    if not selected:
        return fallback
    return " ".join(f"{item['fact']} (Source: {item['source_document']})." for item in selected)


def _table_metric_label(fact: str) -> str:
    match = re.match(r"Table metric ([^:]+):", fact)
    return match.group(1).strip() if match else ""


def _table_metric_parts(fact: str) -> tuple[str, list[tuple[str, str]]]:
    match = re.match(r"Table metric ([^:]+):\s*(.*)", fact)
    if not match:
        return "", []
    return match.group(1).strip(), _metric_pairs(match.group(2))


def _is_arr_metric_label(label: str) -> bool:
    normalized = re.sub(r"[^a-z]", "", label.lower())
    return normalized in {"arr", "annualrecurringrevenue"}


def _format_compact_currency(value: int) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,}"


def _evidence_secondary_categories(item: dict) -> set[str]:
    fact = item["fact"].lower()
    categories = set()
    if any(token in fact for token in ("arr", "revenue growth", "customer count", "customers:", "net revenue retention", "gross retention", "retention", "acv")):
        categories.add("Traction")
    if any(token in fact for token in ("arr", "gross margin", "acv", "net revenue retention", "gross retention", "customer concentration", "cac", "payback", "revenue mix", "share of")):
        categories.add("Financials")
    if any(token in fact for token in ("product", "workflow", "prior authorization", "scheduling", "patient follow-up", "referral intake", "admin workflow", "integration")):
        categories.add("Product")
    if any(token in fact for token in ("segment", "icp", "share of", "clinics", "practices", "regional health", "revenue mix")):
        categories.add("Market")
    if any(token in fact for token in ("sales cycle", "sales motion", "implementation timeline", "regional health", "onboarding", "pipeline", "procurement")):
        categories.add("GTM")
    if any(token in fact for token in ("concentration", "ehr", "implementation", "missing", "not provided", "dependency", "services", "churn", "procurement", "security review", "audited financials", "cac payback")):
        categories.add("Risk")
    if any(token in fact for token in ("customer", "feedback", "objection", "buying", "expansion", "implementation support", "positive feedback")):
        categories.add("Customer Validation")
    return categories


def _risk_match_score(label: str, item: dict) -> int:
    fact = item["fact"].lower()
    score = _evidence_score(item)
    label_keywords = {
        "Top 5 customer concentration": ("top 5", "concentration"),
        "EHR integration complexity": ("ehr", "mapping", "integration complexity"),
        "Implementation scalability / services dependency": ("professional services", "services-heavy", "onboarding", "implementation timeline"),
        "Longer regional health group sales cycles": ("regional", "sales cycle", "procurement", "security review"),
        "Missing CAC payback": ("cac payback", "not provided"),
        "Audited financials not provided": ("audited financials", "audit"),
        "Margin pressure from services-heavy onboarding": ("professional services", "implementation margin", "services-heavy"),
    }
    for keyword in label_keywords.get(label, ()):
        if keyword in fact:
            score += 35
    return score


def _risk_reason(label: str, item: dict, evidence: list[dict]) -> str:
    fact = item["fact"]
    metric_label, pairs = _table_metric_parts(fact)
    pair_lookup = {key.lower(): value for key, value in pairs}
    comment = pair_lookup.get("comment") or pair_lookup.get("notes") or pair_lookup.get("concern or objection")
    current_value = pair_lookup.get("current value")

    if label == "Top 5 customer concentration" and current_value:
        return f"Top customers represent {current_value}, creating concentration risk that should be reviewed before investment."
    if label == "EHR integration complexity":
        return "Extracted customer or operating evidence indicates that EHR integration complexity can delay implementation and time-to-value."
    if label == "Implementation scalability / services dependency":
        if current_value and "professional services" in metric_label.lower():
            return f"Professional services are attached to {current_value}, suggesting onboarding may remain services-heavy as the company scales."
        return "Implementation and onboarding evidence suggests rollout work may remain services-heavy as the company scales."
    if label == "Longer regional health group sales cycles":
        median_sales_cycle = _find_metric_evidence(evidence, "sales cycle")
        if median_sales_cycle:
            _metric, sales_pairs = _table_metric_parts(median_sales_cycle["fact"])
            sales_lookup = {key.lower(): value for key, value in sales_pairs}
            value = sales_lookup.get("current value")
            note = sales_lookup.get("comment") or sales_lookup.get("notes")
            if value and note:
                return f"Regional or larger-account motion may take longer than the median {value}; {note}."
        if comment:
            return comment
    if label == "Missing CAC payback":
        return "CAC payback is not sufficiently supported in the uploaded materials and should be requested from management."
    if label == "Audited financials not provided":
        return "Financial estimates require validation using audited financials or source financial statements."
    if label == "Margin pressure from services-heavy onboarding":
        services = _find_metric_evidence(evidence, "professional services")
        if services:
            _metric, service_pairs = _table_metric_parts(services["fact"])
            service_lookup = {key.lower(): value for key, value in service_pairs}
            value = service_lookup.get("current value")
            note = service_lookup.get("comment") or service_lookup.get("notes")
            if value:
                return f"Professional services are attached to {value}, which may pressure margins if onboarding remains services-heavy."
            if note:
                return note

    if fact.startswith("Table metric "):
        return _strip_terminal_period(_humanize_table_metric(fact, item))
    return fact[:180]


def _find_metric_evidence(evidence: list[dict], label_contains: str) -> dict | None:
    target = label_contains.lower()
    for item in evidence:
        metric_label = _table_metric_label(item["fact"]).lower()
        if target in metric_label:
            return item
    return None


def _section_from_ranked_evidence(
    evidence: list[dict],
    categories: list[str],
    preferred_sources: list[str],
    fallback: str,
) -> str:
    selected = [
        item
        for item in evidence
        if item["category"] in categories and not _is_low_value_evidence(item["fact"])
    ]
    selected = sorted(
        selected,
        key=lambda item: (
            any(source in item["source_document"].lower() for source in preferred_sources),
            item.get("support_level") == "High",
            _evidence_score(item),
        ),
        reverse=True,
    )[:4]
    if not selected:
        return fallback
    return _join_sentences(_render_evidence_sentence(item) for item in selected)


def _compose_market_customer_thesis(evidence: list[dict], revenue_mix: list[str]) -> str:
    parts = []
    if revenue_mix:
        parts.append("Revenue mix evidence indicates " + "; ".join(_strip_terminal_period(item) for item in revenue_mix[:3]) + ".")
    customer_evidence = _section_from_ranked_evidence(
        evidence,
        ["Customer Validation", "GTM"] if revenue_mix else ["Market", "Customer Validation", "GTM"],
        ["pitch", "customer", "metrics"],
        "",
    )
    if customer_evidence:
        parts.append(customer_evidence)
    return " ".join(parts) if parts else "Market and customer thesis requires additional support."


def _compose_financial_section(financial_signals: list[str], revenue_mix: list[str]) -> str:
    parts = []
    if financial_signals:
        parts.append(_join_sentences(financial_signals[:6]))
    if revenue_mix:
        parts.append("Revenue mix: " + "; ".join(_strip_terminal_period(item) for item in revenue_mix[:4]) + ".")
    return " ".join(parts) if parts else "Financial or traction data was not clearly structured in the uploaded materials."


def _compose_competitive_landscape(evidence: list[dict]) -> str:
    text = " ".join(item["fact"] for item in evidence).lower()
    has_competitive_detail = any(token in text for token in ("competitor", "competition", "competitive", "win/loss", "win rate", "pricing comparison"))
    positioning = _section_from_ranked_evidence(
        evidence,
        ["Product", "Market", "Customer Validation"],
        ["pitch", "customer", "manual"],
        "",
    )
    if has_competitive_detail:
        return _section_from_ranked_evidence(
            evidence,
            ["Market", "Risk", "Product"],
            ["pitch", "manual", "customer"],
            "Competitive positioning requires additional support.",
        )
    if positioning:
        return (
            "The uploaded materials do not provide named competitors or detailed win/loss data. "
            f"Based on available evidence, the company appears positioned around {_summarize_positioning_themes(evidence)}. "
            "Competitive diligence should request named competitors, win/loss data, pricing comparisons, and reasons for displacement."
        )
    return (
        "The uploaded materials do not provide enough competitive evidence. Competitive diligence should request named competitors, "
        "win/loss data, pricing comparisons, and reasons for displacement."
    )


def _summarize_positioning_themes(evidence: list[dict]) -> str:
    text = " ".join(item["fact"] for item in evidence).lower()
    themes = []
    for label, keywords in [
        ("workflow visibility", ("visibility", "work queues", "workflow")),
        ("prior authorization tracking", ("prior authorization", "authorization")),
        ("follow-up automation", ("follow-up", "patient engagement")),
        ("referral intake", ("referral intake", "referral")),
        ("multi-site operational standardization", ("multi-site", "multi-location", "standardize")),
        ("implementation support", ("implementation", "onboarding")),
    ]:
        if any(keyword in text for keyword in keywords):
            themes.append(label)
    return ", ".join(themes[:4]) if themes else "the product and customer workflows described in the uploaded materials"


def _financial_signal_sentences(evidence: list[dict]) -> list[str]:
    signals = []
    for item in evidence:
        fact = item["fact"]
        lowered = fact.lower()
        if item["category"] not in {"Financials", "Traction", "Customer Validation"}:
            continue
        if "share of" in lowered or "segment" in lowered:
            continue
        if not any(
            token in lowered
            for token in ("arr", "revenue", "gross margin", "retention", "customers", "acv", "cac", "payback")
        ):
            continue
        if fact.startswith("Table metric "):
            signals.append(_humanize_table_metric(fact, item))
        else:
            signals.append(_fact_with_source(item))
    return _dedupe_preserve_order(signals)


def _revenue_mix_sentences(evidence: list[dict]) -> list[str]:
    mix = []
    for item in evidence:
        fact = item["fact"]
        lowered = fact.lower()
        if "share" in lowered or "segment" in lowered or "revenue mix" in lowered:
            if fact.startswith("Table metric "):
                mix.append(_humanize_table_metric(fact, item))
            else:
                mix.append(_fact_with_source(item))
    return _dedupe_preserve_order(mix)


def _risk_preview(evidence: list[dict]) -> str:
    risks = detect_risks(evidence)[:2]
    if not risks:
        return "The current evidence set does not surface a clear risk profile."
    return "Primary review areas include " + " and ".join(risks) + "."


def _humanize_table_metric(fact: str, item: dict) -> str:
    match = re.match(r"Table metric ([^:]+):\s*(.*)", fact)
    if not match:
        return _fact_with_source(item)
    metric = match.group(1).strip()
    pairs = _metric_pairs(match.group(2))
    qualitative_sentence = _humanize_qualitative_row(metric, pairs)
    if qualitative_sentence:
        return f"{qualitative_sentence} (Source: {item['source_document']})."
    values = [f"{key}={value}" for key, value in pairs]
    share_values = [(key, value) for key, value in pairs if "share" in key.lower()]
    note_values = [(key, value) for key, value in pairs if key.lower() in {"notes", "comment", "current motion", "description", "concern or objection", "positive feedback"}]
    if share_values:
        share_key, share_value = share_values[0]
        sentence = f"{metric} {_plural_verb(metric, 'represent', 'represents')} {share_value}"
        if "arr" in share_key.lower():
            sentence += " of ARR"
        if note_values:
            note_key, note_value = note_values[0]
            sentence += f"; {note_key}: {note_value}"
        return f"{sentence} (Source: {item['source_document']})."
    projection_values = [(key, value) for key, value in pairs if "projection" in key.lower() or "target" in key.lower()]
    historical_values = [(key, value) for key, value in pairs if re.fullmatch(r"20\d{2}", key.strip())]
    if len(historical_values) >= 2:
        start_year, start_value = historical_values[0]
        end_year, end_value = historical_values[-1]
        verb = _metric_trend_verb(metric)
        sentence = f"{metric} {verb} from {start_value} in {start_year} to {end_value} in {end_year}"
        if projection_values:
            projection_label, projection_value = projection_values[-1]
            sentence += f", with {projection_value} marked as {projection_label.lower()}"
    elif any(key.lower() == "current value" for key, _value in pairs):
        current_value = next(value for key, value in pairs if key.lower() == "current value")
        sentence = f"{metric} is {current_value}"
        comments = [value for key, value in pairs if key.lower() in {"comment", "notes"}]
        if comments:
            sentence += f"; {comments[0]}"
    elif note_values and len(note_values) >= 2:
        sentence = f"{metric}: " + "; ".join(f"{key}: {value}" for key, value in note_values[:3])
    elif values:
        sentence = f"{metric}: " + "; ".join(f"{key}: {value}" for key, value in pairs[:4])
    else:
        sentence = metric
    return f"{sentence} (Source: {item['source_document']})."


def _humanize_qualitative_row(metric: str, pairs: list[tuple[str, str]]) -> str:
    lookup = {key.lower(): value for key, value in pairs}
    positive = lookup.get("positive feedback")
    concern = lookup.get("concern or objection")
    description = lookup.get("description")
    current_motion = lookup.get("current motion")
    notes = lookup.get("notes") or lookup.get("comment")

    if positive and concern:
        positive_text = _lower_first(positive).rstrip(".")
        concern_text = _lower_first(concern)
        if positive.lower().startswith(("expansion", "authorization", "follow-up", "centralized", "reporting")):
            return f"Customer notes indicate that {positive_text}, but {concern_text}"
        return f"Customer notes for {metric} indicate that {positive_text}, but {concern_text}"
    if description and current_motion:
        return f"{metric} are described as {description}; current motion is {current_motion}"
    if notes and not any(
        key.lower().startswith("20") or "share" in key.lower() or key.lower() == "current value"
        for key, _value in pairs
    ):
        return f"{metric}: {notes}"
    return ""


def _friendly_subject(label: str) -> str:
    lowered = label.lower()
    if any(token in lowered for token in ("network", "group", "practice", "clinic")):
        return f"{label} customers"
    return label


def _lower_first(value: str) -> str:
    return value[:1].lower() + value[1:] if value else value


def _sector_descriptor(sector_text: str) -> str:
    cleaned = sector_text.strip()
    if not cleaned or cleaned.lower() == "not provided":
        return "the relevant market"
    lowered = cleaned.lower()
    if lowered == "healthcare":
        return "healthcare operations software"
    if lowered in {"fintech", "cybersecurity", "consumer"}:
        return f"the {lowered} market"
    return cleaned


def _plural_verb(subject: str, plural: str, singular: str) -> str:
    lowered = subject.strip().lower()
    if lowered.endswith("s") or any(token in lowered for token in ("clinics", "practices", "groups", "customers")):
        return plural
    return singular


def _metric_pairs(raw_values: str) -> list[tuple[str, str]]:
    pairs = []
    for part in raw_values.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        pairs.append((key.strip(), value.strip()))
    return pairs


def _metric_trend_verb(metric: str) -> str:
    lowered = metric.lower()
    if any(token in lowered for token in ("arr", "revenue", "customer", "acv", "margin", "retention")):
        return "increased"
    return "changed"


def _fact_with_source(item: dict) -> str:
    return f"{item['fact']} (Source: {item['source_document']})."


def _render_evidence_sentence(item: dict) -> str:
    if item["fact"].startswith("Table metric "):
        return _humanize_table_metric(item["fact"], item)
    return _fact_with_source(item)


def _strip_terminal_period(value: str) -> str:
    return value.rstrip().rstrip(".")


def _join_sentences(values) -> str:
    return " ".join(str(value).strip() for value in values if str(value).strip())


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        key = value.lower()
        if key not in seen:
            seen.add(key)
            output.append(value)
    return output


def _build_diligence_questions(evidence: list[dict], missing: list[str]) -> list[str]:
    text = " ".join(item["fact"] for item in evidence).lower()
    questions = []
    if "cac" in text or any("CAC" in item for item in missing):
        questions.append("What is CAC payback by segment, and how does it vary across the core customer segments?")
    if "implementation" in text or "ehr" in text:
        questions.append("How much implementation work is repeatable versus custom for each deployment?")
        questions.append("What percentage of deployments require custom EHR integration or workflow configuration?")
    if "gross margin" in text:
        questions.append("What is gross margin excluding professional services, and what explains the margin bridge over time?")
    if "retention" in text or "churn" in text:
        questions.append("What are logo retention, gross retention, and churn reasons by customer cohort?")
    if "concentration" in text or any("concentration" in item.lower() for item in missing):
        questions.append("What percentage of ARR comes from the top customers, and are any contracts at renewal risk?")
    if "sales cycle" in text or "regional" in text:
        questions.append("How do win rate, sales cycle, and implementation load differ by customer segment?")
    if "competition" in text or "win/loss" in " ".join(missing).lower():
        questions.append("What competitive win/loss data supports the positioning claims?")
    if "market" in text or "segment" in text:
        questions.append("What market size or TAM evidence supports the priority customer segments?")
    targeted_missing_questions = {
        "Audited financials": "Can management provide audited financials or source financial statements supporting the reported metrics?",
        "Implementation margin or services margin": "What is the margin profile of implementation and professional services work?",
        "Detailed churn reasons": "What are the top reasons for churn, non-renewal, or failed expansion by customer segment?",
        "Competitive win/loss data": "Which competitors appear most often in deals, and what are the main win/loss reasons?",
        "Sales efficiency by segment": "How do CAC, sales efficiency, and payback differ by customer segment?",
    }
    for gap in missing:
        if len(questions) >= 10:
            break
        question = targeted_missing_questions.get(gap)
        if question:
            questions.append(question)
    return _dedupe_preserve_order(questions)[:10]


def _document_summary(source: dict) -> str:
    summary = source["summary"]
    table_count = len(source.get("tables") or [])
    if summary == "No extractable summary available." and table_count:
        summary = _table_based_summary(source.get("tables") or [])
    if table_count:
        suffix = f" Extracted {table_count} structured table(s)."
        return f"{summary}{suffix}"[:420]
    return summary


def _table_based_summary(tables: list[dict]) -> str:
    metric_labels = []
    for table in tables:
        for row in table.get("rows") or []:
            label = _row_label(row)
            if label:
                metric_labels.append(label)
            if len(metric_labels) >= 4:
                break
        if len(metric_labels) >= 4:
            break
    if metric_labels:
        return "Extracted structured evidence including " + ", ".join(metric_labels[:4]) + "."
    return "Extracted structured tables for review."


def _row_label(row: dict) -> str:
    for key in ("Metric", "Segment", "Customer type", "Customer segment"):
        if row.get(key):
            return str(row[key])
    return ""


def _clean_extracted_text(text: str) -> str:
    replacements = {
        "(cid:127)": "-",
        "â€¢": "-",
        "\u2022": "-",
        "Â·": "-",
    }
    cleaned = text
    for source, replacement in replacements.items():
        cleaned = cleaned.replace(source, replacement)
    return _compact_whitespace(cleaned)


def _extract_table_evidence(source: dict) -> list[dict]:
    evidence = []
    for table in source.get("tables") or []:
        for row in table.get("rows") or []:
            if not _is_metric_row(row):
                continue
            fact = _format_metric_row(row)
            evidence.append(
                {
                    "fact": fact,
                    "source_document": source["filename"],
                    "category": _categorize_table_fact(row, fact),
                    "support_level": "High",
                    "evidence_type": "table_row",
                    "table_title": table.get("title", "Extracted table"),
                }
            )
    return evidence


def _is_metric_row(row: dict) -> bool:
    text = " ".join([*row.keys(), *(str(value) for value in row.values())]).lower()
    return any(keyword in text for keyword in TABLE_METRIC_KEYWORDS)


def _format_metric_row(row: dict) -> str:
    keys = list(row.keys())
    metric_key = next((key for key in keys if key.lower() in {"metric", "segment", "customer type"}), keys[0] if keys else "Metric")
    metric = str(row.get(metric_key, "Metric")).strip() or "Metric"
    values = []
    for key in keys:
        if key == metric_key:
            continue
        value = str(row.get(key, "")).strip()
        if value:
            values.append(f"{key}={value}")
    return f"Table metric {metric}: {'; '.join(values)}"


def _categorize_table_fact(row: dict, fact: str) -> str:
    keys = " ".join(row.keys()).lower()
    values = " ".join(str(value) for value in row.values()).lower()
    combined = f"{keys} {values} {fact.lower()}"
    if "share of" in combined or "segment" in combined or "customer type" in combined:
        if any(token in combined for token in ("sales cycle", "onboarding", "procurement", "motion")):
            return "GTM"
        return "Market"
    if any(token in combined for token in ("arr", "revenue", "gross margin", "acv", "cac", "payback", "rule of 40")):
        return "Financials"
    if any(token in combined for token in ("retention", "customers", "expansion")):
        return "Customer Validation"
    return categorize_sentence(fact)


def _normalize_table(table: list[list]) -> list[list[str]]:
    normalized = []
    for row in table:
        cells = [_compact_whitespace(str(cell or "")) for cell in row]
        if any(cells):
            normalized.append(cells)

    if not normalized:
        return []

    width = max(len(row) for row in normalized)
    return [row + [""] * (width - len(row)) for row in normalized]


def _table_to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    header = [cell or f"Column {index + 1}" for index, cell in enumerate(rows[0])]
    lines = [
        "| " + " | ".join(_escape_markdown_cell(cell) for cell in header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows[1:]:
        lines.append("| " + " | ".join(_escape_markdown_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def _table_to_rows(rows: list[list[str]]) -> list[dict]:
    if len(rows) < 2:
        return []
    headers = [cell or f"Column {index + 1}" for index, cell in enumerate(rows[0])]
    records = []
    for row in rows[1:]:
        record = {}
        for index, header in enumerate(headers):
            record[header] = row[index] if index < len(row) else ""
        if any(record.values()):
            records.append(record)
    return records


def _combine_text_and_tables(text: str, table_markdowns: list[str]) -> str:
    parts = []
    if text:
        parts.append(text)
    for index, markdown in enumerate(table_markdowns, start=1):
        if markdown:
            parts.append(f"Extracted table {index}:\n{markdown}")
    return _compact_whitespace("\n\n".join(parts))[:24000]


def _is_low_value_evidence(sentence: str) -> bool:
    lowered = sentence.lower()
    blocked_phrases = (
        "fictional demo document",
        "fictional company document",
        "fictional financial",
        "prepared as a text-based pdf",
        "prepared for extraction",
        "intended to test extraction",
        "this document summarizes",
        "document type:",
        "page 1",
        "page 2",
        "memo pilot demo",
    )
    if any(phrase in lowered for phrase in blocked_phrases):
        return True
    if re.fullmatch(r"[\w\s/|:$%.,-]{1,120}", sentence) and lowered.count(" ") < 4:
        return True
    return False


def _looks_like_broken_table_fragment(sentence: str, source: dict) -> bool:
    if not source.get("tables"):
        return False
    lowered = sentence.lower()
    table_tokens = (" metric ", " positive feedback ", " concern or objection ", " current value ", " share of ")
    long_numeric_fragment = len(re.findall(r"20\d{2}|\$|\d+%", sentence)) >= 3
    return any(token in f" {lowered} " for token in table_tokens) or long_numeric_fragment


def _evidence_score(item: dict) -> int:
    fact = item["fact"].lower()
    source = item["source_document"].lower()
    score = 0
    if item.get("evidence_type") == "table_row":
        score += 40
    if item.get("support_level") == "High":
        score += 20
    if "metrics" in source or "financial" in source:
        score += 18
    if "pitch" in source or "deck" in source:
        score += 12
    if "customer" in source:
        score += 10
    if "manual" in source:
        score += 8
    if any(token in fact for token in ("arr", "revenue", "gross margin", "retention", "customer", "segment", "sales cycle", "concentration", "implementation", "risk", "missing")):
        score += 12
    if _is_low_value_evidence(item["fact"]):
        score -= 80
    return score


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").strip()


def _parse_money_value(value: str) -> int | None:
    cleaned = value.lower().replace("$", "").replace(",", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s?(m|mm|million|k)?", cleaned)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2) or ""
    if unit in {"m", "mm", "million"}:
        amount *= 1_000_000
    elif unit == "k":
        amount *= 1_000
    return int(amount)


def _stage(name: str, status: str, summary: str) -> dict:
    return {"name": name, "status": status, "summary": summary}


def _text_extraction_summary(documents: list[dict], manual_notes: str) -> str:
    extracted = sum(1 for document in documents if document["extraction_status"] != "no extractable text")
    note = " Manual notes included." if manual_notes.strip() else ""
    return f"Deterministic PDF parser extracted usable text and tables from {extracted}/{len(documents)} uploaded document(s).{note}"


def _sentences(text: str) -> list[str]:
    cleaned = _clean_extracted_text(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    return [part.strip(" -•\t") for part in parts if 35 <= len(part.strip()) <= 420]


def _compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _looks_like_text(value: str) -> bool:
    if len(value) < 3:
        return False
    letters = sum(character.isalpha() for character in value)
    return letters / max(len(value), 1) > 0.45
