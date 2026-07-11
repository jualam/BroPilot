import io
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone


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
    ("Market Research", ("market", "tam", "sam", "competition", "segment")),
    ("Product Overview", ("product", "platform", "workflow", "feature", "integration")),
    ("Sales/GTM Notes", ("sales", "pipeline", "gtm", "go-to-market", "quota", "conversion")),
]

CATEGORY_KEYWORDS = {
    "Traction": ("arr", "revenue", "growth", "retention", "customer", "pipeline"),
    "Product": ("product", "platform", "workflow", "feature", "integration"),
    "Market": ("market", "tam", "sam", "segment", "industry"),
    "GTM": ("sales", "gtm", "go-to-market", "pipeline", "conversion"),
    "Risk": ("risk", "churn", "dependency", "competition", "burn", "delay"),
}

RISK_KEYWORDS = {
    "Customer concentration or retention risk": ("churn", "retention", "renewal", "concentration"),
    "Execution or implementation risk": ("implementation", "delay", "onboarding", "migration"),
    "Competitive pressure": ("competition", "competitor", "crowded", "pricing pressure"),
    "Financial visibility risk": ("burn", "runway", "margin", "cash", "forecast"),
    "Evidence quality risk": ("assume", "unclear", "missing", "not provided"),
}


def generate_memo_pilot_response(
    *,
    documents: list[dict],
    manual_notes: str,
    company_name: str,
    sector: str,
) -> dict:
    stages = []
    stages.append(_stage("Document Intake", "completed", f"Received {len(documents)} document(s) and manual notes."))

    processed_documents = []
    all_sources = []
    for document in documents:
        extracted_text, status = extract_pdf_text(document["content"])
        source = {
            "filename": document["filename"],
            "text": extracted_text,
            "document_type": detect_document_type(extracted_text, document["filename"]),
            "extraction_status": status,
            "summary": summarize_text(extracted_text) if extracted_text else "No extractable text found.",
        }
        processed_documents.append(
            {
                "filename": source["filename"],
                "document_type": source["document_type"],
                "extraction_status": source["extraction_status"],
                "summary": source["summary"],
            }
        )
        all_sources.append(source)

    if manual_notes.strip():
        all_sources.append(
            {
                "filename": "Manual notes",
                "text": manual_notes.strip(),
                "document_type": "Manual Notes",
                "extraction_status": "provided",
                "summary": summarize_text(manual_notes),
            }
        )

    stages.append(_stage("Text Extraction", "completed", _text_extraction_summary(processed_documents, manual_notes)))

    evidence = extract_evidence(all_sources)
    stages.append(_stage("Evidence Extraction", "completed", f"Extracted {len(evidence)} evidence item(s) with source names."))

    memo_plan = plan_memo(evidence, company_name, sector)
    stages.append(_stage("Memo Planner", "completed", "Mapped evidence into diligence memo sections."))

    memo = draft_memo(evidence, memo_plan, company_name, sector)
    stages.append(_stage("Draft Generator", "completed", "Generated a review-ready diligence memo draft."))

    memo["key_risks"] = detect_risks(evidence)
    stages.append(_stage("Risk Checker", "completed", f"Identified {len(memo['key_risks'])} risk or assumption item(s)."))

    memo["missing_evidence"], memo["diligence_questions"] = review_evidence_gaps(evidence)
    stages.append(_stage("Evidence Gap Review", "completed", "Separated unsupported areas into missing evidence and diligence questions."))

    memo["reviewer_notes"] = reviewer_notes(evidence, processed_documents)
    artifact_markdown = build_markdown_artifact(memo, evidence, company_name, sector)
    stages.append(_stage("Human Review Artifact", "completed", "Packaged markdown, evidence appendix, and reviewer notes."))

    return {
        "documents": processed_documents,
        "evidence": evidence,
        "stages": stages,
        "memo": memo,
        "charts": build_charts(evidence, memo),
        "artifact_markdown": artifact_markdown,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def extract_pdf_text(content: bytes) -> tuple[str, str]:
    pypdf_text = _extract_with_pypdf(content)
    if pypdf_text:
        return _compact_whitespace(pypdf_text), "text extracted"

    fallback_text = _extract_pdf_text_fallback(content)
    if fallback_text:
        return fallback_text, "limited text extracted"

    return "", "no extractable text"


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
    sentences = _sentences(text)
    if not sentences:
        return "No extractable summary available."
    return _compact_whitespace(" ".join(sentences[:2]))[:320]


def extract_evidence(sources: list[dict]) -> list[dict]:
    evidence = []
    seen = set()
    for source in sources:
        for sentence in _sentences(source["text"])[:80]:
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
                }
            )
            if len(evidence) >= 36:
                return evidence

    return evidence


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
    category_counts = Counter(item["category"] for item in evidence)
    top_categories = ", ".join(category for category, _ in category_counts.most_common(3)) or "limited extracted evidence"

    return {
        "executive_summary": (
            f"{name} has been summarized as a review-ready diligence draft using uploaded documents "
            f"and notes. The strongest extracted evidence clusters around {top_categories}. "
            "This draft does not make an investment recommendation."
        ),
        "company_overview": _section_from_evidence(evidence, ["General", "Product"], f"{name} operates in {sector_text}."),
        "product_value_proposition": _section_from_evidence(evidence, ["Product"], "Product evidence is limited in the uploaded materials."),
        "market_customer_thesis": _section_from_evidence(evidence, ["Market", "Traction"], "Market and customer thesis requires additional support."),
        "traction_financial_signals": _section_from_evidence(evidence, ["Traction"], "Financial or traction data was not clearly structured in the uploaded materials."),
        "gtm_motion": _section_from_evidence(evidence, ["GTM"], "Go-to-market motion requires additional evidence."),
        "competitive_landscape": _section_from_evidence(evidence, ["Market", "Risk"], "Competitive positioning requires additional support."),
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
    categories = {item["category"] for item in evidence}
    missing = []
    questions = []
    expected = {
        "Traction": "Recent ARR/revenue, retention, growth rate, and customer cohort data",
        "GTM": "Pipeline conversion, sales cycle, CAC, and repeatable GTM motion",
        "Market": "Market sizing, customer segmentation, and competitive differentiation",
        "Product": "Product architecture, onboarding flow, and implementation complexity",
    }
    for category, gap in expected.items():
        if category not in categories:
            missing.append(gap)
            questions.append(f"What evidence supports the {category.lower()} thesis?")

    if not missing:
        missing.append("Management references or source documents for the most important claims")
    if not questions:
        questions.append("Which claims should be validated directly with customers or management?")
    return missing[:6], questions[:8]


def reviewer_notes(evidence: list[dict], documents: list[dict]) -> list[str]:
    notes = [
        "Human review required before use in any investment process.",
        "Facts are limited to uploaded documents and manual notes.",
    ]
    if any(document["extraction_status"] != "text extracted" for document in documents):
        notes.append("Some documents had limited extraction; scanned PDFs may require OCR.")
    if not evidence:
        notes.append("No strong evidence was extracted; memo should be treated as a shell draft.")
    return notes


def build_charts(evidence: list[dict], memo: dict) -> dict:
    return {
        "arr_growth": extract_arr_growth(evidence),
        "evidence_completeness": evidence_completeness(evidence),
        "risk_priority": [
            {"risk": risk, "score": max(45, 90 - index * 12)}
            for index, risk in enumerate(memo["key_risks"][:5])
        ],
    }


def extract_arr_growth(evidence: list[dict]) -> list[dict]:
    points = {}
    pattern = re.compile(r"(20\d{2}).{0,40}?\$?\s?(\d+(?:\.\d+)?)\s?(m|mm|million)?", re.I)
    for item in evidence:
        for year, value, unit in pattern.findall(item["fact"]):
            arr = float(value)
            if unit.lower() in {"m", "mm", "million"}:
                arr *= 1_000_000
            points[year] = int(arr)
    return [{"year": year, "arr": arr} for year, arr in sorted(points.items())]


def evidence_completeness(evidence: list[dict]) -> list[dict]:
    counts = Counter(item["category"] for item in evidence)
    categories = ["Product", "Market", "Traction", "GTM", "Risk"]
    return [
        {"category": category, "score": min(100, counts.get(category, 0) * 20)}
        for category in categories
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


def _stage(name: str, status: str, summary: str) -> dict:
    return {"name": name, "status": status, "summary": summary}


def _text_extraction_summary(documents: list[dict], manual_notes: str) -> str:
    extracted = sum(1 for document in documents if document["extraction_status"] != "no extractable text")
    note = " Manual notes included." if manual_notes.strip() else ""
    return f"Extracted usable text from {extracted}/{len(documents)} uploaded document(s).{note}"


def _sentences(text: str) -> list[str]:
    cleaned = _compact_whitespace(text)
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
