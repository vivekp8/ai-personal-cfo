"""Statement ingestion: parse, clean, and validate bank-statement rows.

Accepts many file formats and normalises them to a clean list of
``{date, description, amount}`` dicts:

- CSV / TXT / TSV / any delimited text (delimiter is auto-sniffed)
- Excel: .xlsx (openpyxl) and legacy .xls (xlrd)
- OpenDocument spreadsheets: .ods (odf) when available
- JSON: array of records or {"transactions": [...]}
- PDF: tabular bank statements (pdfplumber) when available

Row-level cleaning handles:
- +/- signs on amounts, Dr/Cr suffixes, parentheses for negatives
- comma / space grouped amounts (e.g. "+50,000")
- currency symbols (Rs, INR, ₹, $, etc.)
- many date formats (DD-MM-YYYY, ISO, etc.), day-first by default
"""
from __future__ import annotations

import io
import json
import logging
import re
import time
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger("agents.ingestion")

# Columns we will try to map, case-insensitive.
_DATE_KEYS = {"date", "txn date", "transaction date", "value date", "posting date"}
_DESC_KEYS = {
    "description",
    "desc",
    "narration",
    "particulars",
    "details",
    "merchant",
    "remarks",
    "transaction details",
}
_AMT_KEYS = {"amount", "amt", "value", "transaction amount"}
# Separate debit/credit columns are common in Indian bank exports.
_DEBIT_KEYS = {"debit", "withdrawal", "withdrawal amt", "dr", "debit amount", "paid out"}
_CREDIT_KEYS = {"credit", "deposit", "deposit amt", "cr", "credit amount", "paid in"}

_DATE_FORMATS = [
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%y",
    "%d/%m/%y",
    "%m/%d/%Y",
    "%d-%b-%Y",
    "%d %b %Y",
    "%d-%B-%Y",
    "%d %B %Y",
    "%Y/%m/%d",
]


class IngestionError(Exception):
    """Raised when a file cannot be parsed into valid transactions."""


def _find_column(columns: list[str], candidates: set[str]) -> str | None:
    lowered = {str(c).lower().strip(): c for c in columns}
    for cand in candidates:
        if cand in lowered:
            return lowered[cand]
    # fuzzy contains
    for low, original in lowered.items():
        if any(cand in low for cand in candidates):
            return original
    return None


def _parse_amount(raw: Any) -> tuple[float, str]:
    if raw is None:
        raise ValueError("empty amount")
    s = str(raw).strip()
    if s == "" or s.lower() in {"nan", "none"}:
        raise ValueError("empty amount")
    
    # Detect sign
    sign = 1.0
    low = s.lower()
    if s.startswith("-") or s.startswith("(") or low.endswith("dr") or " dr" in low:
        sign = -1.0
    if s.startswith("+") or low.endswith("cr") or " cr" in low:
        sign = 1.0
        
    # Extract currency symbol
    currency = "Rs." # default
    currency_match = re.search(r'([$€£¥₹]|Rs\.?|INR|USD|EUR|GBP)', s, re.IGNORECASE)
    if currency_match:
        currency = currency_match.group(1).upper()
        if currency.startswith("RS"):
            currency = "Rs."
        elif currency == "INR":
            currency = "Rs."
        elif currency == "₹":
            currency = "Rs."
            
    # Clean string to only numbers, commas, and dots
    cleaned = re.sub(r"[^\d.,]", "", s)
    if cleaned == "":
        raise ValueError(f"no numeric value in amount: {raw!r}")
        
    # Handle European vs US formatting
    if "," in cleaned and "." in cleaned:
        last_comma = cleaned.rfind(",")
        last_dot = cleaned.rfind(".")
        if last_comma > last_dot:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
            
    if cleaned.count(".") > 1:
        parts = cleaned.split(".")
        cleaned = "".join(parts[:-1]) + "." + parts[-1]
        
    return sign * float(cleaned), currency


def _parse_date(raw: Any) -> str:
    s = str(raw).strip()
    # pandas Timestamp / datetime coming from Excel cells
    if isinstance(raw, (pd.Timestamp, datetime)):
        return pd.Timestamp(raw).strftime("%Y-%m-%d")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # last resort: let pandas try (dayfirst for Indian statements)
    try:
        return pd.to_datetime(s, dayfirst=True).strftime("%Y-%m-%d")
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"unparseable date: {raw!r}") from exc


def _dataframe_to_transactions(df: pd.DataFrame) -> list[dict]:
    """Map an arbitrary statement DataFrame to clean transactions."""
    if df is None or df.empty:
        raise IngestionError("The file contains no rows.")

    # Drop fully-empty columns/rows that spreadsheets often carry.
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    cols = list(df.columns)

    date_col = _find_column(cols, _DATE_KEYS)
    desc_col = _find_column(cols, _DESC_KEYS)
    amt_col = _find_column(cols, _AMT_KEYS)
    debit_col = _find_column(cols, _DEBIT_KEYS)
    credit_col = _find_column(cols, _CREDIT_KEYS)

    has_amount = amt_col is not None
    has_split = debit_col is not None or credit_col is not None

    missing = []
    if date_col is None:
        missing.append("date")
    if desc_col is None:
        missing.append("description")
    if not has_amount and not has_split:
        missing.append("amount (or debit/credit)")
    if missing:
        raise IngestionError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Found columns: {', '.join(cols) or '(none)'}"
        )

    transactions: list[dict] = []
    errors: list[str] = []
    for idx, row in df.iterrows():
        try:
            date = _parse_date(row[date_col])
            desc = str(row[desc_col]).strip()
            if desc == "" or desc.lower() == "nan":
                raise ValueError("empty description")

            currency = "Rs."
            if has_amount:
                amount, currency = _parse_amount(row[amt_col])
                raw_amt = str(row[amt_col]).strip().lower()
                if amount > 0 and not raw_amt.startswith("+") and not raw_amt.endswith("cr") and " cr" not in raw_amt:
                    desc_low = desc.lower()
                    is_credit = any(h in desc_low for h in _CREDIT_HINTS)
                    if not is_credit:
                        amount = -amount
            else:
                # Combine debit (negative) and credit (positive) columns.
                debit = 0.0
                credit = 0.0
                if debit_col is not None:
                    try:
                        parsed = _parse_amount(row[debit_col])
                        debit = abs(parsed[0])
                        currency = parsed[1]
                    except ValueError:
                        debit = 0.0
                if credit_col is not None:
                    try:
                        parsed = _parse_amount(row[credit_col])
                        credit = abs(parsed[0])
                        currency = parsed[1]
                    except ValueError:
                        credit = 0.0
                if debit == 0.0 and credit == 0.0:
                    raise ValueError("no debit/credit value")
                amount = credit - debit
                
            # Extract payment method
            desc_low = desc.lower()
            payment_method = "Other"
            for pm in ["upi", "neft", "imps", "rtgs", "pos", "atm", "cash"]:
                if pm in desc_low:
                    payment_method = pm.upper()
                    break

            transactions.append({"date": date, "description": desc, "amount": amount, "currency": currency, "payment_method": payment_method})
        except ValueError as exc:
            errors.append(f"row {idx + 2}: {exc}")
            continue

    if not transactions:
        raise IngestionError(
            "No valid transactions found. Sample errors: " + "; ".join(errors[:5])
        )

    transactions.sort(key=lambda t: t["date"])
    return transactions


# ---------- format-specific readers ----------
def _decode_text(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    # last resort: detect
    try:
        import chardet

        guess = chardet.detect(content).get("encoding") or "utf-8"
        return content.decode(guess, errors="replace")
    except Exception:  # noqa: BLE001
        return content.decode("utf-8", errors="replace")


def _read_delimited(content: bytes | str) -> pd.DataFrame:
    text = _decode_text(content) if isinstance(content, bytes) else content
    # Sniff the delimiter from the first non-empty line.
    sample_lines = [ln for ln in text.splitlines() if ln.strip()][:5]
    sample = "\n".join(sample_lines)
    delimiter = ","
    if sample:
        counts = {d: sample.count(d) for d in [",", "\t", ";", "|"]}
        delimiter = max(counts, key=counts.get) if max(counts.values()) > 0 else ","
    try:
        return pd.read_csv(io.StringIO(text), sep=delimiter, engine="python", skip_blank_lines=True)
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Could not read delimited text: {exc}") from exc


def _read_excel(content: bytes, engine: str | None = None) -> pd.DataFrame:
    try:
        return pd.read_excel(io.BytesIO(content), engine=engine)
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(
            f"Could not read spreadsheet: {exc}. "
            "Make sure the file is a valid Excel/ODS workbook."
        ) from exc


def _read_json(content: bytes | str) -> pd.DataFrame:
    text = _decode_text(content) if isinstance(content, bytes) else content
    try:
        data = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Invalid JSON: {exc}") from exc
    if isinstance(data, dict):
        for key in ("transactions", "data", "rows", "records"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise IngestionError("JSON must be an array of transaction objects.")
    return pd.DataFrame(data)


# Date at the start of a statement line: 01-01-2025, 1/1/25, 2025-01-01, 01 Jan 2025, 01-Jan-2025
_LINE_DATE_RE = re.compile(
    r"^\s*("
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"           # 2025-01-01
    r"|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"          # 01-01-2025 / 1/1/25
    r"|\d{1,2}[-\s][A-Za-z]{3,9}[-\s]\d{2,4}"  # 01 Jan 2025 / 01-Jan-2025
    r")"
)
# A monetary token with 2 decimals, optional grouping, sign, parens and Dr/Cr.
_MONEY_RE = re.compile(
    r"(\(?\s*[-+]?\d+(?:,\d{2,3})*(?:\.\d{1,2})\s*\)?)\s*(cr|dr)?",
    re.IGNORECASE,
)
# Fallback: integer amounts (no decimals) with optional grouping / Dr-Cr.
_MONEY_INT_RE = re.compile(
    r"(\(?\s*[-+]?\d+(?:,\d{2,3})+\s*\)?|\(?\s*[-+]?\d{3,}\s*\)?)\s*(cr|dr)?",
    re.IGNORECASE,
)
_CREDIT_HINTS = (
    "salary",
    "credit",
    "deposit",
    "refund",
    "cashback",
    "interest",
    "neft cr",
    "imps cr",
    "received",
    "reversal",
)


def _pdf_extract_text(pdf) -> str:
    """Fast path: pull text from every page (cheap in pdfplumber)."""
    parts: list[str] = []
    for page in pdf.pages:
        txt = page.extract_text() or ""
        if txt:
            parts.append(txt)
    return "\n".join(parts)


def _pdf_extract_tables(pdf) -> list:
    """Slow path: table detection per page. Only call when text parsing fails."""
    tables: list = []
    for page in pdf.pages:
        for table in page.extract_tables() or []:
            if table:
                tables.append(table)
    return tables


def _tables_to_df(tables: list) -> pd.DataFrame | None:
    header: list[str] | None = None
    rows: list[list[str]] = []
    for table in tables:
        if not table:
            continue
        if header is None:
            header = [str(c or "").strip() for c in table[0]]
            body = table[1:]
        else:
            body = table
        for r in body:
            rows.append([str(c or "").strip() for c in r])
    if not header or not rows:
        return None
    width = len(header)
    norm = [r[:width] + [""] * (width - len(r)) for r in rows]
    df = pd.DataFrame(norm, columns=header)
    # Only trust the table path if it actually has the columns we need.
    cols = [str(c) for c in df.columns]
    if _find_column(cols, _DATE_KEYS) and (
        _find_column(cols, _AMT_KEYS)
        or _find_column(cols, _DEBIT_KEYS)
        or _find_column(cols, _CREDIT_KEYS)
    ):
        return df
    return None


def _amount_from_line(rest: str, description: str) -> float | None:
    """Pick the transaction amount from the non-date part of a statement line."""
    matches = list(_MONEY_RE.finditer(rest)) or list(_MONEY_INT_RE.finditer(rest))
    if not matches:
        return None

    def to_value(m: re.Match) -> tuple[float, str | None]:
        token = m.group(1).strip()
        marker = (m.group(2) or "").lower() or None
        neg = token.startswith("(") or token.startswith("-")
        num = re.sub(r"[^\d.]", "", token)
        if num == "" or num == ".":
            return 0.0, marker
        try:
            val = float(num)
        except ValueError:
            return 0.0, marker
        return (-val if neg else val), marker

    # Prefer a token explicitly tagged Dr/Cr — that's the transaction amount,
    # not the running balance.
    for m in matches:
        val, marker = to_value(m)
        if marker == "dr":
            return -abs(val)
        if marker == "cr":
            return abs(val)

    # No Dr/Cr marker: assume [amount, balance, ...]; take the first number.
    val, _ = to_value(matches[0])
    if val == 0.0:
        return None
    if val > 0:
        desc_low = description.lower()
        is_credit = any(h in desc_low for h in _CREDIT_HINTS)
        return abs(val) if is_credit else -abs(val)
    return val


def _parse_pdf_text(text: str) -> list[dict]:
    """Heuristic line-by-line parser for text-based statement PDFs."""
    transactions: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        dm = _LINE_DATE_RE.match(line)
        if not dm:
            continue
        try:
            date = _parse_date(dm.group(1))
        except ValueError:
            continue
        rest = line[dm.end():].strip(" -|\t")
        money = list(_MONEY_RE.finditer(rest)) or list(_MONEY_INT_RE.finditer(rest))
        if not money:
            continue
        description = rest[: money[0].start()].strip(" -|\t")
        if not description:
            continue
        amount = _amount_from_line(rest, description)
        if amount is None or amount == 0.0:
            continue
        transactions.append(
            {"date": date, "description": description, "amount": amount}
        )
    transactions.sort(key=lambda t: t["date"])
    return transactions


def _llm_extract_transactions(text: str) -> list[dict]:
    """Last-resort: ask the configured LLM to transcribe transactions to JSON.

    This only transcribes what is written in the document; all downstream
    financial figures (score, forecast, what-if) remain deterministic.
    """
    try:
        from agents import llm_client
    except Exception:  # noqa: BLE001
        return []
    if not llm_client.is_configured():
        return []

    # Chunk the text to avoid LLM output token limits on massive statements
    # Use 15000 chars (~4k tokens) so it safely fits in ANY model's context window 
    # (even 8k models on Groq/Ollama) to ensure no chunks are rejected.
    chunk_size = 15000
    lines = text.splitlines()
    chunks = []
    current_chunk = []
    current_len = 0
    for line in lines:
        if current_len + len(line) > chunk_size and current_chunk:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_len = 0
        current_chunk.append(line)
        current_len += len(line) + 1
    if current_chunk:
        chunks.append("\n".join(current_chunk))

    out: list[dict] = []
    
    for snippet in chunks:
        if not snippet.strip():
            continue
        prompt = (
            "You are a precise bank-statement parser. Extract EVERY transaction from "
            "the statement text below into a JSON array. Each element must be exactly:\n"
            '{"date": "YYYY-MM-DD", "description": "string", "amount": number, "category": "string", "currency": "string", "payment_method": "string"}\n'
            "Rules: amount is NEGATIVE for debits/withdrawals/payments and POSITIVE "
            "for credits/deposits/salary. Do NOT include running balances as amounts. "
            "For category, create a short, logical category (e.g., Groceries, Food, Transfer, Utilities, Salary) "
            "based on the description. "
            "Extract 'currency' symbol (e.g. $, €, Rs.). "
            "Extract 'payment_method' if obvious (UPI, NEFT, IMPS, POS, CASH), otherwise 'Other'. "
            "Copy figures exactly as printed; never invent values. Return ONLY the JSON "
            "array, nothing else.\n\nSTATEMENT TEXT:\n" + snippet
        )
        raw = llm_client.generate(prompt)
        if not raw or raw.startswith("[LLM error"):
            raise IngestionError(f"LLM extraction failed: {raw}")
            
        data = []
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
            except Exception:
                pass
                
        if not data:
            # Fallback for truncated/broken JSON
            objs = re.findall(r'\{[^{}]+\}', raw)
            for o in objs:
                try:
                    data.append(json.loads(o))
                except Exception:
                    pass

        for item in data if isinstance(data, list) else []:
            if not isinstance(item, dict):
                continue
            try:
                date = _parse_date(item.get("date"))
                amount, currency = _parse_amount(item.get("amount"))
                desc = str(item.get("description", "")).strip()
                cat = str(item.get("category", "")).strip()
                pm = str(item.get("payment_method", "Other")).strip()
                llm_currency = str(item.get("currency", "")).strip()
                if llm_currency:
                    currency = llm_currency
            except (ValueError, TypeError):
                continue
            if desc:
                out.append({
                    "date": date, 
                    "description": desc, 
                    "amount": amount, 
                    "currency": currency,
                    "payment_method": pm,
                    "category": cat or "Uncategorized"
                })

    out.sort(key=lambda t: t["date"])
    return out


def _parse_pdf(content: bytes) -> list[dict]:
    """Parse a PDF statement fast-first: cheap text extraction and heuristic
    line parsing, then (only if that fails) expensive table detection, then an
    optional LLM fallback. The PDF is opened once and reused.
    """
    try:
        import pdfplumber
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(
            "PDF support requires pdfplumber. Run: pip install pdfplumber"
        ) from exc

    started = time.perf_counter()
    text = ""
    df: pd.DataFrame | None = None
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page_count = len(pdf.pages)
            
            # 1) PRIMARY PATH: structured table detection
            logger.info("Trying PDF table detection (slow but accurate)...")
            tables = _pdf_extract_tables(pdf)
            df = _tables_to_df(tables)
            if df is not None:
                try:
                    txns = _dataframe_to_transactions(df)
                    if len(txns) > 0:
                        logger.info(
                            "PDF parsed via tables in %.0fms (%d txns)",
                            (time.perf_counter() - started) * 1000, len(txns),
                        )
                        return txns
                except IngestionError:
                    pass

            # 2) FAST TEXT PATH: text extraction + heuristic line parsing
            logger.info("Table detection insufficient; trying text heuristics...")
            text = _pdf_extract_text(pdf)
            if text.strip():
                txns = _parse_pdf_text(text)
                # Only trust it if we found a reasonable number of transactions
                if len(txns) >= max(3, page_count):
                    logger.info(
                        "PDF parsed via text in %.0fms (%d pages, %d txns)",
                        (time.perf_counter() - started) * 1000, page_count, len(txns),
                    )
                    return txns

    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Could not read the PDF: {exc}") from exc

    # 3) LLM-assisted extraction for irregular layouts (network — last resort).
    if text.strip():
        txns = _llm_extract_transactions(text)
        if txns:
            logger.info(
                "PDF parsed via LLM in %.0fms (%d txns)",
                (time.perf_counter() - started) * 1000, len(txns),
            )
            return txns

        raise IngestionError(
            "This PDF's layout couldn't be parsed automatically. It may use an "
            "unusual format. Please export your statement as CSV or Excel, or "
            "configure an LLM provider for smarter PDF extraction."
        )

    raise IngestionError(
        "No readable text found in the PDF — it looks like a scanned image. "
        "Scanned statements need OCR; please upload a text-based PDF, CSV, or Excel file."
    )


# ---------- public entry points ----------
def parse_statement(content: bytes | str, filename: str | None = None) -> list[dict]:
    """Parse a statement of any supported format into clean transactions.

    Dispatches on the file extension; falls back to delimited-text parsing when
    the extension is unknown.
    """
    name = (filename or "").lower().strip()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""

    # PDF returns transactions directly (tables/text/LLM layered internally).
    if ext == "pdf":
        if isinstance(content, str):
            raise IngestionError("PDF must be uploaded as binary, not text.")
        return _parse_pdf(content)

    if ext in {"xlsx", "xlsm"}:
        df = _read_excel(content if isinstance(content, bytes) else content.encode(), "openpyxl")
    elif ext == "xls":
        df = _read_excel(content if isinstance(content, bytes) else content.encode(), "xlrd")
    elif ext == "ods":
        df = _read_excel(content if isinstance(content, bytes) else content.encode(), "odf")
    elif ext == "json":
        df = _read_json(content)
    elif ext in {"csv", "tsv", "txt", ""}:
        df = _read_delimited(content)
    else:
        # Unknown extension: best-effort as delimited text.
        df = _read_delimited(content)

    return _dataframe_to_transactions(df)


def parse_csv(content: bytes | str) -> list[dict]:
    """Backward-compatible CSV entry point (delegates to parse_statement)."""
    return parse_statement(content, filename="upload.csv")
