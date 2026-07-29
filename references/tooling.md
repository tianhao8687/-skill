# 工具使用说明

`novelctl.py`仅使用Python标准库，推荐Python 3.10及以上。

## 初始化

```bash
python scripts/novelctl.py init <项目目录> \
  --title "书名" \
  --target-chars 5000000 \
  --chapter-chars 5500
```

## 创建下一章工作文件

```bash
python scripts/novelctl.py new-chapter <项目目录>
```

生成：

- `working/####-brief.md`
- `working/####-commit.json`
- 若不存在则生成空白章节文件。

## 准备写作上下文

```bash
python scripts/novelctl.py context <项目目录> \
  --chapter 12 \
  --query "主角 师父 宗门考核" \
  --limit 8
```

## 提交章节

```bash
python scripts/novelctl.py commit <项目目录> \
  --chapter-file chapters/0012.md \
  --commit-file working/0012-commit.json
```

提交会更新：

- `commits/0012.json`
- `summaries/0012.json`
- `state/goldfinger.json`
- `state/facts.json`
- `state/loops.json`
- `state/timeline.jsonl`
- `state/characters/*.json`
- `index/novel.db`

## 检索

```bash
python scripts/novelctl.py search <项目目录> "旧剑 法宝来历" --limit 10
```

## 验证和状态

```bash
python scripts/novelctl.py validate <项目目录>
python scripts/novelctl.py status <项目目录>
```

## 数据原则

- 第一次提交某章后默认不可覆盖；需要修文时使用 `--force`，脚本会保存旧提交备份。
- 脚本只验证结构和明确状态冲突，不能代替文学判断。
- `next_possibilities`不会写入硬事实。
- `interpreted`和`rumor`事实允许后续正文推翻。
- 若脚本报告正文与提交字数不一致，应先重新读取正文再决定。
