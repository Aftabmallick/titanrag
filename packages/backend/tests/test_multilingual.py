import json
from pathlib import Path

from titan_backend.retrieval.cross_lingual import CrossLingualRetriever
from titan_workers.pipeline.parser.multilingual_ocr import MultilingualOCREngine


def test_multilingual_ocr_script_detection():
    engine = MultilingualOCREngine()

    # Japanese text
    jp_text = "これはテスト文章です。TitanRAGドキュメント。"
    assert engine.detect_dominant_script(jp_text) == "jpn"

    # Arabic text
    ar_text = "هذا نص تجريبي للتحقق من استخراج المستندات"
    assert engine.detect_dominant_script(ar_text) == "ara"

    # Russian Cyrillic text
    ru_text = "Это тестовый документ для проверки распознавания"
    assert engine.detect_dominant_script(ru_text) == "rus"

    # English Latin text
    en_text = "This is an enterprise compliance policy document."
    assert engine.detect_dominant_script(en_text) == "eng"


def test_multilingual_ocr_run():
    engine = MultilingualOCREngine()
    result = engine.run_ocr(b"dummy_image_bytes", page_num=2)
    assert result["page_num"] == 2
    assert "detected_script" in result
    assert "is_rtl" in result
    assert len(result["languages_configured"]) >= 10


def test_cross_lingual_retriever():
    retriever = CrossLingualRetriever()

    # Detect Spanish
    es_query = "¿Cuál es la política de seguridad para el almacenamiento en la nube?"
    assert retriever.detect_language(es_query) == "es"

    # Detect German
    de_query = "Welche Sicherheitsrichtlinien gelten für das Projekt?"
    assert retriever.detect_language(de_query) == "de"

    # Detect Japanese
    ja_query = "セキュリティポリシーの概要は何ですか？"
    assert retriever.detect_language(ja_query) == "ja"

    # E5 prefixes
    formatted_query = retriever.format_e5_query("security guidelines")
    assert formatted_query == "query: security guidelines"

    formatted_passage = retriever.format_e5_passage("All documents must be encrypted at rest.")
    assert formatted_passage == "passage: All documents must be encrypted at rest."

    # Scaffolding
    variants = retriever.scaffold_cross_lingual_queries(es_query)
    assert len(variants) == 2
    assert variants[0]["language"] == "es"
    assert variants[0]["is_original"] is True
    assert variants[1]["language"] == "en"
    assert variants[1]["is_original"] is False


def test_frontend_i18n_dictionaries():
    messages_dir = Path("/Users/aftabmallick/Desktop/rag-god/titanrag/packages/frontend/src/messages")
    required_locales = ["en", "es", "de", "ja", "ar"]

    required_keys = {"nav", "chat", "documents", "settings", "common"}

    for locale in required_locales:
        file_path = messages_dir / f"{locale}.json"
        assert file_path.exists(), f"Missing translation dictionary for {locale}"

        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        assert required_keys.issubset(data.keys()), f"Locale {locale} missing primary key namespaces"
