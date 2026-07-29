# 设计依据（2026-07-29）

本 Skill 为原创实现，只吸收公开项目的高层设计经验，不复制其代码或文本。

## Agent Skill 结构

- OpenAI Build Skills: https://developers.openai.com/codex/build-skills
- Anthropic Skill Creator: https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md

吸收：渐进式加载、`SKILL.md + scripts + references`结构、触发描述的重要性。

## 长篇写作系统

- Webnovel Writer: https://github.com/lingfengQAQ/webnovel-writer
- Story Skills: https://github.com/danjdewhurst/story-skills
- Novel Creator Skill: https://github.com/leenbj/novel-creator-skill

吸收：写前检索、写后沉淀、章节提交、连续性检查、状态文件。

主动舍弃：每章强制多重门禁、固定爽点和钩子频率、完整自动写完、过度多Agent编排。

## 番茄平台公开信息

- 作者创作指南: https://fanqienovel.com/docs/8231
- 作品运作说明: https://fanqienovel.com/docs/8231/90699
- 作家福利: https://fanqienovel.com/welfare

平台规则会变化，签约、更新和福利要求应以作者后台当前公告为准。本 Skill 只处理创作方法，不保证商业结果。

## 类型作品研究边界

只研究公开作品的抽象叙事机制，不储存或提供作品正文，不仿写特定作者。
