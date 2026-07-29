from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "novelctl.py"


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode != expect:
        raise AssertionError(
            f"expected {expect}, got {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


class NovelCtlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "novel"
        run("init", str(self.root), "--title", "测试书")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_chapter_one(self) -> None:
        run("new-chapter", str(self.root))
        (self.root / "chapters/0001.md").write_text(
            "# 第1章 欠条\n\n陈闲摸了测灵碑，石碑吐出一张天道欠条。\n",
            encoding="utf-8",
        )
        payload = {
            "schema_version": 1,
            "chapter": 1,
            "title": "欠条",
            "summary": "陈闲在测灵时收到天道欠条。",
            "location": "测灵场",
            "story_time": {"label": "第一日", "ordinal": 1},
            "present_characters": ["char-protagonist"],
            "posthumous_or_remote_characters": [],
            "new_facts": [
                {
                    "id": "fact-0001",
                    "statement": "陈闲收到天道欠条。",
                    "hardness": "hard",
                    "tags": ["主线"],
                }
            ],
            "character_updates": [
                {
                    "id": "char-protagonist",
                    "set": {"name": "陈闲", "location": "测灵场"},
                    "add_knowledge": ["自己收到天道欠条"],
                    "remove_knowledge": [],
                    "relationship_notes": {},
                }
            ],
            "loop_updates": [
                {
                    "id": "loop-0001",
                    "action": "open",
                    "type": "mystery",
                    "title": "欠条来源",
                    "note": "来源未知",
                    "importance": "high",
                    "due_hint": "第一卷",
                }
            ],
            "goldfinger_update": {
                "unlock_layers": [],
                "skills": [
                    {
                        "id": "skill-basic-sword",
                        "name": "基础御剑术",
                        "art": "剑道",
                        "stage": "入门",
                        "traits_add": [],
                        "note": "首次学会",
                    }
                ],
                "fusions": [
                    {
                        "id": "fusion-step-wind",
                        "name": "踏风步",
                        "tier": "minor",
                        "status": "clue",
                        "requirements": ["轻身术·精通", "清风术·精通"],
                        "completed_requirements_add": [],
                        "missing_hint": "缺失两项技能阶段",
                    }
                ],
                "materials_add": [],
                "notes_add": ["首次察觉技能可能存在关联"],
            },
            "tone": {
                "dominant": "轻松",
                "humor_sources": ["制度荒谬"],
                "emotional_aftertaste": "好奇",
            },
            "next_possibilities": ["查账"],
        }
        (self.root / "working/0001-commit.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        run(
            "commit",
            str(self.root),
            "--chapter-file",
            "chapters/0001.md",
            "--commit-file",
            "working/0001-commit.json",
        )

    def test_init_commit_validate_and_search(self) -> None:
        self.write_chapter_one()
        validation = run("validate", str(self.root))
        self.assertIn("校验通过", validation.stdout)
        search = run("search", str(self.root), "天道 欠条")
        self.assertIn("chapters/0001.md", search.stdout)
        status = run("status", str(self.root))
        self.assertIn("当前章节：1", status.stdout)
        self.assertIn("已登记技能：1", status.stdout)
        goldfinger = json.loads((self.root / "state/goldfinger.json").read_text(encoding="utf-8"))
        self.assertEqual(goldfinger["current_state"]["skills"][0]["stage"], "入门")
        self.assertEqual(goldfinger["current_state"]["fusions"][0]["status"], "clue")

    def test_force_revision_rebuilds_state(self) -> None:
        self.write_chapter_one()
        path = self.root / "working/0001-commit.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["new_facts"][0]["statement"] = "陈闲收到会计息的天道欠条。"
        payload["character_updates"][0]["add_knowledge"] = ["天道欠条会计息"]
        payload["goldfinger_update"]["skills"][0]["stage"] = "熟练"
        payload["goldfinger_update"]["skills"][0]["note"] = "修订后在第一章达到熟练"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        run(
            "commit",
            str(self.root),
            "--chapter-file",
            "chapters/0001.md",
            "--commit-file",
            "working/0001-commit.json",
            "--force",
        )
        facts = json.loads((self.root / "state/facts.json").read_text(encoding="utf-8"))
        self.assertEqual(len(facts["facts"]), 1)
        self.assertIn("会计息", facts["facts"][0]["statement"])
        char = json.loads((self.root / "state/characters/char-protagonist.json").read_text(encoding="utf-8"))
        self.assertEqual(char["knowledge"], ["天道欠条会计息"])
        goldfinger = json.loads((self.root / "state/goldfinger.json").read_text(encoding="utf-8"))
        self.assertEqual(goldfinger["current_state"]["skills"][0]["stage"], "熟练")
        self.assertEqual(len(goldfinger["current_state"]["skills"]), 1)

    def test_rejects_out_of_order_commit(self) -> None:
        run("new-chapter", str(self.root), "--chapter", "2")
        (self.root / "chapters/0002.md").write_text("# 第2章\n\n正文。\n", encoding="utf-8")
        payload = json.loads((self.root / "working/0002-commit.json").read_text(encoding="utf-8"))
        payload["title"] = "第二章"
        payload["summary"] = "跳过第一章。"
        (self.root / "working/0002-commit.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        result = run(
            "commit",
            str(self.root),
            "--chapter-file",
            "chapters/0002.md",
            "--commit-file",
            "working/0002-commit.json",
            expect=2,
        )
        self.assertIn("必须顺序进行", result.stderr)


if __name__ == "__main__":
    unittest.main()
