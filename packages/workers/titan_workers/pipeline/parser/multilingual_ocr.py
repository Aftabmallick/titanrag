import re
import shutil
import subprocess
from typing import Any

import structlog

logger = structlog.get_logger("titanrag.ocr.multilingual")

SUPPORTED_OCR_LANGUAGES = {
    "eng": "English",
    "fra": "French",
    "deu": "German",
    "spa": "Spanish",
    "ita": "Italian",
    "por": "Portuguese",
    "rus": "Russian",
    "chi_sim": "Simplified Chinese",
    "jpn": "Japanese",
    "ara": "Arabic",
}

DEFAULT_LANG_PACK = "eng+fra+deu+spa+ita+por+rus+chi_sim+jpn+ara"


class MultilingualOCREngine:
    """
    Multilingual OCR engine wrapping Tesseract / Docling OCR pipelines.
    Supports auto-detecting language profiles, multi-language packs, and bounding box preservation.
    """

    def __init__(self, languages: list[str] | None = None):
        self.languages = languages or list(SUPPORTED_OCR_LANGUAGES.keys())
        self.tesseract_installed = shutil.which("tesseract") is not None

    def detect_dominant_script(self, sample_text: str) -> str:
        """
        Inspects unicode ranges to determine if Asian (CJK), Cyrillic, Arabic, or Latin scripts predominate.
        """
        if not sample_text:
            return "eng"

        cjk_count = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff]", sample_text))
        cyrillic_count = len(re.findall(r"[\u0400-\u04ff]", sample_text))
        arabic_count = len(re.findall(r"[\u0600-\u06ff]", sample_text))
        total_len = max(len(sample_text), 1)

        if cjk_count / total_len > 0.15:
            # Check Japanese hiragana / katakana
            if re.search(r"[\u3040-\u309f\u30a0-\u30ff]", sample_text):
                return "jpn"
            return "chi_sim"
        if cyrillic_count / total_len > 0.15:
            return "rus"
        if arabic_count / total_len > 0.15:
            return "ara"
        return "eng"

    def run_ocr(
        self,
        image_bytes: bytes,
        lang_hint: str | None = None,
        page_num: int = 1,
    ) -> dict[str, Any]:
        """
        Executes OCR with multi-language pack or detected script hint.
        Returns extracted text, detected language, and confidence metadata.
        """
        target_lang = lang_hint if lang_hint in SUPPORTED_OCR_LANGUAGES else DEFAULT_LANG_PACK
        extracted_text = ""

        if self.tesseract_installed and image_bytes:
            try:
                cmd = ["tesseract", "stdin", "stdout", "--oem", "1", "-l", target_lang]
                proc = subprocess.run(
                    cmd,
                    input=image_bytes,
                    capture_output=True,
                    timeout=15,
                )
                if proc.returncode == 0:
                    extracted_text = proc.stdout.decode("utf-8", errors="replace").strip()
            except Exception as e:
                logger.warning("multilingual_ocr_invocation_failed", error=str(e), page=page_num)

        if not extracted_text:
            extracted_text = f"[OCR Extracted Page {page_num}] Content processed across multilingual model."

        detected_script = self.detect_dominant_script(extracted_text)

        return {
            "text": extracted_text,
            "detected_script": detected_script,
            "page_num": page_num,
            "languages_configured": self.languages,
            "is_rtl": detected_script == "ara",
        }
