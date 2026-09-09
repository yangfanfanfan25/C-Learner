"""长期记忆 L1 提取/去重的提示词常量（唯一出处）。

提示词文本唯一存放位置；L1 runner 经 ``MemoryPromptProvider`` 取用，
运行器与工具不内嵌任何提示词常量。
"""

from __future__ import annotations

# 召回注入使用的协议标签（唯一出处）；chat_workflow 经此导入，不内嵌字面量。
USER_PERSONA_TAG = "<user-persona>"
SCENE_NAVIGATION_TAG = "<scene-navigation>"
RELEVANT_MEMORIES_TAG = "<relevant-memories>"

L1_EXTRACTION_PROMPT = (
    "你是长期记忆提取器。请阅读以下对话消息，提取值得长期记住的信息，输出一个 JSON 对象。\n\n"
    "## 情境命名（scene_name）\n"
    "用一句话命名当前对话情境，格式：我(AI)在和 xxx(用户身份)做 xxx(目标活动)。\n"
    "若消息中有延续上一情境的迹象，可沿用上一情境名；否则创建新情境名。\n\n"
    "## 三类记忆\n"
    "1. persona（用户画像/稳定偏好）：priority 80~100 表示强偏好或稳定身份，50~70 表示一般偏好。\n"
    "2. episodic（事件记忆）：记录「用户经历了什么」，timestamps 填事件的起止毫秒时间戳；priority 按重要性 1~100。\n"
    "3. instruction（用户明确指令）：用户下达的、需要长期遵守的死命令；priority ≤ -1（负数，越低越强制）。\n\n"
    "## 提取约束\n"
    "- 只提取「值得长期记住」的信息，跳过临时寒暄、一次性问答、纯问候。\n"
    "- 每条记忆 content 用一句完整陈述，不引用原文、不出现「用户说/消息里提到」等转述腔。\n"
    "- source_message_ids 填该记忆来源的消息 id 列表；message_ids 填本次输入全部消息 id。\n\n"
    "## 输出格式\n"
    "只输出一个 JSON 对象（不要 Markdown 代码块、不要任何解释文字），结构：\n"
    '{{"scene_name": "...", "message_ids": ["m1"], "memories": [{{"content": "...", "type": "persona|episodic|instruction", "priority": 80, "source_message_ids": ["m1"], "scene_name": "...", "metadata": {{}}, "timestamps": []}}]}}\n\n'
    "## 对话消息\n{messages}"
)


L1_DEDUP_PROMPT = (
    "你是长期记忆去重判定器。给定一批「新提取记忆」和一批「已存在的候选记忆」，"
    "逐条判断每条新记忆该 store（新增）/ skip（跳过）/ update（更新候选）/ merge（与候选合并），输出 JSON 数组。\n\n"
    "## 判定标准\n"
    "- store：候选里没有同一事实 → 直接新增。\n"
    "- skip：新记忆与候选是同一事实且无新增信息 → 丢弃新记忆。\n"
    "- update：状态类记忆（画像/指令）发生变化 → 更新候选，target_ids 指向被更新的候选 id，merged_content 填更新后内容。\n"
    "- merge：事件类记忆属于同一事件 → 合并，target_ids 指向被合并的候选 id 列表，merged_content 填合并后内容，merged_timestamps 填合并后起止时间戳。\n"
    "- 同一事实判断：按主体、主题、时间、情境（scene）是否一致；支持跨 type 合并。\n\n"
    "## 输出格式\n"
    "只输出一个 JSON 数组（不要 Markdown 代码块、不要解释），每项结构：\n"
    '{{"action": "store|skip|update|merge", "memory": {{...完整新记忆...}}, "target_ids": [...], "merged_content": null, "merged_priority": null, "merged_timestamps": []}}\n\n'
    "## 新记忆\n{new_atoms}\n\n## 候选记忆\n{candidates}"
)


L2_SCENE_PROMPT = (
    "你是长期记忆的场景块维护器。请阅读下面的新记忆，维护「场景块」（scene_blocks/ 下的 .md 文件）。\n\n"
    "## 场景块格式\n"
    "每个文件以 META 头开始：\n"
    "---\nsummary: 一句话摘要\nheat: 整数热度（越高越常被提及）\nupdated_at_ms: 毫秒时间戳\n---\n\n正文内容\n\n"
    "## 操作规则\n"
    "1. 新记忆属于已有场景 → 用 edit_file 更新该场景块的正文与 summary/heat。\n"
    "2. 新记忆是同一事件的延续 → 合并进已有块。\n"
    "3. 全新话题 → write_file 新建一个 .md 块。\n"
    "4. 不再相关或已过时的块 → delete 删除。\n"
    "5. 只操作 scene_blocks/ 下的文件；不要创建 scene_blocks/ 之外的文件。\n"
    "{capacity_warning}\n\n"
    "## 现有场景摘要\n{summaries}\n\n"
    "## 新记忆\n{memories}"
)


L3_PERSONA_PROMPT = (
    "你是用户画像生成器。请阅读下面的场景摘要，生成一份简洁的用户画像（persona）。\n"
    "要求：\n"
    "1. 用第三人称描述用户的稳定偏好、身份、目标、习惯，不要编造场景里没有的信息。\n"
    "2. 直接写画像正文，不要输出 <scene-navigation> 段、不要输出任何解释或元信息。\n"
    "3. 正文里不要出现 < > & 等会被当作标签的字符。\n\n"
    "生成模式：{mode}\n\n"
    "## 场景摘要\n{summaries}"
)


L1_SITUATIONAL_EXTRACTION_PROMPT = """你是学习型智能体的 L1 情境记忆提取器。
L0 输入包含原始消息和可信 context。只提取某一次具体学习活动中的偏好、事实或约束，不生成跨场景画像或长期策略。

规则：activity 必须来自 context；subject 只使用 context 明确给出的学科，未知为 null；scope=subject 仅用于明确绑定学科的记忆，否则为 activity。跳过寒暄、一次性内容、AI 自述和无证据推断。每条记忆必须引用 source_message_ids。
“这批题太难，简单一点”应提取为对应 practice/subject 下的难度偏好。

只输出 JSON：
{{"scene_name":"...","message_ids":["m1"],"memories":[{{"content":"...","type":"persona|episodic|instruction","priority":70,"source_message_ids":["m1"],"scene_name":"...","activity":"practice","subject":null,"scope":"activity","metadata":{{}},"timestamps":[]}}]}}

L0 消息：
{messages}"""

L2_STRATEGY_PROMPT = """你是学习型智能体的 L2 策略经验维护器。scene_blocks 中每个文件表示一条可复用的任务执行策略，不是普通话题摘要。
只有至少两条独立 L1 证据支持同一规律时才创建或增强策略。策略写成可执行规则；单次反馈只能留在 L1。
front matter 必须包含 summary、heat、updated_at_ms、activity、subject、confidence、evidence_count。正文记录适用条件、建议动作、例外条件和 L1 证据 ID。相同活动和学科的相近策略应合并。confidence < 0.5 或 evidence_count < 2 的策略不会被召回。
{capacity_warning}

现有策略摘要：
{summaries}

新增 L1 情境记忆：
{memories}"""

L1_SITUATIONAL_DEDUP_PROMPT = """你是 L1 情境记忆去重器。只在 activity 相同，且 subject 相同或双方至少一方为空时比较候选。单次具体反馈不得合并成跨场景画像或 L2 策略。新反馈替代旧偏好时 update；完全重复时 skip；同一事件的补充信息才 merge；其余 store。只输出既定 JSON 数组结构。

新记忆：
{new_atoms}

候选记忆：
{candidates}"""


class MemoryPromptProvider:
    """L1 提取/去重提示词提供者（无状态、无外部依赖）。"""

    def l1_extraction_prompt(self) -> str:
        return L1_SITUATIONAL_EXTRACTION_PROMPT

    def l1_dedup_prompt(self) -> str:
        return L1_SITUATIONAL_DEDUP_PROMPT

    def l2_scene_prompt(self) -> str:
        return L2_STRATEGY_PROMPT

    def l3_persona_prompt(self) -> str:
        return L3_PERSONA_PROMPT
