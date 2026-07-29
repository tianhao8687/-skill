#!/usr/bin/env python3
"""Lightweight state and retrieval tooling for long-form Chinese web fiction.

No third-party dependencies are required. The script deliberately validates
state and continuity data without deciding literary quality or plot direction.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
CHAPTER_RE = re.compile(r"^(\d{4,})")
VALID_HARDNESS = {"hard", "interpreted", "rumor"}
VALID_CHARACTER_STATUS = {"alive", "dead", "missing", "sealed", "unknown", "departed"}
VALID_LOOP_STATUS = {"active", "sleeping", "paid_off", "abandoned"}
VALID_LOOP_ACTIONS = {"open", "advance", "payoff", "abandon", "sleep", "wake"}
VALID_GOLDFINGER_LAYERS = {"proficiency", "hundred_arts", "fusion"}
VALID_SKILL_STAGES = ["入门", "熟练", "精通", "圆满", "化境"]
VALID_FUSION_TIERS = {"minor", "core", "dao"}
VALID_FUSION_STATUS = {"clue", "collecting", "ready", "completed", "failed", "dormant"}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def fail(message: str, code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        fail(f"文件不存在: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"JSON格式错误: {path}: {exc}")


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def visible_char_count(text: str) -> int:
    """Count non-whitespace characters, excluding a leading Markdown H1 title."""
    lines = text.splitlines()
    if lines and lines[0].lstrip().startswith("#"):
        lines = lines[1:]
    return len(re.sub(r"\s+", "", "\n".join(lines)))


def chapter_number_from_path(path: Path) -> int:
    match = CHAPTER_RE.match(path.stem)
    if not match:
        fail(f"无法从文件名识别章节号: {path.name}，请使用0001.md格式")
    return int(match.group(1))


def project_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def copy_template(name: str, destination: Path, replacements: dict[str, str] | None = None) -> None:
    source = skill_root() / "templates" / name
    if not source.exists():
        fail(f"Skill模板缺失: {source}")
    text = source.read_text(encoding="utf-8")
    for old, new in (replacements or {}).items():
        text = text.replace(old, new)
    atomic_write_text(destination, text)


def ensure_project(root: Path) -> dict[str, Any]:
    cfg_path = root / "novel.json"
    if not cfg_path.exists():
        fail(f"这里不是已初始化的小说项目: {root}\n请先运行 init")
    cfg = load_json(cfg_path)
    if cfg.get("schema_version") != SCHEMA_VERSION:
        fail(f"不支持的项目schema_version: {cfg.get('schema_version')}")
    return cfg


def default_character(char_id: str, name: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": char_id,
        "name": name or char_id,
        "status": "alive",
        "location": "",
        "realm": "凡人",
        "identity": "",
        "current_desire": "",
        "current_pressure": "",
        "independent_goal": "",
        "comic_logic": "",
        "emotional_anchor": "",
        "knowledge": [],
        "items": [],
        "relationships": {},
        "last_updated_chapter": 0,
    }


def init_project(args: argparse.Namespace) -> None:
    root = project_path(args.project)
    if (root / "novel.json").exists() and not args.force:
        fail(f"项目已存在: {root}。需要重建请添加 --force")
    root.mkdir(parents=True, exist_ok=True)

    dirs = [
        "plans/volumes", "plans/arcs", "chapters", "summaries", "commits",
        "working", "state/characters", "state/world_rules", "state/factions",
        "state/items", "state/baseline/characters", "index", "backups/commits", "backups/state",
    ]
    for directory in dirs:
        (root / directory).mkdir(parents=True, exist_ok=True)

    estimate = max(1, math.ceil(args.target_chars / args.chapter_chars))
    config = {
        "schema_version": SCHEMA_VERSION,
        "title": args.title,
        "genre": "轻松有趣的原创修仙长篇",
        "platform_target": args.platform,
        "target_chars": args.target_chars,
        "chapter_target_chars": args.chapter_chars,
        "target_chapters_estimate": estimate,
        "status": "planning",
        "current_chapter": 0,
        "current_volume": 1,
        "current_arc": "arc-001",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "creative_policy": {
            "canon_is_hard": True,
            "future_outline_is_soft": True,
            "allow_emergent_plot": True,
            "imitate_named_author_style": False,
        },
        "core_premise": "",
        "protagonist_contradiction": "",
        "comic_engine": "",
        "growth_engine": "",
        "emotional_core": "",
        "goldfinger_id": "goldfinger-wanfa-proficiency",
        "focus_arts": ["剑道", "炼丹", "阵法"],
    }
    atomic_write_json(root / "novel.json", config)
    copy_template("reader-contract.md", root / "plans/reader-contract.md")
    copy_template("series-spine.md", root / "plans/series-spine.md")
    copy_template("story-frontier.md", root / "plans/story-frontier.md")
    copy_template("volume-plan.md", root / "plans/volumes/vol-001.md", {"[卷号]": "1"})
    copy_template("arc-card.md", root / "plans/arcs/arc-001.md", {"[arc-id]": "arc-001"})
    atomic_write_json(root / "state/facts.json", {"schema_version": SCHEMA_VERSION, "facts": []})
    atomic_write_json(root / "state/loops.json", {"schema_version": SCHEMA_VERSION, "loops": []})
    atomic_write_text(root / "state/timeline.jsonl", "")
    protagonist = load_json(skill_root() / "templates/protagonist-character.json")
    atomic_write_json(root / "state/characters/char-protagonist.json", protagonist)
    goldfinger = load_json(skill_root() / "templates/goldfinger.json")
    atomic_write_json(root / "state/goldfinger.json", goldfinger)
    atomic_write_text(
        root / "README.md",
        f"# {args.title}\n\n目标约 {args.target_chars:,} 字，估算约 {estimate} 章。\n\n"
        "本项目由 freeform-xianxia-serial Skill 初始化。未来规划属于软方向，正文事实与章节提交优先。\n",
    )
    build_index(root, quiet=True)
    print(f"已初始化: {root}")
    print(f"目标字数: {args.target_chars:,}；估算章节: {estimate}")
    print("下一步：填写 novel.json、plans/reader-contract.md 和 plans/series-spine.md")


def next_chapter_number(root: Path, config: dict[str, Any]) -> int:
    numbers = [chapter_number_from_path(p) for p in (root / "chapters").glob("*.md") if CHAPTER_RE.match(p.stem)]
    return max([int(config.get("current_chapter", 0)), *numbers], default=0) + 1


def new_chapter(args: argparse.Namespace) -> None:
    root = project_path(args.project)
    config = ensure_project(root)
    number = args.chapter or next_chapter_number(root, config)
    stem = f"{number:04d}"
    brief = root / "working" / f"{stem}-brief.md"
    commit_path = root / "working" / f"{stem}-commit.json"
    chapter_path = root / "chapters" / f"{stem}.md"

    if any(p.exists() for p in (brief, commit_path, chapter_path)) and not args.force:
        fail(f"第{number}章工作文件已存在；需要覆盖请添加 --force")

    copy_template("chapter-brief.md", brief, {"[章节号]": str(number)})
    commit_data = load_json(skill_root() / "templates/chapter-commit.json")
    commit_data["chapter"] = number
    commit_data["new_facts"] = []
    commit_data["character_updates"] = []
    commit_data["loop_updates"] = []
    commit_data["goldfinger_update"] = {
        "unlock_layers": [],
        "skills": [],
        "fusions": [],
        "materials_add": [],
        "notes_add": [],
    }
    atomic_write_json(commit_path, commit_data)
    if not chapter_path.exists() or args.force:
        atomic_write_text(chapter_path, f"# 第{number}章 [临时标题]\n\n")
    print(f"已创建第{number}章工作文件:")
    print(f"- {brief.relative_to(root)}")
    print(f"- {chapter_path.relative_to(root)}")
    print(f"- {commit_path.relative_to(root)}")


def validate_commit_payload(data: dict[str, Any], chapter: int) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append("commit.schema_version必须为1")
    if data.get("chapter") != chapter:
        errors.append(f"commit章节号{data.get('chapter')}与文件章节号{chapter}不一致")
    if not str(data.get("title", "")).strip():
        errors.append("commit.title不能为空")
    if not str(data.get("summary", "")).strip():
        errors.append("commit.summary不能为空")
    story_time = data.get("story_time", {})
    if not isinstance(story_time, dict) or not isinstance(story_time.get("ordinal"), (int, float)):
        errors.append("commit.story_time.ordinal必须是数字")
    for fact in data.get("new_facts", []):
        if not fact.get("id") or not fact.get("statement"):
            errors.append("每条new_fact都需要id和statement")
        if fact.get("hardness", "hard") not in VALID_HARDNESS:
            errors.append(f"事实{fact.get('id')}的hardness无效")
    for update in data.get("character_updates", []):
        if not update.get("id"):
            errors.append("每条character_update都需要id")
        if not isinstance(update.get("set", {}), dict):
            errors.append(f"人物{update.get('id')}的set必须是对象")
    for update in data.get("loop_updates", []):
        if not update.get("id"):
            errors.append("每条loop_update都需要id")
        if update.get("action") not in VALID_LOOP_ACTIONS:
            errors.append(f"事项{update.get('id')}的action无效")

    gf = data.get("goldfinger_update", {})
    if not isinstance(gf, dict):
        errors.append("goldfinger_update必须是对象")
    else:
        for layer in gf.get("unlock_layers", []):
            if layer not in VALID_GOLDFINGER_LAYERS:
                errors.append(f"金手指层级无效: {layer}")
        for skill in gf.get("skills", []):
            if not skill.get("id") or not skill.get("name"):
                errors.append("每条goldfinger skill都需要id和name")
            stage = skill.get("stage")
            if stage is not None and stage not in VALID_SKILL_STAGES:
                errors.append(f"技能{skill.get('id')}的stage无效: {stage}")
            if not isinstance(skill.get("traits_add", []), list):
                errors.append(f"技能{skill.get('id')}的traits_add必须是数组")
        for fusion in gf.get("fusions", []):
            if not fusion.get("id") or not fusion.get("name"):
                errors.append("每条goldfinger fusion都需要id和name")
            tier = fusion.get("tier")
            if tier is not None and tier not in VALID_FUSION_TIERS:
                errors.append(f"融合{fusion.get('id')}的tier无效: {tier}")
            status = fusion.get("status")
            if status is not None and status not in VALID_FUSION_STATUS:
                errors.append(f"融合{fusion.get('id')}的status无效: {status}")
            if not isinstance(fusion.get("completed_requirements_add", []), list):
                errors.append(f"融合{fusion.get('id')}的completed_requirements_add必须是数组")
        for material in gf.get("materials_add", []):
            if not isinstance(material, dict) or not material.get("id") or not material.get("name"):
                errors.append("每条goldfinger material都需要id和name")
    return errors


def preflight_state_updates(root: Path, commit: dict[str, Any], chapter: int) -> list[str]:
    """Check semantic state operations before writing any project files."""
    errors: list[str] = []
    facts_data = load_json(root / "state/facts.json", {"facts": []})
    facts_by_id = {item.get("id"): item for item in facts_data.get("facts", [])}
    for fact in commit.get("new_facts", []):
        existing = facts_by_id.get(fact.get("id"))
        if existing and existing.get("statement") != fact.get("statement"):
            errors.append(f"事实ID重复且内容不同: {fact.get('id')}")

    characters = load_characters(root)
    remote = set(commit.get("posthumous_or_remote_characters", []))
    for char_id in commit.get("present_characters", []):
        if characters.get(char_id, {}).get("status") == "dead" and char_id not in remote:
            errors.append(f"已死亡人物无说明地作为现场人物出现: {char_id}")
    for update in commit.get("character_updates", []):
        status = update.get("set", {}).get("status")
        if status is not None and status not in VALID_CHARACTER_STATUS:
            errors.append(f"人物{update.get('id')}的status无效: {status}")

    loops_data = load_json(root / "state/loops.json", {"loops": []})
    loops_by_id = {item.get("id"): item for item in loops_data.get("loops", [])}
    for update in commit.get("loop_updates", []):
        if update.get("action") != "open" and update.get("id") not in loops_by_id:
            errors.append(f"事项尚未open，不能执行{update.get('action')}: {update.get('id')}")

    goldfinger = load_json(root / "state/goldfinger.json", load_json(skill_root() / "templates/goldfinger.json"))
    current_state = goldfinger.get("current_state", {})
    skills_by_id = {item.get("id"): item for item in current_state.get("skills", [])}
    for update in commit.get("goldfinger_update", {}).get("skills", []):
        existing = skills_by_id.get(update.get("id"))
        new_stage = update.get("stage")
        old_stage = existing.get("stage") if existing else None
        if old_stage in VALID_SKILL_STAGES and new_stage in VALID_SKILL_STAGES:
            if VALID_SKILL_STAGES.index(new_stage) < VALID_SKILL_STAGES.index(old_stage):
                errors.append(f"技能阶段不能倒退: {update.get('id')} {old_stage} -> {new_stage}")

    fusions_by_id = {item.get("id"): item for item in current_state.get("fusions", [])}
    for update in commit.get("goldfinger_update", {}).get("fusions", []):
        existing = fusions_by_id.get(update.get("id"))
        if existing and existing.get("status") == "completed" and update.get("status") not in {None, "completed"}:
            errors.append(f"已完成融合不能退回未完成状态: {update.get('id')}")

    timeline_path = root / "state/timeline.jsonl"
    if timeline_path.exists():
        last: dict[str, Any] | None = None
        for line in timeline_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    last = json.loads(line)
                except json.JSONDecodeError:
                    errors.append("现有时间线包含非法JSON，不能继续提交")
                    break
        ordinal = commit.get("story_time", {}).get("ordinal")
        if last and isinstance(ordinal, (int, float)) and ordinal < last.get("ordinal", ordinal):
            errors.append(f"故事时间倒退: 上一条ordinal={last.get('ordinal')}，本章={ordinal}")
    return errors


def backup_file(root: Path, path: Path, category: str) -> None:
    if not path.exists():
        return
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = root / "backups" / category / f"{path.stem}-{stamp}{path.suffix}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)


def load_characters(root: Path) -> dict[str, dict[str, Any]]:
    characters: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "state/characters").glob("*.json")):
        data = load_json(path)
        if data.get("id"):
            characters[data["id"]] = data
    return characters


def ensure_baseline(root: Path) -> None:
    """Snapshot pre-chapter state once so later chapter revisions can rebuild safely."""
    baseline = root / "state/baseline"
    marker = baseline / ".created"
    if marker.exists():
        return
    (baseline / "characters").mkdir(parents=True, exist_ok=True)
    for name in ("facts.json", "loops.json", "goldfinger.json"):
        source = root / "state" / name
        if source.exists():
            shutil.copy2(source, baseline / name)
    for source in (root / "state/characters").glob("*.json"):
        shutil.copy2(source, baseline / "characters" / source.name)
    atomic_write_text(marker, now_iso() + "\n")


def restore_baseline(root: Path) -> None:
    baseline = root / "state/baseline"
    if not (baseline / ".created").exists():
        fail("缺少写作前基线，无法安全重建状态")
    for name, default in (
        ("facts.json", {"schema_version": SCHEMA_VERSION, "facts": []}),
        ("loops.json", {"schema_version": SCHEMA_VERSION, "loops": []}),
        ("goldfinger.json", load_json(skill_root() / "templates/goldfinger.json")),
    ):
        source = baseline / name
        atomic_write_json(root / "state" / name, load_json(source, default))
    chars_dir = root / "state/characters"
    for path in chars_dir.glob("*.json"):
        path.unlink()
    for source in (baseline / "characters").glob("*.json"):
        shutil.copy2(source, chars_dir / source.name)
    atomic_write_text(root / "state/timeline.jsonl", "")


def rebuild_state_from_commits(root: Path) -> None:
    """Recompute derived state after an edited historical chapter commit."""
    restore_baseline(root)
    commit_paths = sorted((root / "commits").glob("*.json"), key=chapter_number_from_path)
    previous = 0
    for path in commit_paths:
        chapter = chapter_number_from_path(path)
        if chapter != previous + 1:
            fail(f"无法重建：提交序列在第{chapter}章不连续")
        payload = load_json(path)
        update_facts(root, payload, chapter)
        update_characters(root, payload, chapter)
        update_loops(root, payload, chapter)
        update_goldfinger(root, payload, chapter)
        append_timeline(root, payload, chapter)
        previous = chapter
    config = ensure_project(root)
    config["current_chapter"] = previous
    config["updated_at"] = now_iso()
    atomic_write_json(root / "novel.json", config)


def update_facts(root: Path, commit: dict[str, Any], chapter: int) -> None:
    path = root / "state/facts.json"
    data = load_json(path, {"schema_version": SCHEMA_VERSION, "facts": []})
    facts = data.setdefault("facts", [])
    by_id = {item.get("id"): item for item in facts}
    for fact in commit.get("new_facts", []):
        item = dict(fact)
        item.setdefault("hardness", "hard")
        item.setdefault("tags", [])
        item["chapter"] = chapter
        existing = by_id.get(item["id"])
        if existing:
            if existing.get("statement") != item.get("statement"):
                fail(f"事实ID重复且内容不同: {item['id']}")
            continue
        facts.append(item)
        by_id[item["id"]] = item
    atomic_write_json(path, data)


def update_characters(root: Path, commit: dict[str, Any], chapter: int) -> None:
    characters = load_characters(root)
    remote = set(commit.get("posthumous_or_remote_characters", []))
    for char_id in commit.get("present_characters", []):
        existing = characters.get(char_id)
        if existing and existing.get("status") == "dead" and char_id not in remote:
            fail(f"已死亡人物无说明地作为现场人物出现: {char_id}")

    for update in commit.get("character_updates", []):
        char_id = update["id"]
        path = root / "state/characters" / f"{char_id}.json"
        char = characters.get(char_id)
        if char is None:
            name = update.get("set", {}).get("name") or update.get("name") or char_id
            char = default_character(char_id, name)
        set_values = update.get("set", {})
        if "status" in set_values and set_values["status"] not in VALID_CHARACTER_STATUS:
            fail(f"人物{char_id}的status无效: {set_values['status']}")
        for key, value in set_values.items():
            if key in {"id", "schema_version"}:
                continue
            char[key] = value

        knowledge = list(dict.fromkeys(char.get("knowledge", [])))
        for item in update.get("add_knowledge", []):
            if item not in knowledge:
                knowledge.append(item)
        remove_set = set(update.get("remove_knowledge", []))
        char["knowledge"] = [item for item in knowledge if item not in remove_set]

        relationships = char.setdefault("relationships", {})
        for other_id, note in update.get("relationship_notes", {}).items():
            relationships[other_id] = note
        char["last_updated_chapter"] = chapter
        atomic_write_json(path, char)
        characters[char_id] = char


def update_loops(root: Path, commit: dict[str, Any], chapter: int) -> None:
    path = root / "state/loops.json"
    data = load_json(path, {"schema_version": SCHEMA_VERSION, "loops": []})
    loops = data.setdefault("loops", [])
    by_id = {item.get("id"): item for item in loops}

    for update in commit.get("loop_updates", []):
        loop_id = update["id"]
        action = update["action"]
        existing = by_id.get(loop_id)
        if action == "open":
            if existing and existing.get("status") in {"active", "sleeping"}:
                existing["last_advanced_chapter"] = chapter
                existing.setdefault("history", []).append({"chapter": chapter, "action": "advance", "note": update.get("note", "")})
                continue
            item = {
                "id": loop_id,
                "type": update.get("type", "promise"),
                "title": update.get("title") or loop_id,
                "note": update.get("note", ""),
                "importance": update.get("importance", "medium"),
                "due_hint": update.get("due_hint", ""),
                "status": "active",
                "opened_chapter": chapter,
                "last_advanced_chapter": chapter,
                "history": [{"chapter": chapter, "action": "open", "note": update.get("note", "")}],
            }
            loops.append(item)
            by_id[loop_id] = item
            continue

        if existing is None:
            fail(f"事项尚未open，不能执行{action}: {loop_id}")
        existing.setdefault("history", []).append({"chapter": chapter, "action": action, "note": update.get("note", "")})
        existing["last_advanced_chapter"] = chapter
        if update.get("note"):
            existing["note"] = update["note"]
        if update.get("due_hint"):
            existing["due_hint"] = update["due_hint"]
        if action == "advance":
            existing["status"] = "active"
        elif action == "payoff":
            existing["status"] = "paid_off"
            existing["resolved_chapter"] = chapter
        elif action == "abandon":
            existing["status"] = "abandoned"
            existing["resolved_chapter"] = chapter
        elif action == "sleep":
            existing["status"] = "sleeping"
        elif action == "wake":
            existing["status"] = "active"

    atomic_write_json(path, data)


def update_goldfinger(root: Path, commit: dict[str, Any], chapter: int) -> None:
    """Merge deterministic progression updates into the golden-finger state."""
    path = root / "state/goldfinger.json"
    data = load_json(path, load_json(skill_root() / "templates/goldfinger.json"))
    state = data.setdefault(
        "current_state",
        {
            "unlocked_layers": ["proficiency"],
            "focus_arts": {"primary": "剑道", "secondary": ["炼丹", "阵法"]},
            "skills": [],
            "fusions": [],
            "materials": [],
            "notes": [],
            "last_updated_chapter": 0,
        },
    )
    update = commit.get("goldfinger_update", {})
    if not isinstance(update, dict):
        return

    unlocked = list(dict.fromkeys(state.get("unlocked_layers", [])))
    for layer in update.get("unlock_layers", []):
        if layer not in VALID_GOLDFINGER_LAYERS:
            fail(f"金手指层级无效: {layer}")
        if layer not in unlocked:
            unlocked.append(layer)
        if layer in data.get("layers", {}):
            data["layers"][layer]["current_status"] = "unlocked"
    state["unlocked_layers"] = unlocked

    skills = state.setdefault("skills", [])
    skills_by_id = {item.get("id"): item for item in skills}
    for patch in update.get("skills", []):
        skill_id = patch["id"]
        item = skills_by_id.get(skill_id)
        if item is None:
            item = {
                "id": skill_id,
                "name": patch["name"],
                "art": patch.get("art", "其他"),
                "stage": patch.get("stage", "入门"),
                "traits": [],
                "learned_chapter": chapter,
                "last_updated_chapter": chapter,
                "history": [],
            }
            skills.append(item)
            skills_by_id[skill_id] = item
        new_stage = patch.get("stage")
        old_stage = item.get("stage")
        if new_stage:
            if new_stage not in VALID_SKILL_STAGES:
                fail(f"技能{skill_id}的stage无效: {new_stage}")
            if old_stage in VALID_SKILL_STAGES and VALID_SKILL_STAGES.index(new_stage) < VALID_SKILL_STAGES.index(old_stage):
                fail(f"技能阶段不能倒退: {skill_id} {old_stage} -> {new_stage}")
            item["stage"] = new_stage
        if patch.get("name"):
            item["name"] = patch["name"]
        if patch.get("art"):
            item["art"] = patch["art"]
        traits = list(dict.fromkeys(item.get("traits", [])))
        for trait in patch.get("traits_add", []):
            if trait not in traits:
                traits.append(trait)
        item["traits"] = traits
        if patch.get("note"):
            item["note"] = patch["note"]
        item.setdefault("history", []).append(
            {
                "chapter": chapter,
                "stage": item.get("stage"),
                "note": patch.get("note", ""),
            }
        )
        item["last_updated_chapter"] = chapter

    fusions = state.setdefault("fusions", [])
    fusions_by_id = {item.get("id"): item for item in fusions}
    for patch in update.get("fusions", []):
        fusion_id = patch["id"]
        item = fusions_by_id.get(fusion_id)
        if item is None:
            item = {
                "id": fusion_id,
                "name": patch["name"],
                "tier": patch.get("tier", "minor"),
                "status": patch.get("status", "clue"),
                "requirements": patch.get("requirements", []),
                "completed_requirements": [],
                "discovered_chapter": chapter,
                "last_updated_chapter": chapter,
                "history": [],
            }
            fusions.append(item)
            fusions_by_id[fusion_id] = item
        if item.get("status") == "completed" and patch.get("status") not in {None, "completed"}:
            fail(f"已完成融合不能退回未完成状态: {fusion_id}")
        if patch.get("name"):
            item["name"] = patch["name"]
        if patch.get("tier"):
            if patch["tier"] not in VALID_FUSION_TIERS:
                fail(f"融合{fusion_id}的tier无效: {patch['tier']}")
            item["tier"] = patch["tier"]
        if patch.get("status"):
            if patch["status"] not in VALID_FUSION_STATUS:
                fail(f"融合{fusion_id}的status无效: {patch['status']}")
            item["status"] = patch["status"]
            if patch["status"] == "completed":
                item.setdefault("completed_chapter", chapter)
        if "requirements" in patch:
            item["requirements"] = patch.get("requirements", [])
        completed = list(dict.fromkeys(item.get("completed_requirements", [])))
        for requirement in patch.get("completed_requirements_add", []):
            if requirement not in completed:
                completed.append(requirement)
        item["completed_requirements"] = completed
        for key in ("missing_hint", "result", "common_principle", "note"):
            if patch.get(key):
                item[key] = patch[key]
        item.setdefault("history", []).append(
            {
                "chapter": chapter,
                "status": item.get("status"),
                "note": patch.get("note", ""),
            }
        )
        item["last_updated_chapter"] = chapter

    materials = state.setdefault("materials", [])
    materials_by_id = {item.get("id"): item for item in materials}
    for patch in update.get("materials_add", []):
        material_id = patch["id"]
        existing = materials_by_id.get(material_id)
        if existing:
            if patch.get("name") and existing.get("name") != patch.get("name"):
                fail(f"融合材料ID重复且名称不同: {material_id}")
            continue
        item = dict(patch)
        item["acquired_chapter"] = chapter
        materials.append(item)
        materials_by_id[material_id] = item

    notes = state.setdefault("notes", [])
    for note in update.get("notes_add", []):
        notes.append({"chapter": chapter, "note": str(note)})

    if any(update.get(key) for key in ("unlock_layers", "skills", "fusions", "materials_add", "notes_add")):
        state["last_updated_chapter"] = chapter
    atomic_write_json(path, data)


def append_timeline(root: Path, commit: dict[str, Any], chapter: int) -> None:
    path = root / "state/timeline.jsonl"
    story_time = commit.get("story_time", {})
    ordinal = story_time.get("ordinal")
    existing: list[dict[str, Any]] = []
    if path.exists():
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                existing.append(json.loads(line))
            except json.JSONDecodeError:
                fail(f"时间线第{line_no}行不是合法JSON")
    if existing and ordinal < existing[-1].get("ordinal", ordinal):
        fail(f"故事时间倒退: 上一条ordinal={existing[-1].get('ordinal')}，本章={ordinal}")
    entry = {
        "chapter": chapter,
        "ordinal": ordinal,
        "label": story_time.get("label", ""),
        "location": commit.get("location", ""),
        "event": commit.get("summary", ""),
    }
    lines = [json.dumps(item, ensure_ascii=False) for item in existing if item.get("chapter") != chapter]
    lines.append(json.dumps(entry, ensure_ascii=False))
    atomic_write_text(path, "\n".join(lines) + "\n")


def commit_chapter(args: argparse.Namespace) -> None:
    root = project_path(args.project)
    config = ensure_project(root)
    chapter_path = (root / args.chapter_file).resolve() if not Path(args.chapter_file).is_absolute() else Path(args.chapter_file).resolve()
    commit_input = (root / args.commit_file).resolve() if not Path(args.commit_file).is_absolute() else Path(args.commit_file).resolve()
    if root not in chapter_path.parents or root not in commit_input.parents:
        fail("章节文件和提交文件必须位于项目目录内")
    if not chapter_path.exists() or not commit_input.exists():
        fail("章节文件或提交文件不存在")

    chapter = chapter_number_from_path(chapter_path)
    payload = load_json(commit_input)
    errors = validate_commit_payload(payload, chapter)
    if errors:
        fail("提交数据未通过校验:\n- " + "\n- ".join(errors))

    current = int(config.get("current_chapter", 0))
    final_commit_path = root / "commits" / f"{chapter:04d}.json"
    if chapter != current + 1 and not (args.force and final_commit_path.exists()):
        fail(f"章节提交必须顺序进行。当前已提交{current}章，收到第{chapter}章")
    if final_commit_path.exists() and not args.force:
        fail(f"第{chapter}章已提交；修改后重新提交请添加 --force")

    chapter_text = chapter_path.read_text(encoding="utf-8")
    char_count = visible_char_count(chapter_text)
    if char_count == 0:
        fail("章节正文为空")

    ensure_baseline(root)

    if args.force:
        backup_file(root, final_commit_path, "commits")
        for state_file in [root / "state/facts.json", root / "state/loops.json", root / "state/goldfinger.json", root / "state/timeline.jsonl"]:
            backup_file(root, state_file, "state")

    committed = dict(payload)
    committed["char_count"] = char_count
    committed["source_file"] = str(chapter_path.relative_to(root)).replace("\\", "/")
    committed["source_sha256"] = sha256_text(chapter_text)
    committed["committed_at"] = now_iso()

    # Validate state before mutating it. Historical revisions are rebuilt from baseline.
    if not args.force:
        state_errors = preflight_state_updates(root, committed, chapter)
        if state_errors:
            fail("状态更新未通过预检:\n- " + "\n- ".join(state_errors))

    summary = {
        "schema_version": SCHEMA_VERSION,
        "chapter": chapter,
        "title": committed["title"],
        "summary": committed["summary"],
        "location": committed.get("location", ""),
        "story_time": committed.get("story_time", {}),
        "present_characters": committed.get("present_characters", []),
        "tone": committed.get("tone", {}),
        "next_possibilities": committed.get("next_possibilities", []),
        "char_count": char_count,
    }
    atomic_write_json(final_commit_path, committed)
    atomic_write_json(root / "summaries" / f"{chapter:04d}.json", summary)

    if args.force:
        rebuild_state_from_commits(root)
        config = ensure_project(root)
    else:
        update_facts(root, committed, chapter)
        update_characters(root, committed, chapter)
        update_loops(root, committed, chapter)
        update_goldfinger(root, committed, chapter)
        append_timeline(root, committed, chapter)

    config["current_chapter"] = max(current, chapter)
    config["status"] = "serializing"
    config["updated_at"] = now_iso()
    atomic_write_json(root / "novel.json", config)
    build_index(root, quiet=True)
    print(f"已提交第{chapter}章《{committed['title']}》，正文约{char_count}字")


def iter_indexable_files(root: Path) -> Iterable[tuple[Path, str, int | None, str]]:
    patterns = [
        ("chapters/*.md", "chapter"),
        ("summaries/*.json", "summary"),
        ("plans/**/*.md", "plan"),
        ("state/**/*.json", "state"),
        ("novel.json", "config"),
    ]
    for pattern, kind in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_dir():
                continue
            chapter: int | None = None
            title = path.stem
            if kind in {"chapter", "summary"} and CHAPTER_RE.match(path.stem):
                chapter = int(CHAPTER_RE.match(path.stem).group(1))  # type: ignore[union-attr]
            if path.suffix == ".json":
                try:
                    data = load_json(path)
                    content = json.dumps(data, ensure_ascii=False, indent=2)
                    title = str(data.get("title") or data.get("name") or title) if isinstance(data, dict) else title
                except SystemExit:
                    continue
            else:
                content = path.read_text(encoding="utf-8", errors="replace")
                first_heading = next((line.lstrip("# ").strip() for line in content.splitlines() if line.startswith("#")), "")
                if first_heading:
                    title = first_heading
            yield path, kind, chapter, title + "\n" + content


def build_index(root: Path, quiet: bool = False) -> None:
    ensure_project(root)
    db_path = root / "index/novel.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("DROP TABLE IF EXISTS docs")
        connection.execute(
            "CREATE TABLE docs (path TEXT PRIMARY KEY, kind TEXT NOT NULL, chapter INTEGER, title TEXT, content TEXT NOT NULL)"
        )
        rows = []
        for path, kind, chapter, combined in iter_indexable_files(root):
            title, _, content = combined.partition("\n")
            rows.append((str(path.relative_to(root)).replace("\\", "/"), kind, chapter, title, content))
        connection.executemany("INSERT INTO docs(path, kind, chapter, title, content) VALUES (?, ?, ?, ?, ?)", rows)
        connection.execute("CREATE INDEX idx_docs_kind ON docs(kind)")
        connection.execute("CREATE INDEX idx_docs_chapter ON docs(chapter)")
        connection.commit()
    finally:
        connection.close()
    if not quiet:
        print(f"索引已重建: {db_path}，共{len(rows)}个文档")


def query_index(root: Path, query: str, limit: int) -> list[dict[str, Any]]:
    db_path = root / "index/novel.db"
    if not db_path.exists():
        build_index(root, quiet=True)
    terms = [term for term in re.split(r"\s+", query.strip()) if term]
    if not terms:
        return []
    clauses = " AND ".join(["(title LIKE ? OR content LIKE ?)"] * len(terms))
    params: list[Any] = []
    for term in terms:
        token = f"%{term}%"
        params.extend([token, token])
    params.append(limit * 4)
    sql = f"SELECT path, kind, chapter, title, content FROM docs WHERE {clauses} ORDER BY COALESCE(chapter, 0) DESC LIMIT ?"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        raw_rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()

    results: list[dict[str, Any]] = []
    for row in raw_rows:
        content = row["content"]
        score = sum(content.count(term) + str(row["title"]).count(term) * 3 for term in terms)
        snippet_start = min([content.find(term) for term in terms if content.find(term) >= 0] or [0])
        snippet = content[max(0, snippet_start - 100): snippet_start + 400].replace("\n", " ")
        results.append({
            "path": row["path"], "kind": row["kind"], "chapter": row["chapter"],
            "title": row["title"], "score": score, "snippet": snippet,
        })
    results.sort(key=lambda item: (item["score"], item.get("chapter") or 0), reverse=True)
    return results[:limit]


def search_command(args: argparse.Namespace) -> None:
    root = project_path(args.project)
    ensure_project(root)
    results = query_index(root, args.query, args.limit)
    if not results:
        print("没有找到匹配内容。")
        return
    for index, item in enumerate(results, 1):
        chapter = f" / 第{item['chapter']}章" if item.get("chapter") else ""
        print(f"[{index}] {item['path']} ({item['kind']}{chapter}) score={item['score']}")
        print(f"    {item['snippet']}")


def recent_summaries(root: Path, chapter: int, count: int = 3) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    start = max(1, chapter - count)
    for number in range(start, chapter):
        path = root / "summaries" / f"{number:04d}.json"
        if path.exists():
            items.append(load_json(path))
    return items


def context_command(args: argparse.Namespace) -> None:
    root = project_path(args.project)
    config = ensure_project(root)
    chapter = args.chapter or int(config.get("current_chapter", 0)) + 1
    print(f"# 第{chapter}章写作上下文\n")
    print("## 项目核心\n")
    print(f"- 书名：{config.get('title', '')}")
    print(f"- 核心奇点：{config.get('core_premise', '') or '[未填写]'}")
    print(f"- 主角矛盾：{config.get('protagonist_contradiction', '') or '[未填写]'}")
    print(f"- 喜剧引擎：{config.get('comic_engine', '') or '[未填写]'}")

    goldfinger = load_json(root / "state/goldfinger.json", load_json(skill_root() / "templates/goldfinger.json"))
    gf_state = goldfinger.get("current_state", {})
    print("\n## 金手指状态\n")
    print(f"- 名称：{goldfinger.get('name', '万法熟练度')}")
    layer_names = {"proficiency": "熟练度成长", "hundred_arts": "百艺兼修", "fusion": "技能融合"}
    unlocked_names = [layer_names.get(item, item) for item in gf_state.get("unlocked_layers", [])]
    print(f"- 已解锁层级：{', '.join(unlocked_names) or '[暂无]'}")
    focus = gf_state.get("focus_arts", {})
    print(f"- 重点技艺：{focus.get('primary', '剑道')}、{'、'.join(focus.get('secondary', ['炼丹', '阵法']))}")
    recent_skills = sorted(gf_state.get("skills", []), key=lambda item: item.get("last_updated_chapter", 0), reverse=True)[:8]
    if recent_skills:
        print("- 近期相关技能：" + "；".join(f"{item.get('name')}·{item.get('stage')}" for item in recent_skills))
    active_fusions = [item for item in gf_state.get("fusions", []) if item.get("status") not in {"completed", "failed", "dormant"}]
    if active_fusions:
        status_names = {"clue": "已发现线索", "collecting": "收集中", "ready": "条件将成"}
        print("- 活跃融合：" + "；".join(f"{item.get('name')}（{status_names.get(item.get('status'), item.get('status'))}）" for item in active_fusions[:5]))

    summaries = recent_summaries(root, chapter, 3)
    print("\n## 最近章节\n")
    if not summaries:
        print("[尚无已提交摘要]")
    for item in summaries:
        print(f"### 第{item.get('chapter')}章 {item.get('title', '')}\n{item.get('summary', '')}\n")

    print("## 当前规划\n")
    plan_paths = [
        root / "plans/story-frontier.md",
        root / "plans/volumes" / f"vol-{int(config.get('current_volume', 1)):03d}.md",
        root / "plans/arcs" / f"{config.get('current_arc', 'arc-001')}.md",
    ]
    for path in plan_paths:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            print(f"### {path.relative_to(root)}\n{text[:3000]}\n")

    loops_data = load_json(root / "state/loops.json", {"loops": []})
    active_loops = [item for item in loops_data.get("loops", []) if item.get("status") == "active"]
    active_loops.sort(key=lambda item: ({"high": 3, "medium": 2, "low": 1}.get(item.get("importance"), 0), item.get("last_advanced_chapter", 0)), reverse=True)
    print("## 活跃承诺与未结事项\n")
    if not active_loops:
        print("[暂无]")
    for item in active_loops[:10]:
        print(f"- {item.get('id')}｜{item.get('title')}｜最近推进第{item.get('last_advanced_chapter')}章：{item.get('note', '')}")

    if args.query:
        print("\n## 相关检索\n")
        for item in query_index(root, args.query, args.limit):
            print(f"### {item['path']}\n{item['snippet']}\n")


def validate_project(args: argparse.Namespace) -> None:
    root = project_path(args.project)
    config = ensure_project(root)
    errors: list[str] = []
    warnings: list[str] = []
    current = int(config.get("current_chapter", 0))

    chapter_files = sorted((root / "chapters").glob("*.md"))
    commit_files = sorted((root / "commits").glob("*.json"))
    summary_files = sorted((root / "summaries").glob("*.json"))
    commit_numbers = [chapter_number_from_path(path) for path in commit_files]
    expected = list(range(1, current + 1))
    if commit_numbers != expected:
        errors.append(f"提交序列不连续：期望1..{current}，实际{commit_numbers[:10]}{'...' if len(commit_numbers) > 10 else ''}")
    summary_numbers = [chapter_number_from_path(path) for path in summary_files]
    if summary_numbers != expected:
        errors.append("摘要序列与当前章节不一致")

    chapter_numbers = [chapter_number_from_path(path) for path in chapter_files]
    missing_chapter_text = [number for number in expected if number not in chapter_numbers]
    if missing_chapter_text:
        errors.append(f"已提交但正文缺失的章节：{missing_chapter_text[:10]}")

    facts_data = load_json(root / "state/facts.json", {"facts": []})
    fact_ids = [item.get("id") for item in facts_data.get("facts", [])]
    duplicate_facts = sorted({item for item in fact_ids if item and fact_ids.count(item) > 1})
    if duplicate_facts:
        errors.append(f"重复事实ID：{duplicate_facts}")
    for fact in facts_data.get("facts", []):
        if fact.get("hardness", "hard") not in VALID_HARDNESS:
            errors.append(f"事实{fact.get('id')}的hardness无效")

    characters = load_characters(root)
    for char_id, char in characters.items():
        if char.get("status") not in VALID_CHARACTER_STATUS:
            errors.append(f"人物{char_id}的status无效")
        if int(char.get("last_updated_chapter", 0)) > current:
            errors.append(f"人物{char_id}更新时间超过当前章节")

    for path in commit_files:
        data = load_json(path)
        chapter = chapter_number_from_path(path)
        remote = set(data.get("posthumous_or_remote_characters", []))
        for char_id in data.get("present_characters", []):
            char = characters.get(char_id)
            if char and char.get("status") == "dead" and int(char.get("last_updated_chapter", 0)) < chapter and char_id not in remote:
                warnings.append(f"第{chapter}章出现当前标记死亡的人物{char_id}，请确认死亡发生章节和出场方式")
        source = root / data.get("source_file", "")
        if source.exists():
            current_hash = sha256_text(source.read_text(encoding="utf-8"))
            if data.get("source_sha256") != current_hash:
                warnings.append(f"第{chapter}章正文在提交后被修改，需重新生成提交")

    goldfinger_path = root / "state/goldfinger.json"
    if not goldfinger_path.exists():
        errors.append("缺少state/goldfinger.json")
    else:
        goldfinger = load_json(goldfinger_path)
        if goldfinger.get("schema_version") != SCHEMA_VERSION:
            errors.append("goldfinger.schema_version必须为1")
        gf_state = goldfinger.get("current_state", {})
        skill_ids: list[str] = []
        for skill in gf_state.get("skills", []):
            if skill.get("id") in skill_ids:
                errors.append(f"重复技能ID：{skill.get('id')}")
            skill_ids.append(skill.get("id"))
            if skill.get("stage") not in VALID_SKILL_STAGES:
                errors.append(f"技能{skill.get('id')}阶段无效")
        fusion_ids: list[str] = []
        for fusion in gf_state.get("fusions", []):
            if fusion.get("id") in fusion_ids:
                errors.append(f"重复融合ID：{fusion.get('id')}")
            fusion_ids.append(fusion.get("id"))
            if fusion.get("tier") not in VALID_FUSION_TIERS:
                errors.append(f"融合{fusion.get('id')}tier无效")
            if fusion.get("status") not in VALID_FUSION_STATUS:
                errors.append(f"融合{fusion.get('id')}status无效")

    loops_data = load_json(root / "state/loops.json", {"loops": []})
    for item in loops_data.get("loops", []):
        if item.get("status") not in VALID_LOOP_STATUS:
            errors.append(f"事项{item.get('id')}状态无效")
        opened = int(item.get("opened_chapter", 0))
        resolved = int(item.get("resolved_chapter", opened)) if item.get("resolved_chapter") is not None else opened
        if resolved < opened:
            errors.append(f"事项{item.get('id')}在开启前被解决")
        if item.get("status") == "active":
            age = current - int(item.get("last_advanced_chapter", opened))
            importance = item.get("importance", "medium")
            threshold = {"high": 80, "medium": 150, "low": 300}.get(importance, 150)
            if age > threshold:
                warnings.append(f"事项{item.get('id')}已{age}章未推进；可考虑推进、休眠或明确放弃")

    timeline_path = root / "state/timeline.jsonl"
    previous_ordinal: float | None = None
    if timeline_path.exists():
        for line_no, line in enumerate(timeline_path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"时间线第{line_no}行JSON无效")
                continue
            ordinal = item.get("ordinal")
            if not isinstance(ordinal, (int, float)):
                errors.append(f"时间线第{line_no}行缺少数字ordinal")
            elif previous_ordinal is not None and ordinal < previous_ordinal:
                errors.append(f"时间线在第{line_no}行倒退")
            previous_ordinal = ordinal if isinstance(ordinal, (int, float)) else previous_ordinal

    print(f"项目：{config.get('title')}｜当前第{current}章")
    if errors:
        print(f"\n错误 {len(errors)} 项：")
        for item in errors:
            print(f"- {item}")
    if warnings:
        print(f"\n警告 {len(warnings)} 项：")
        for item in warnings:
            print(f"- {item}")
    if not errors and not warnings:
        print("校验通过，未发现结构性问题。")
    elif not errors:
        print("\n结构校验通过，但存在需要作者判断的警告。")
    if errors:
        raise SystemExit(1)


def status_command(args: argparse.Namespace) -> None:
    root = project_path(args.project)
    config = ensure_project(root)
    current = int(config.get("current_chapter", 0))
    total_chars = 0
    latest_title = ""
    for path in sorted((root / "summaries").glob("*.json")):
        item = load_json(path)
        total_chars += int(item.get("char_count", 0))
        latest_title = item.get("title", latest_title)
    target = int(config.get("target_chars", 0))
    progress = (total_chars / target * 100) if target else 0
    loops = load_json(root / "state/loops.json", {"loops": []}).get("loops", [])
    active = [item for item in loops if item.get("status") == "active"]
    sleeping = [item for item in loops if item.get("status") == "sleeping"]
    characters = load_characters(root)
    goldfinger = load_json(root / "state/goldfinger.json", load_json(skill_root() / "templates/goldfinger.json"))
    gf_state = goldfinger.get("current_state", {})

    print(f"# {config.get('title')}\n")
    print(f"- 状态：{config.get('status')}")
    print(f"- 当前章节：{current}" + (f"《{latest_title}》" if latest_title else ""))
    print(f"- 已写字数：{total_chars:,} / {target:,}（{progress:.2f}%）")
    print(f"- 当前卷：{config.get('current_volume')}｜当前故事弧：{config.get('current_arc')}")
    print(f"- 登记人物：{len(characters)}")
    print(f"- 活跃事项：{len(active)}｜休眠事项：{len(sleeping)}")
    print(f"- 已登记技能：{len(gf_state.get('skills', []))}｜融合路线：{len(gf_state.get('fusions', []))}｜已完成融合：{len([item for item in gf_state.get('fusions', []) if item.get('status') == 'completed'])}")
    if active:
        print("\n## 重要活跃事项")
        active.sort(key=lambda item: ({"high": 3, "medium": 2, "low": 1}.get(item.get("importance"), 0), item.get("last_advanced_chapter", 0)), reverse=True)
        for item in active[:8]:
            print(f"- {item.get('id')}｜{item.get('title')}｜第{item.get('last_advanced_chapter')}章：{item.get('note', '')}")


def index_command(args: argparse.Namespace) -> None:
    root = project_path(args.project)
    build_index(root, quiet=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="自在修仙长篇项目工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="初始化小说项目")
    p_init.add_argument("project")
    p_init.add_argument("--title", required=True)
    p_init.add_argument("--target-chars", type=int, default=5_000_000)
    p_init.add_argument("--chapter-chars", type=int, default=5_500)
    p_init.add_argument("--platform", default="番茄小说")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=init_project)

    p_new = sub.add_parser("new-chapter", help="创建下一章工作文件")
    p_new.add_argument("project")
    p_new.add_argument("--chapter", type=int)
    p_new.add_argument("--force", action="store_true")
    p_new.set_defaults(func=new_chapter)

    p_commit = sub.add_parser("commit", help="提交章节并更新长期记忆")
    p_commit.add_argument("project")
    p_commit.add_argument("--chapter-file", required=True)
    p_commit.add_argument("--commit-file", required=True)
    p_commit.add_argument("--force", action="store_true")
    p_commit.set_defaults(func=commit_chapter)

    p_context = sub.add_parser("context", help="生成写章最小上下文")
    p_context.add_argument("project")
    p_context.add_argument("--chapter", type=int)
    p_context.add_argument("--query", default="")
    p_context.add_argument("--limit", type=int, default=8)
    p_context.set_defaults(func=context_command)

    p_search = sub.add_parser("search", help="检索项目内容")
    p_search.add_argument("project")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.set_defaults(func=search_command)

    p_validate = sub.add_parser("validate", help="检查结构与连续性数据")
    p_validate.add_argument("project")
    p_validate.set_defaults(func=validate_project)

    p_status = sub.add_parser("status", help="显示创作进度")
    p_status.add_argument("project")
    p_status.set_defaults(func=status_command)

    p_index = sub.add_parser("index", help="重建检索索引")
    p_index.add_argument("project")
    p_index.set_defaults(func=index_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "target_chars", 1) <= 0 or getattr(args, "chapter_chars", 1) <= 0:
        fail("字数参数必须大于0")
    args.func(args)


if __name__ == "__main__":
    main()
