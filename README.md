# 自在修仙长篇共创 Skill

一个面向中文轻松修仙长篇的原创 Agent Skill，默认按约500万字连载设计。

它不是“一键自动生成500万字”，也不是把小说拆成九百个固定提示词。它采用：

- `SKILL.md`：创作决策与使用流程。
- `references/`：按需加载的创作方法，不占满上下文。
- `scripts/novelctl.py`：确定性的状态、检索、提交和校验。
- `templates/`：项目、分卷、故事弧、人物和章节提交模板。
- `evals/`：用于检查是否压制脑洞、是否过度套路化的测试场景。

## 设计目标

1. AI可以自由决定具体桥段、场景和解决办法。
2. 已写事实、人物状态、时间线和伏笔不能靠“记得差不多”。
3. 未来大纲始终是软方向，不把约900章提前锁死。
4. 轻松感来自人物、关系和世界制度，并通过可选的长期幽默状态防止机制复读，而不是固定段子频率。
5. 适配番茄读者的进入门槛和追读习惯，但不强制打脸、升级和章末悬崖。
6. 可研究《从前有座灵剑山》等作品的抽象方法，但禁止复制其独特文风、角色和桥段。

## 运行要求

- Skill本身：任何支持开放Agent Skills格式、能读取`SKILL.md`的宿主。
- 脚本：Python 3.10+，只使用标准库，不需要安装第三方包。

## 安装

### Codex / ChatGPT Skills

将整个 `freeform-xianxia-serial-skill` 文件夹放入支持的 Skills 目录，或将压缩包作为 Skill 上传。目录顶层必须保留 `SKILL.md`。

### Claude Code / 其他兼容Agent

将文件夹复制到对应的 Skills 目录；也可在项目中直接要求 Agent 读取此 `SKILL.md`。不同版本的插件市场安装方式可能变化，因此本包不绑定某个平台专有清单。

## 快速开始

初始化一本500万字项目：

```bash
python scripts/novelctl.py init ./我的修仙小说 \
  --title "书名" \
  --target-chars 5000000 \
  --chapter-chars 5500
```

创建第一章工作文件：

```bash
python scripts/novelctl.py new-chapter ./我的修仙小说
```

让 Agent 填写：

- `chapters/0001.md`
- `working/0001-commit.json`

提交章节并更新长期记忆：

```bash
python scripts/novelctl.py commit ./我的修仙小说 \
  --chapter-file chapters/0001.md \
  --commit-file working/0001-commit.json
```

准备下一章上下文：

```bash
python scripts/novelctl.py context ./我的修仙小说 \
  --chapter 2 \
  --query "主角 师父 宗门考核" \
  --limit 8
```

查看进度与校验：

```bash
python scripts/novelctl.py status ./我的修仙小说
python scripts/novelctl.py validate ./我的修仙小说
```

## 项目结构

```text
我的修仙小说/
├── novel.json                  # 项目核心与当前位置
├── plans/
│   ├── reader-contract.md      # 读者契约
│   ├── series-spine.md         # 全书低分辨率脊柱
│   ├── story-frontier.md       # 未来3-12章候选路径
│   ├── volumes/                # 分卷地图
│   └── arcs/                   # 故事弧卡片
├── chapters/                   # 正文
├── summaries/                  # 每章摘要
├── commits/                    # 每章事实增量，审计来源
├── working/                    # 当前章节简报和待提交数据
├── state/
│   ├── characters/             # 人物当前状态
│   ├── goldfinger.json         # 万法熟练度、技能与融合进度
│   ├── humor.json              # 重要幽默事件、回收项、失效模式和情绪保护
│   ├── facts.json              # 已确认事实
│   ├── loops.json              # 伏笔、承诺和未结事项
│   ├── timeline.jsonl          # 时间线
│   └── baseline/               # 第一章前状态，用于历史修订重建
└── index/novel.db              # 本地检索索引
```

## 500万字默认尺度

- 约850至950章，核心目标约900章。
- 单章约5000至6000字。
- 约9至12卷。
- 6至8个阶段。
- 只细化当前卷和未来3至12章。
- 每章写后提交事实；每卷结束重新发现中远期方向。

这些都是容量建议，不是强制模板。

## 目前故意没有加入的功能

- 自动连续生成几百章。
- 强制每章五步门禁。
- 固定爽点、打脸、升级和断章频率。
- 每章强制启用多Agent喜剧评审；只在关键场景或专项体检时按需使用。
- 多Agent互相讨论后堆出大量中间文本。
- 自动模仿某本小说的文风。
- 必须联网的向量数据库。

这些功能看起来“更完善”，但会增加成本、降低可控性，并更容易把创作变成流水线。

## 局限

- 脚本能发现明确的数据冲突，不能理解所有文学语义。
- Agent仍需正确填写章节提交文件，不能把推测写成硬事实。
- SQLite检索采用轻量文字匹配，适合本地可控工作流；超大项目可后续替换为混合检索，但不建议一开始就增加RAG部署负担。
- 平台政策、签约和福利要求会变化，应以番茄作家后台的最新公告为准。

## 版本

`0.3.0`：加入不抢总控权的幽默叙事子引擎、长期重复检测、回收型笑点与重大情绪保护状态。
