---
description: Create or update the feature specification from a natural language feature description.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Outline

The text the user typed after `/speckit.specify` in the triggering message **is** the feature description. Assume you always have it available in this conversation even if `$ARGUMENTS` appears literally below. Do not ask the user to repeat it unless they provided an empty command.

**语言约定**：本项目的 spec 模板与生成的 spec **一律使用中文**。章节标题、验收场景格式（**前置条件** / **当** / **那么**）、占位符（如 [功能名称]、[日期]、[描述]）、检查清单等均使用中文。仅在技术术语（如 P1、FR-001、SC-001）或专有名词处保留英文。

Given that feature description, do this:

1. **生成功能的中文简短名称**（2–4 个词），用于功能目录名：
   - 从功能描述中提取关键词，生成**中文**简短名称
   - **不要使用英文**：目录名一律为中文，例如「综合选股」「用户登录」
   - 示例：
     - "我要开发综合选股" → "综合选股"
     - "先做用户登录" → "用户登录"
     - "持仓助手" → "持仓助手"

2. **在 master 上创建功能目录与 spec 文件**：调用脚本时必须传入 `--no-branch` 和 `--short-name "中文名称"`（及 `--json`），不创建、不切换 git 分支；脚本仅创建功能目录（如 `specs/002-综合选股/`）和 spec 文件：

   - Bash 示例：`.specify/scripts/bash/create-new-feature.sh "功能描述" --json --no-branch --short-name "综合选股"`
   - PowerShell 示例：`.specify/scripts/bash/create-new-feature.sh "功能描述" -Json -NoBranch -ShortName "综合选股"`

   **注意**：
   - 必须传 `--no-branch`，功能分支统一使用 master，不新建分支
   - 必须传 `--short-name` 且使用**中文**，生成目录名为 `002-综合选股` 这种形式，不要英文（如 002-comprehensive-stock-selection）
   - 不要传 `--number`，脚本会自动检测下一个可用编号
   - 必须传 `--json`，以便解析输出；JSON 中包含 BRANCH_NAME（此时为 "master"）、SPEC_FILE 路径、FEATURE_NUM
   - 脚本只执行一次

3. Load `.specify/templates/spec-template.md` to understand required sections. **模板与生成的 spec 均使用中文**（见上方语言约定）。

   **Spec 结构（必选方面）** — 创建或初始化 SPEC_FILE 时，按以下顺序组织，不得省略或合并：
   - **用户场景与测试**：按优先级（P1、P2、P3）排列的用户需求，每则含「为何此优先级」「独立测试」「验收场景」（**前置条件** / **当** / **那么**）；以及 **边界情况**。
   - **功能需求**：**功能要求**（FR-001、FR-002…，可测试的“必须”条款）与 **关键实体**（若功能涉及数据）。
   - **成功标准**：**可衡量结果**（SC-001、SC-002…，与技术实现无关、用户/业务可度量）。
   - **假设**：数据来源、默认范围、用户类型及未明确约定的计算或范围假设。

   若用户要求 **仅初始化模版**（如「帮我初始化一个模版我再写」「只生成模版」），则 SPEC_FILE 只写 **填空模版**：上述中文章节标题 + 中文占位符（如 `[功能名称]`、`[日期]`、`[描述]`，验收场景用「前置条件/当/那么」），**不要**填入具体功能内容。

4. Follow this execution flow:

    1. Parse user description from Input
       If empty: ERROR "No feature description provided"
    2. Extract key concepts from description
       Identify: actors, actions, data, constraints
    3. For unclear aspects:
       - Make informed guesses based on context and industry standards
       - Only mark with [NEEDS CLARIFICATION: specific question] if:
         - The choice significantly impacts feature scope or user experience
         - Multiple reasonable interpretations exist with different implications
         - No reasonable default exists
       - **LIMIT: Maximum 3 [NEEDS CLARIFICATION] markers total**
       - Prioritize clarifications by impact: scope > security/privacy > user experience > technical details
    4. 填写「用户场景与测试」章节
       若无法推断用户流程：ERROR "无法确定用户场景"
    5. 生成「功能需求」
       每条需求须可测试
       未明确处用合理默认并写在「假设」中
    6. 定义「成功标准」
       可衡量、与技术实现无关
       包含定量（时间、性能、规模）与定性（满意度、任务完成率）
       每条可验证且不依赖实现细节
    7. 识别「关键实体」（若涉及数据）
    8. Return: SUCCESS (spec ready for planning)

5. 将规格写入 SPEC_FILE：使用中文模板结构，用功能描述推导出的具体内容替换占位符，保持章节顺序与中文标题不变。

6. **Specification Quality Validation**: After writing the initial spec, validate it against quality criteria:

   a. **创建规格质量检查清单**：在 `FEATURE_DIR/checklists/requirements.md` 生成检查清单，使用以下结构（**中文**）：

      ```markdown
      # 规格质量检查清单：[功能名称]
      
      **目的**：在进入规划前验证规格完整性与质量  
      **创建日期**：[日期]  
      **功能规格**：[链接到 spec.md]
      
      ## 内容质量
      
      - [ ] 无实现细节（语言、框架、API）
      - [ ] 聚焦用户价值与业务需求
      - [ ] 面向非技术干系人可读
      - [ ] 所有必填章节已填写
      
      ## 需求完整性
      
      - [ ] 无 [待澄清] 标记残留
      - [ ] 需求可测试且无歧义
      - [ ] 成功标准可衡量
      - [ ] 成功标准与技术实现无关
      - [ ] 所有验收场景已定义
      - [ ] 边界情况已识别
      - [ ] 范围边界清晰
      - [ ] 依赖与假设已标明
      
      ## 功能就绪
      
      - [ ] 所有功能要求均有明确验收标准
      - [ ] 用户场景覆盖主流程
      - [ ] 功能满足「成功标准」中的可衡量结果
      - [ ] 规格中无实现细节泄露
      
      ## 备注
      
      - 未勾选项需在 `/speckit.clarify` 或 `/speckit.plan` 前更新 spec
      ```

   b. **Run Validation Check**: Review the spec against each checklist item:
      - For each item, determine if it passes or fails
      - Document specific issues found (quote relevant spec sections)

   c. **Handle Validation Results**:

      - **If all items pass**: Mark checklist complete and proceed to step 7

      - **If items fail (excluding [NEEDS CLARIFICATION])**:
        1. List the failing items and specific issues
        2. Update the spec to address each issue
        3. Re-run validation until all items pass (max 3 iterations)
        4. If still failing after 3 iterations, document remaining issues in checklist notes and warn user

      - **If [NEEDS CLARIFICATION] markers remain**:
        1. Extract all [NEEDS CLARIFICATION: ...] markers from the spec
        2. **LIMIT CHECK**: If more than 3 markers exist, keep only the 3 most critical (by scope/security/UX impact) and make informed guesses for the rest
        3. 对每个待澄清项（最多 3 个），用**中文**以下格式向用户呈现选项：

           ```markdown
           ## 问题 [N]：[主题]
           
           **上下文**：[引用 spec 中相关段落]
           
           **需确认**：[来自 [待澄清] 的具体问题]
           
           **建议选项**：
           
           | 选项 | 答案 | 对功能的影响 |
           |------|------|----------------|
           | A    | [第一个建议] | [对功能的影响] |
           | B    | [第二个建议] | [对功能的影响] |
           | C    | [第三个建议] | [对功能的影响] |
           | 自定义 | 自行填写 | [说明如何提供] |
           
           **你的选择**：_[等待用户回复]_
           ```

        4. **表格格式**：确保 markdown 表格正确（表头分隔符至少三横线，单元格内留空格）。
        5. 问题按顺序编号（Q1、Q2、Q3，最多 3 个）。
        6. 一次性呈现所有问题后再等待用户回复。
        7. 等待用户回复所有选择（如「Q1: A，Q2: 自定义 - [说明]，Q3: B」）。
        8. 用用户选择或填写的内容替换 spec 中的 [待澄清] 标记。
        9. 澄清全部解决后重新跑一遍校验。

   d. **更新检查清单**：每次校验后更新检查清单文件中的通过/未通过状态。

7. 报告完成：功能目录名（如 `002-综合选股`）、spec 文件路径、检查清单结果及是否可进入下一阶段（`/speckit.clarify` 或 `/speckit.plan`）。不报告分支名（始终为 master）。

**注意**：脚本不会创建或切换分支，仅在当前分支（master）下创建功能目录与 spec 文件并写入。

## 简要指南

- 关注用户**需要什么**与**为什么**，不写「如何实现」（不涉及技术栈、API、代码结构）。
- 面向业务干系人，非开发人员。
- 不在 spec 内嵌检查清单，检查清单单独生成。

### 章节要求

- **必填章节**：每个功能都必须完成（用户场景与测试、功能需求、成功标准、假设；若涉及数据则含关键实体）。
- **可选章节**：仅在与功能相关时保留。
- 某章节不适用时，整节删除，不要留「N/A」。

### 生成规格时（AI）

1. **合理推断**：用上下文、行业惯例和常见模式补全未写明的部分。
2. **记录假设**：合理默认写在「假设」章节。
3. **限制待澄清**：最多 3 处 [待澄清：具体问题]，仅用于对范围或体验影响大的决策，且无合理默认时。
4. **澄清优先级**：范围 > 安全/隐私 > 体验 > 技术细节。
5. **以测试视角**：含糊需求视为未通过「可测试、无歧义」。
6. **常需澄清**（仅在无合理默认时）：功能边界、用户类型与权限、安全/合规要求。

**合理默认示例**（无需追问）：数据保留按行业惯例、性能按常见 Web/移动预期、错误提示友好可回退、认证用会话或 OAuth2、集成方式按项目约定（如 REST/GraphQL）。

### 成功标准写法

须**可衡量、与技术无关、用户/业务视角、可验证**：

- 好：用户能在 3 分钟内完成下单、系统支持 1 万并发不降级、搜索 1 秒内返回结果。
- 差：API 响应 <200ms、数据库 1000 TPS、某框架/某技术指标（避免写实现细节）。
