"""Integration checks for substantive knowledge answers and local rotation."""

from pathlib import Path
import json
import tempfile
import unittest

from services.knowledge_search_service import KnowledgeSearchService


BACKEND_DIR = Path(__file__).resolve().parents[1]


class KnowledgeVariationsTest(unittest.TestCase):
    def setUp(self):
        state = tempfile.NamedTemporaryFile(prefix="knowledge-variation-", suffix=".json", dir=Path(__file__).parent, delete=False)
        state.close()
        self.state_path = Path(state.name)
        voice_state = tempfile.NamedTemporaryFile(prefix="voice-variation-", suffix=".json", dir=Path(__file__).parent, delete=False)
        voice_state.close()
        self.voice_state_path = Path(voice_state.name)
        fixture = tempfile.NamedTemporaryFile(prefix="knowledge-reviewed-", suffix=".json", dir=Path(__file__).parent, delete=False)
        fixture.close()
        self.fixture_path = Path(fixture.name)
        self.search = KnowledgeSearchService(BACKEND_DIR)
        self.search.variant_state_path = self.state_path
        self.search._local_responses.state_path = self.voice_state_path

    def tearDown(self):
        self.state_path.unlink(missing_ok=True)
        self.voice_state_path.unlink(missing_ok=True)
        self.fixture_path.unlink(missing_ok=True)

    def test_bible_manifest_is_the_canonical_source_registry(self):
        self.assertTrue(self.search.bible_manifest_path.is_file())
        self.assertEqual(self.search.offline_path.name, "catalog.json")
        self.assertTrue(str(self.search.offline_path).endswith("data\\Bible\\.internal\\sources\\offline_knowledge\\catalog.json"))

    def test_search_selects_semantic_child_but_draft_cannot_answer(self):
        cases = {
            "Что такое эмоция?": "psych-002-emotions-v1",
            "Как отличить мысль от эмоции?": "psych-002-emotions-v2",
            "Как собрать вокальный компинг?": "voice-002-editing-v2",
            "Почему щелкает стык вокальных дублей?": "voice-002-editing-v3",
            "Как убрать постоянный шум с вокала?": "voice-003-noise-v3",
            "Почему голос звучит водянисто после шумоподавления?": "voice-003-noise-v4",
            "Чем граница отличается от просьбы?": "psych-003-boundaries-v1",
            "Как сформулировать личную границу?": "psych-003-boundaries-v2",
        }
        for question, expected in cases.items():
            matches = self.search.search(question, 10)
            child = next((item for item in matches if item.get("id") == expected), None)
            self.assertIsNotNone(child)
            self.assertEqual(child["parent_id"], expected.rsplit("-v", 1)[0])
            self.assertIsNone(child["audio_path"])
            self.assertTrue(child["sources"])
            self.assertIsNone(self.search.answer(question))

    def test_recent_variant_rotation_is_local_and_bounded(self):
        variants = [{"variant_id": f"test-topic-v{i}", "variant_kind": f"angle-{i}",
                     "parent_id": "test-topic", "text": f"Тестовая тема: объяснение {i}",
                     "query_patterns": ["Тестовая тема"], "source_ids": ["https://example.org/source"],
                     "status": "VERIFIED", "audio_status": "AUDIO_PENDING"} for i in range(1, 5)]
        self.fixture_path.write_text(json.dumps({"cards": [{"id": "test-topic", "title": "Тестовая тема",
            "status": "VERIFIED", "sources": ["https://example.org/source"],
            "response_variations": variants}]}, ensure_ascii=False), encoding="utf-8")
        self.search.psychology_path = self.fixture_path
        ids = [self.search.answer("Тестовая тема")["id"] for _ in range(4)]
        self.assertEqual(len(set(ids)), 4)
        self.assertTrue(self.state_path.exists())
        self.assertIsNone(self.search.answer("Тестовая тема")["audio_path"])

    def test_search_ranks_topic_child_above_incidental_offline_word(self):
        results = self.search.search("Что такое эмоция?", 8)
        self.assertEqual(results[0]["id"], "psych-002-emotions-v1")
        self.assertEqual(results[0]["parent_id"], "psych-002-emotions")

    def test_unified_catalog_preserves_owners_and_legacy_collisions(self):
        catalog = self.search.catalog()
        self.assertEqual(len({row["canonical_id"] for row in catalog["records"]}), catalog["count"])
        music = json.loads(self.search.music_path.read_text(encoding="utf-8"))
        local_rows = [row for row in catalog["records"] if row["kind"].startswith("local_")]
        self.assertEqual(len(local_rows), sum(len(music[key]) for key in ("tracks", "artists", "albums")))
        offline = self.search.get("offline:topic:offline_0002_intel_8086")
        self.assertEqual(offline["record"]["source_location"], "data/Bible/.internal/sources/offline_knowledge/catalog.json")
        self.assertEqual(offline["content"]["id"], "offline_0002_intel_8086")
        legacy = self.search.get("offline:topic:offline_0001_topic_0001")
        self.assertEqual(legacy["record"]["recorded_status"], "VERIFIED")
        if not legacy["content"].get("sources"):
            self.assertEqual(legacy["record"]["content_status"], "RESEARCH_REQUIRED")
        voice = self.search.get("voice:intent:greetings_001")
        self.assertEqual(voice["record"]["source_location"], "data/Bible/.internal/sources/voice_responses/questions.json")

    def test_one_resolver_serves_voice_and_reviewed_offline(self):
        instant = self.search.answer("Привет, Jarvis")
        self.assertEqual(instant["source"], "conversational")
        self.assertTrue(Path(instant["audio_path"]).is_file())
        offline = self.search.answer("что такое Intel 8086")
        self.assertEqual(offline["source"], "offline_knowledge")
        self.assertEqual(offline["id"], "offline_0002_intel_8086-v1")
        self.assertIsNone(offline["audio_path"])
        pilot = self.search.get("offline:topic:offline_0002_intel_8086")
        self.assertEqual(pilot["record"]["content_status"], "VERIFIED")
        self.assertEqual(pilot["record"]["variant_count"], 6)
        unsourced = self.search.get("offline:topic:offline_0001_topic_0001")["content"]
        self.assertFalse(unsourced.get("sources"))
        self.assertIsNone(self.search.answer(unsourced["title"]))

    def test_news_question_does_not_reuse_how_are_you_response(self):
        answer = self.search.answer("Что нового?")
        self.assertIsNone(answer)

    def test_model_context_excludes_unsourced_legacy_cards(self):
        bundle = self.search.context_bundle("что такое Intel 8086", 6)
        self.assertTrue(bundle["sources"])
        self.assertFalse(bundle["multi_source"])
        self.assertTrue(bundle["requires_generation"])
        self.assertTrue(all(item["sources"] for item in bundle["sources"]))

    def test_reviewed_offline_variants_follow_question_without_legacy_wav(self):
        cases = {
            "Как 8086 вычисляет физический адрес?": "offline_0002_intel_8086-v3",
            "Чем Intel 8086 отличается от 8088?": "offline_0002_intel_8086-v4",
            "Какие ошибки допускают при объяснении Intel 8086?": "offline_0002_intel_8086-v6",
            "Сколько памяти может адресовать Intel 80386?": "offline_0010_intel_80386-v2",
            "Что добавил paging в Intel 386?": "offline_0010_intel_80386-v3",
            "Как Intel 80386 совместим с программами для 8086?": "offline_0010_intel_80386-v4",
            "Чем Intel 80386 отличался от 8086 и 80286?": "offline_0010_intel_80386-v5",
        }
        for question, expected in cases.items():
            answer = self.search.answer(question)
            self.assertEqual(answer["id"], expected)
            self.assertEqual(answer["parent_id"], expected.rsplit("-v", 1)[0])
            self.assertIsNone(answer["audio_path"])

    def test_fender_history_has_one_canonical_answer_and_preserved_alias(self):
        alias = self.search.get("offline:topic:offline_0041_fender_stratocaster")
        self.assertEqual(alias["record"]["alias_of"], "knowledge3:guitar:fender-stratocaster")
        self.assertEqual(alias["record"]["content_status"], "OUTDATED")
        self.assertEqual(len(alias["content"]["audio"]), 10)
        cases = {
            "История Fender Stratocaster": "fender-stratocaster-v1",
            "Какая электроника была у Stratocaster 1954 года?": "fender-stratocaster-v3",
            "Как устроено раннее тремоло Stratocaster?": "fender-stratocaster-v4",
        }
        for question, expected in cases.items():
            answer = self.search.answer(question)
            self.assertEqual(answer["id"], expected)
            self.assertEqual(answer["source"], "guitar")
            self.assertIsNone(answer["audio_path"])
            self.assertFalse(any(row.get("id") == "offline_0041_fender_stratocaster"
                                 for row in self.search.search(question, 100)))

    def test_reviewed_stress_guidance_uses_relevant_child_without_legacy_wav(self):
        item = self.search.get("knowledge3:psychology:psych-004-stress")
        self.assertEqual(item["content"]["version"], 2)
        self.assertEqual(item["content"]["quality_review"]["status"], "VERIFIED")
        self.assertEqual(item["content"]["audio_status"], "LEGACY_AUDIO_UNREVIEWED")
        self.assertTrue((BACKEND_DIR.parent / item["content"]["audio_path"]).is_file())
        cases = {
            "Как быстро стабилизироваться при стрессе?": "psych-004-stress-v2",
            "Что делать, если дыхательное упражнение неприятно?": "psych-004-stress-v4",
            "Чем стресс отличается от тревоги?": "psych-004-stress-v5",
            "Когда обращаться за помощью из-за стресса?": "psych-004-stress-v6",
            "Какие ошибки бывают в упражнениях при стрессе?": "psych-004-stress-v8",
        }
        for question, expected in cases.items():
            answer = self.search.answer(question)
            self.assertIsNotNone(answer, question)
            self.assertEqual(answer["id"], expected, question)
            self.assertEqual(answer["parent_id"], "psych-004-stress")
            self.assertIsNone(answer["audio_path"])
            self.assertTrue(answer["sources"])

    def test_reviewed_vocal_compression_routes_to_distinct_lessons(self):
        item = self.search.get("knowledge3:voice_production:voice-004-compression")
        self.assertEqual(item["content"]["version"], 2)
        self.assertEqual(item["content"]["quality_review"]["status"], "VERIFIED")
        self.assertEqual(item["content"]["audio_status"], "LEGACY_AUDIO_UNREVIEWED")
        self.assertTrue((BACKEND_DIR.parent / item["content"]["audio_path"]).is_file())
        cases = {
            "Что делает компрессор с вокалом?": "voice-004-compression-v1",
            "Как работают Threshold и Ratio у компрессора?": "voice-004-compression-v2",
            "Как настроить Attack и Release на вокале?": "voice-004-compression-v3",
            "Как пошагово настроить компрессию вокала?": "voice-004-compression-v4",
            "Когда компрессор на вокале не нужен?": "voice-004-compression-v6",
            "Что такое параллельная компрессия вокала?": "voice-004-compression-v8",
        }
        for question, expected in cases.items():
            answer = self.search.answer(question)
            self.assertIsNotNone(answer, question)
            self.assertEqual(answer["id"], expected, question)
            self.assertEqual(answer["parent_id"], "voice-004-compression")
            self.assertIsNone(answer["audio_path"])
            self.assertTrue(answer["sources"])

    def test_carnegie_book_uses_edition_scoped_sections_and_keeps_old_audio(self):
        item = self.search.get("knowledge3:literature:carnegie-friends")
        self.assertEqual(item["content"]["version"], 2)
        self.assertEqual(item["content"]["quality_review"]["status"], "VERIFIED")
        self.assertEqual(item["content"]["audio_status"], "LEGACY_AUDIO_UNREVIEWED")
        self.assertTrue((BACKEND_DIR.parent / item["content"]["audio_path"]).is_file())
        self.assertEqual(len(item["content"]["detailed_material"]["parts"]), 4)
        self.assertEqual(item["content"]["detailed_material"]["quotes"], [])
        cases = {
            "О чём книга Как завоёвывать друзей и оказывать влияние на людей?": "carnegie-friends-v1",
            "Что в первой части книги Карнеги?": "carnegie-friends-v2",
            "Как Карнеги предлагает вести спор?": "carnegie-friends-v4",
            "Как Карнеги советует давать обратную связь?": "carnegie-friends-v5",
            "Почему в разных изданиях Карнеги разное оглавление?": "carnegie-friends-v8",
        }
        for question, expected in cases.items():
            answer = self.search.answer(question)
            self.assertIsNotNone(answer, question)
            self.assertEqual(answer["id"], expected, question)
            self.assertEqual(answer["parent_id"], "carnegie-friends")
            self.assertIsNone(answer["audio_path"])
            self.assertTrue(answer["sources"])

    def test_cort_evl_z4_keeps_disputed_specs_explicit_and_routes_variants(self):
        item = self.search.get("knowledge3:guitar:cort-evl-z4")
        content = item["content"]
        self.assertEqual(content["version"], 2)
        self.assertEqual(content["brand"], "Cort")
        self.assertEqual(content["series"], "EVL")
        self.assertEqual(content["quality_review"]["status"], "VERIFIED")
        self.assertEqual(len(content["detailed_material"]["catalog_conflicts"]), 3)
        self.assertEqual(content["audio_status"], "LEGACY_AUDIO_UNREVIEWED")
        self.assertTrue((BACKEND_DIR.parent / content["audio_path"]).is_file())
        cases = {
            "Что за гитара Cort EVL-Z4?": "cort-evl-z4-v1",
            "Сколько ладов и какая конструкция у Cort EVL-Z4?": "cort-evl-z4-v2",
            "Какая электроника у Cort EVL-Z4?": "cort-evl-z4-v3",
            "Какой бридж стоит на Cort EVL-Z4 и чем его заменить?": "cort-evl-z4-v4",
            "Как настроить Cort EVL-Z4 для пониженного строя?": "cort-evl-z4-v5",
            "Что проверить перед покупкой Cort EVL-Z4 с рук?": "cort-evl-z4-v6",
            "Чем Cort EVL-Z4 отличается от Ibanez GIO GRG170DX?": "cort-evl-z4-v7",
            "Как улучшить или отремонтировать Cort EVL-Z4?": "cort-evl-z4-v8",
        }
        for question, expected in cases.items():
            answer = self.search.answer(question)
            self.assertIsNotNone(answer, question)
            self.assertEqual(answer["id"], expected, question)
            self.assertEqual(answer["parent_id"], "cort-evl-z4")
            self.assertIsNone(answer["audio_path"])
            self.assertTrue(answer["sources"])

    def test_audio_shortlist_uses_exact_reviewed_text(self):
        root = BACKEND_DIR.parent
        shortlist = json.loads((root / "data/Bible/.internal/sources/knowledge3/audio/AUDIO_READY_FOR_GENERATION.json").read_text(encoding="utf-8"))
        self.assertEqual(shortlist["queue_submission_status"], "NOT_SUBMITTED")
        for entry in shortlist["items"]:
            item = self.search.get(entry["canonical_id"])
            self.assertEqual(item["record"]["version"], entry["content_version"])
            self.assertEqual(item["content"].get("quality_review", {}).get("status"), "VERIFIED")
            variant = next(row for row in item["content"]["response_variations"] if row["variant_id"] == entry["variant_id"])
            self.assertEqual(entry["voice_text"], variant["text"])
            self.assertEqual(variant["status"], "VERIFIED")
            self.assertEqual(variant["audio_status"], "AUDIO_PENDING")
            self.assertGreaterEqual(entry["parts"], 1)


if __name__ == "__main__":
    unittest.main()
