from __future__ import annotations

import json
import logging
import os
import re
import secrets
import threading
import time
import unicodedata
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Request
from fastapi.responses import JSONResponse

from .env import load_server_env

load_server_env()
logger = logging.getLogger("text_to_speech_service")

LANGUAGES = {
    "vn": "Vietnamese",
    "en": "English",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "es": "Spanish",
}

_VIETNAMESE_DIGITS = (
    "không",
    "một",
    "hai",
    "ba",
    "bốn",
    "năm",
    "sáu",
    "bảy",
    "tám",
    "chín",
)
_VIETNAMESE_SCALES = (
    "",
    "nghìn",
    "triệu",
    "tỷ",
    "nghìn tỷ",
    "triệu tỷ",
    "tỷ tỷ",
)
_NUMBER_PATTERN = re.compile(r"(?<![\w])([+-]?\d+(?:[.,]\d+)*)(?![\w])")
_DATE_DMY_PATTERN = re.compile(
    r"(?<!\w)(?:ngày\s+)?(?P<day>\d{1,2})[./-](?P<month>\d{1,2})[./-](?P<year>\d{4})(?!\d)",
    re.IGNORECASE,
)
_DATE_YMD_PATTERN = re.compile(
    r"(?<!\w)(?:ngày\s+)?(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})(?!\d)",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_URL_PATTERN = re.compile(r"\b(?:https?://|www\.)[^\s<>()]+", re.IGNORECASE)

_CURRENCY_NAMES = {
    "₫": "đồng",
    "đ": "đồng",
    "vnd": "đồng Việt Nam",
    "vnđ": "đồng Việt Nam",
    "$": "đô la Mỹ",
    "usd": "đô la Mỹ",
    "€": "ơ rô",
    "eur": "ơ rô",
    "£": "bảng Anh",
    "gbp": "bảng Anh",
    "¥": "yên Nhật",
    "jpy": "yên Nhật",
    "cny": "nhân dân tệ",
}
_CURRENCY_TOKEN = r"(?:VNĐ|VND|USD|EUR|GBP|JPY|CNY|[₫đ$€£¥])"
_AMOUNT_TOKEN = r"[+-]?\d+(?:[.,]\d+)*"
_CURRENCY_BEFORE_PATTERN = re.compile(
    rf"(?<!\w)(?P<currency>{_CURRENCY_TOKEN})\s*(?P<amount>{_AMOUNT_TOKEN})(?!\w)",
    re.IGNORECASE,
)
_CURRENCY_AFTER_PATTERN = re.compile(
    rf"(?<!\w)(?P<amount>{_AMOUNT_TOKEN})\s*(?P<currency>{_CURRENCY_TOKEN})(?!\w)",
    re.IGNORECASE,
)

_VIETNAMESE_UNITS = {
    "km/h": "ki lô mét trên giờ",
    "km²": "ki lô mét vuông",
    "m²": "mét vuông",
    "km": "ki lô mét",
    "cm": "xen ti mét",
    "mm": "mi li mét",
    "kg": "ki lô gam",
    "mg": "mi li gam",
    "g": "gam",
    "m": "mét",
    "gb": "ghi ga bai",
    "mb": "mê ga bai",
    "kb": "ki lô bai",
    "°c": "độ xê",
    "°f": "độ ép",
}
_UNIT_TOKEN = "|".join(
    re.escape(unit) for unit in sorted(_VIETNAMESE_UNITS, key=len, reverse=True)
)
_VIETNAMESE_UNIT_PATTERN = re.compile(
    rf"(?<!\w)(?P<amount>{_AMOUNT_TOKEN})\s*(?P<unit>{_UNIT_TOKEN})(?!\w)",
    re.IGNORECASE,
)

_VIETNAMESE_ABBREVIATIONS = {
    "TP.HCM": "thành phố Hồ Chí Minh",
    "TPHCM": "thành phố Hồ Chí Minh",
    "TP HCM": "thành phố Hồ Chí Minh",
    "PGS.TS": "phó giáo sư tiến sĩ",
    "GS.TS": "giáo sư tiến sĩ",
    "TS.BS": "tiến sĩ bác sĩ",
    "QĐ": "quyết định",
    "ÂL": "âm lịch",
    "UBND": "ủy ban nhân dân",
    "HĐND": "hội đồng nhân dân",
    "BHXH": "bảo hiểm xã hội",
    "BHYT": "bảo hiểm y tế",
    "CNTT": "công nghệ thông tin",
    "CCCD": "căn cước công dân",
    "CMND": "chứng minh nhân dân",
    "THPT": "trung học phổ thông",
    "THCS": "trung học cơ sở",
    "NXB": "nhà xuất bản",
    "PGS": "phó giáo sư",
    "GS": "giáo sư",
    "TS": "tiến sĩ",
    "THS": "thạc sĩ",
    "BS": "bác sĩ",
    "KS": "kỹ sư",
    "ĐH": "đại học",
    "ĐT": "điện thoại",
    "TP.": "thành phố",
    "AI": "trí tuệ nhân tạo",
    "TTS": "chuyển văn bản thành giọng nói",
    "API": "giao diện lập trình ứng dụng",
    "URL": "địa chỉ liên kết",
    "SMS": "tin nhắn",
    "GDP": "tổng sản phẩm quốc nội",
    "VAT": "thuế giá trị gia tăng",
    "KM/H": "ki lô mét trên giờ",
    "KM²": "ki lô mét vuông",
    "M²": "mét vuông",
    "KM": "ki lô mét",
    "CM": "xen ti mét",
    "MM": "mi li mét",
    "KG": "ki lô gam",
    "MG": "mi li gam",
    "GB": "ghi ga bai",
    "MB": "mê ga bai",
    "KB": "ki lô bai",
    "°C": "độ xê",
    "°F": "độ ép",
}

_VIETNAMESE_PRONUNCIATIONS = {
    "ChatGPT": "chát gi pi ti",
    "GPT": "gi pi ti",
    "Wi-Fi": "quai fai",
    "wifi": "quai fai",
    "Google": "gu gồ",
    "YouTube": "diu túp",
    "Facebook": "phây búc",
    "Zalo": "gia lô",
    "email": "i meo",
}

_VIETNAMESE_SYMBOLS = {
    "%": " phần trăm ",
    "‰": " phần nghìn ",
    "&": " và ",
    "@": " a còng ",
    "+": " cộng ",
    "=": " bằng ",
    "#": " thăng ",
    "×": " nhân ",
    "÷": " chia ",
    "≤": " nhỏ hơn hoặc bằng ",
    "≥": " lớn hơn hoặc bằng ",
    "<": " nhỏ hơn ",
    ">": " lớn hơn ",
    "~": " xấp xỉ ",
    "^": " mũ ",
    "*": " sao ",
    "/": " trên ",
    "\\": " gạch chéo ngược ",
    "|": " gạch đứng ",
}

CORS_ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
)

_COUNTER = 0
_COUNTER_LOCK = threading.Lock()


def _read_three_digit_number(value: int, *, full: bool) -> str:
    hundreds, remainder = divmod(value, 100)
    tens, ones = divmod(remainder, 10)
    words: list[str] = []

    if hundreds:
        words.extend((_VIETNAMESE_DIGITS[hundreds], "trăm"))
    elif full and remainder:
        words.extend(("không", "trăm"))

    if tens > 1:
        words.extend((_VIETNAMESE_DIGITS[tens], "mươi"))
    elif tens == 1:
        words.append("mười")
    elif ones and (hundreds or full):
        words.append("lẻ")

    if ones:
        if ones == 1 and tens > 1:
            words.append("mốt")
        elif ones == 4 and tens > 1:
            words.append("tư")
        elif ones == 5 and tens >= 1:
            words.append("lăm")
        else:
            words.append(_VIETNAMESE_DIGITS[ones])

    return " ".join(words)


def _read_vietnamese_integer(value: int) -> str:
    if value == 0:
        return _VIETNAMESE_DIGITS[0]
    if value < 0:
        return f"âm {_read_vietnamese_integer(abs(value))}"

    original_value = value
    groups: list[int] = []
    while value:
        value, group = divmod(value, 1000)
        groups.append(group)

    if len(groups) > len(_VIETNAMESE_SCALES):
        return " ".join(_VIETNAMESE_DIGITS[int(digit)] for digit in str(original_value))

    words: list[str] = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if not group:
            continue
        group_words = _read_three_digit_number(group, full=index < len(groups) - 1)
        words.append(group_words)
        if _VIETNAMESE_SCALES[index]:
            words.append(_VIETNAMESE_SCALES[index])
    return " ".join(words)


def _split_number_token(token: str) -> tuple[str, str | None, str]:
    sign = ""
    if token[0] in "+-":
        sign, token = token[0], token[1:]

    decimal_separator: str | None = None
    if "." in token and "," in token:
        decimal_separator = "." if token.rfind(".") > token.rfind(",") else ","
    else:
        separator = "." if "." in token else "," if "," in token else None
        if separator:
            groups = token.split(separator)
            is_grouped_integer = (
                all(len(group) == 3 for group in groups[1:]) and groups[0] != "0"
            )
            if not is_grouped_integer:
                decimal_separator = separator

    if decimal_separator:
        integer_part, decimal_part = token.rsplit(decimal_separator, 1)
        integer_part = integer_part.replace(".", "").replace(",", "")
        decimal_part = decimal_part.replace(".", "").replace(",", "")
    else:
        integer_part = token.replace(".", "").replace(",", "")
        decimal_part = None
    return integer_part, decimal_part, sign


def _read_vietnamese_number(token: str) -> str:
    integer_part, decimal_part, sign = _split_number_token(token)
    prefix = "âm " if sign == "-" else "dương " if sign == "+" else ""
    words = _read_vietnamese_integer(int(integer_part or "0"))
    if decimal_part is not None:
        decimals = " ".join(_VIETNAMESE_DIGITS[int(digit)] for digit in decimal_part)
        words = f"{words} phẩy {decimals}"
    return f"{prefix}{words}"


def _replace_vietnamese_date(match: re.Match[str]) -> str:
    day = int(match.group("day"))
    month = int(match.group("month"))
    year = int(match.group("year"))
    try:
        datetime(year, month, day)
    except ValueError:
        return match.group(0)
    return (
        f"ngày {_read_vietnamese_integer(day)} "
        f"tháng {_read_vietnamese_integer(month)} "
        f"năm {_read_vietnamese_integer(year)}"
    )


def _replace_vietnamese_currency(match: re.Match[str]) -> str:
    currency = _CURRENCY_NAMES[match.group("currency").lower()]
    return f"{_read_vietnamese_number(match.group('amount'))} {currency}"


def _replace_vietnamese_unit(match: re.Match[str]) -> str:
    unit = _VIETNAMESE_UNITS[match.group("unit").lower()]
    return f"{_read_vietnamese_number(match.group('amount'))} {unit}"


def _speak_vietnamese_url(match: re.Match[str]) -> str:
    value = match.group(0)
    trailing = ""
    while value and value[-1] in ".,!?;":
        trailing = value[-1] + trailing
        value = value[:-1]

    value = re.sub(
        r"^https://",
        "hát tê tê p ét hai chấm gạch chéo gạch chéo ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"^http://",
        "hát tê tê p hai chấm gạch chéo gạch chéo ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"^www\.",
        "vê kép vê kép vê kép chấm ",
        value,
        flags=re.IGNORECASE,
    )
    replacements = {
        ".": " chấm ",
        "/": " gạch chéo ",
        "-": " gạch ngang ",
        "_": " gạch dưới ",
        "@": " a còng ",
        ":": " hai chấm ",
        "?": " dấu hỏi ",
        "=": " bằng ",
        "&": " và ",
        "%": " phần trăm ",
        "#": " thăng ",
        "+": " cộng ",
    }
    for symbol, spoken in replacements.items():
        value = value.replace(symbol, spoken)
    value = re.sub(
        r"\d",
        lambda digit: f" {_VIETNAMESE_DIGITS[int(digit.group(0))]} ",
        value,
    )
    return f"{re.sub(r'\s+', ' ', value).strip()}{trailing}"


def _replace_terms(text: str, replacements: dict[str, str]) -> str:
    for source in sorted(replacements, key=len, reverse=True):
        text = re.sub(
            rf"(?<!\w){re.escape(source)}(?!\w)",
            replacements[source],
            text,
            flags=re.IGNORECASE,
        )
    return text


def _normalize_vietnamese(text: str) -> str:
    text = unicodedata.normalize("NFC", text).strip()
    text = _EMAIL_PATTERN.sub(_speak_vietnamese_url, text)
    text = _URL_PATTERN.sub(_speak_vietnamese_url, text)
    text = _DATE_YMD_PATTERN.sub(_replace_vietnamese_date, text)
    text = _DATE_DMY_PATTERN.sub(_replace_vietnamese_date, text)
    text = _CURRENCY_BEFORE_PATTERN.sub(_replace_vietnamese_currency, text)
    text = _CURRENCY_AFTER_PATTERN.sub(_replace_vietnamese_currency, text)
    text = _VIETNAMESE_UNIT_PATTERN.sub(_replace_vietnamese_unit, text)
    text = re.sub(r"(?<!\w)Q\.\s*(?=\d)", "quận ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)P\.\s*(?=\d)", "phường ", text, flags=re.IGNORECASE)
    text = _replace_terms(text, _VIETNAMESE_ABBREVIATIONS)
    text = _replace_terms(text, _VIETNAMESE_PRONUNCIATIONS)
    text = _NUMBER_PATTERN.sub(
        lambda match: _read_vietnamese_number(match.group(1)), text
    )
    for symbol, spoken in _VIETNAMESE_SYMBOLS.items():
        text = text.replace(symbol, spoken)

    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r",{2,}", ",", text)
    text = re.sub(r";{2,}", ";", text)
    text = re.sub(r":{2,}", ":", text)
    text = re.sub(r"!{2,}", "!", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(
        r"[!?]{2,}", lambda match: "?" if "?" in match.group(0) else "!", text
    )
    text = re.sub(r"([.!?])(?:\s*[.!?])+", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,.;:!?])(?=\S)", r"\1 ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalization_not_implemented(text: str, language: str) -> str:
    logger.warning(
        "Text normalization for %s will be implemented in the future",
        LANGUAGES[language],
    )
    return text


def normalize(text: str, language: str = "vn") -> str:
    """Normalize text for TTS while preserving unsupported languages unchanged."""
    language = language.lower().strip()
    match language:
        case "vn":
            return _normalize_vietnamese(text)
        case "en":
            return _normalization_not_implemented(text, language)
        case "zh":
            return _normalization_not_implemented(text, language)
        case "ja":
            return _normalization_not_implemented(text, language)
        case "ko":
            return _normalization_not_implemented(text, language)
        case "fr":
            return _normalization_not_implemented(text, language)
        case "de":
            return _normalization_not_implemented(text, language)
        case "it":
            return _normalization_not_implemented(text, language)
        case "pt":
            return _normalization_not_implemented(text, language)
        case "ru":
            return _normalization_not_implemented(text, language)
        case "es":
            return _normalization_not_implemented(text, language)
        case _:
            raise ValueError(f"Unsupported language: {language}")


def job_id_generator() -> str:
    global _COUNTER
    with _COUNTER_LOCK:
        _COUNTER = (_COUNTER + 1) % 65536
        counter = _COUNTER
    return f"tts{int(time.time() * 1000):x}{counter:04x}{secrets.token_hex(5)}"


def is_valid_job_id(job_id: str) -> bool:
    return bool(job_id) and job_id.isalnum() and len(job_id) <= 80


def output_filename(language: str, timezone_name: str) -> str:
    today = datetime.now(ZoneInfo(timezone_name)).strftime("%d-%m-%Y")
    return f"{today}-{language}.mp3"


def json_sse(payload: dict[str, Any], event_id: str) -> str:
    return f"id: {event_id}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def error_envelope_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled request error")
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error"}
        )
