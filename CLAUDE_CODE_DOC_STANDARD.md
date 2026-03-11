# CLAUDE_CODE_DOC_STANDARD — 开发计划文档规范 V2.1

> 适用范围：所有使用 Claude Code 进行版本迭代的项目
> 版本历史：V2.0 → V2.1（修复 BDD 定位模糊、合并重复规则、新增变更处理规则）

---

## 一、核心理念

每个版本的开发由以下三个文档驱动：

| 文档 | 作者 | 读者 | 目的 |
|---|---|---|---|
| **SPEC_Vx.md** | Claude（Human 确认） | 所有人 | 定义"做什么"（Story + Scenario） |
| **INSTRUCTIONS_Vx.md** | Claude（Human 确认） | Claude Code | 定义"怎么做"（Step + 测试） |
| **CLAUDE.md** | Claude Code 维护 | 所有人 | 项目认知 + 当前状态 |

**核心原则**：Story 驱动 Step，Scenario 驱动测试，测试驱动实现。

文档的生产顺序：
```
Human 需求 → User Stories → BDD Scenarios → SPEC → Instructions → 代码 + 测试
```

⚠️ 关于 BDD Scenarios 的定位说明：
本文档中的 BDD Scenarios 是「书面规格」，不是 pytest-bdd 的可执行 .feature 文件。
「从 Scenarios 直接生成 Instructions」的含义是：
  Instructions 中每个测试函数必须与某个 Scenario 一一对应，通过命名约定关联。
  不需要安装 pytest-bdd，不需要维护 .feature 文件。

---

## 二、User Stories 写法

### 2.1 标准格式

```
作为 [用户角色]，
我希望 [完成某件事]，
以便 [获得某种价值]。

验收标准：
- [ ] 具体可验证的条件 1
- [ ] 具体可验证的条件 2
```

### 2.2 Story 粒度原则

- 一个 Story 描述一个完整的用户价值单元
- Story 不描述技术实现，只描述用户视角的结果
- 一个版本通常包含 2~5 个 Story

### 2.3 INVEST 原则

| 字母 | 含义 |
|---|---|
| I — Independent  | Story 之间相互独立，可单独交付 |
| N — Negotiable   | 细节可与 Human 协商，不是固定合同 |
| V — Valuable     | 每个 Story 对用户有独立价值 |
| E — Estimable    | Claude 能拆解为明确的 Step，Human 能判断本版本是否做 |
| S — Small        | 一个 Story 不超过 3 个 Step |
| T — Testable     | 有明确的验收标准，可写成测试 |

---

## 三、BDD Scenarios 写法

### 3.1 标准格式（Gherkin 风格，书面规格）

```
Feature: [功能名称]
  覆盖 Story：US-N [Story 标题]

  Scenario: [场景名称]
    Given [前置条件]
    When  [触发动作]
    Then  [预期结果]
```

### 3.2 命名约定（与 Instructions 测试函数对应）

| BDD Scenario | pytest 测试函数 |
|---|---|
| `Scenario: 用户发送消息后收到回复` | `test_user_receives_reply_after_sending_message` |
| `Scenario: LLM 失败时降级到今日一句` | `test_fallback_to_daily_tip_on_llm_failure` |

### 3.3 覆盖率要求

- 每个 Story 至少有 2 个 Scenario（正向 + 边界/异常）
- 所有 Scenario 必须在 Instructions 中有对应测试函数
- 技术 Step 没有对应 Story 时，标注 `覆盖 Story：TECH`

---

## 四、SPEC 文档结构

```markdown
# Speakeasy Vx.x — 版本规格说明

## 一、User Stories
[所有 Story，Human 确认后不随意改动]

## 二、BDD Scenarios
[每个 Story 对应的 Scenarios]

## 三、前端 UI 规格
[界面描述、交互逻辑]

## 四、后端接口规格
[API 定义、请求/响应格式]

## 五、数据模型规格
[新增或修改的数据表结构]

## 六、降级策略
[各功能点的失败降级方案]
```

---

## 五、Instructions 文档结构

```markdown
# Speakeasy Vx.x — Claude Code 执行指令

## 工作规则
[见第九章]

## Step N：[Step 名称]
> 覆盖 Story：US-N [Story 标题]
> 覆盖 Scenarios：[Scenario 名称列表]

### 实现
[具体实现要求，代码片段，文件路径]

### 自测脚本：tests/test_stepN.py
[完整测试代码]

运行：`pytest tests/test_stepN.py -v`
全部 PASS 后打印 `✅ Step N 完成`
```

---

## 六、Step 拆分规则

### 6.1 Step 的粒度

- 每个 Step 是独立可测试的增量
- 一个 Step 的实现时间：30 分钟 ～ 2 小时
- 一个版本通常 5～9 个 Step

### 6.2 Step 类型

| 类型 | 说明 | 示例 |
|---|---|---|
| 数据层 | 数据表创建/修改 | Step 1 环境 + 数据表 |
| 服务层 | 业务逻辑实现 | Step 2 FSRS 记忆服务 |
| 接口层 | API 路由实现 | Step 3 复盘查询接口 |
| 前端层 | UI 组件实现 | Step 4 复盘前端 UI |
| 集成层 | 端到端测试 | Step 5 全链路回归 |

### 6.2.1 固定位置的 Step（必须出现，位置不可变）

每个版本的最后两个 Step 固定为：

```
## Step N-1：文档同步           ← 必须，位置固定在回归之前
## Step N：全链路回归 + 汇报    ← 必须，位置固定在最后
```

Step N-1 规范见 **7.0 文档同步 Step 规范**。

### 6.3 技术 Step 的标记方式

```
> 覆盖 Story：TECH（纯技术 Step，无对应用户 Story）
> 技术目标：[描述技术目的，如性能优化/重构/迁移]
> 验收标准：[测试通过 / 性能指标 / 代码质量指标]
```

---

## 七、汇报模板

### 7.0 文档同步 Step 规范（Step N-1）

```markdown
## Step N-1：文档同步

### 检查清单

对本版本每个新增或修改的服务，按以下规则判断是否需要更新文档：

| 情况 | 动作 |
|---|---|
| 新增跨模块服务（涉及 2+ 个文件的调用链） | 新建 `docs/architecture/flows/xxx-flow.md` |
| 修改了已有服务的跨模块调用链 | 更新对应的 flow 文档 |
| 仅修改单个文件内部逻辑 | 不需要 flow 文档 |
| 纯前端 Step | 不需要 flow 文档 |
| 新增或删除模块 | 更新 `docs/architecture/c4-container.md` |
| 做了重要技术决策 | 在 `docs/adr/` 新增 ADR 草稿，汇报中标注"待 Human 确认" |

### Flow 文档模板

新建的 flow 文档放在 `docs/architecture/flows/`，文件名格式：`{功能名}-flow.md`。

每个 flow 文档必须包含：
- **全局流程概览**（`flowchart TD`）：从用户触发到最终响应的完整路径
- **关键子流程**（`sequenceDiagram`）：跨模块的详细调用时序
- **状态机**（`stateDiagram-v2`，如有）：数据对象的状态变化

图表类型选择规则：
- "谁调用了谁、顺序是什么" → `sequenceDiagram`
- "这个对象有哪些状态" → `stateDiagram-v2`
- "流程里有什么分支" → `flowchart TD`
- "系统由哪些模块组成" → `graph TB`

### 完成标志

```bash
# 确认新建的 flow 文档存在
ls docs/architecture/flows/

# 确认 c4-container.md 的流程文档索引已更新
grep "flows/" docs/architecture/c4-container.md
```

全部确认后打印 `✅ Step N-1 完成`
```

### 7.1 Step 完成汇报（自动打印）

```
✅ Step N 完成
```

### 7.2 版本完成汇报（向 Human 输出）

```markdown
## Speakeasy Vx.x 完成汇报

### 测试结果
✅ 通过：N 个用例
❌ 失败：0 个用例

### 各 Step 状态
- Step 1 [名称]   ✅
- Step 2 [名称]   ✅
...

### 验收标准覆盖
- [ 已覆盖 ] [BDD Scenario 描述]
- [ 已覆盖 ] [BDD Scenario 描述]
...

### 遗留问题
（如有则列出，无则填"无"）

### 待 Human 人工验收
- [需要人工验证的场景]
...

### 文档同步状态
- CLAUDE.md        ✅ 已更新至当前版本状态
- C4 架构图        ✅ 已更新 / ⬜ 本版本无架构变更
- ADR              ✅ 新增 ADR-00X（[决策名]）/ ⬜ 本版本无新决策
- BUG_LOG          ✅ 已更新 / ⬜ 本版本无 Bug
- ROADMAP          ⏳ 待 Human 将本版本移入"已发布"（1分钟操作）
```

---

## 八、文档体系

### 8.1 文档全景

```
speakeasy/
├── CLAUDE.md                    ← 项目认知 + 当前状态（Claude Code 维护）
├── ROADMAP.md                   ← 版本路线图（Human 维护）
├── BUG_LOG.md                   ← Bug 记录（Claude Code 维护）
├── CLAUDE_CODE_DOC_STANDARD.md  ← 本文档
├── ALEX_BEHAVIOR_TEST_STANDARD.md ← Alex 行为测试标准
├── docs/
│   ├── adr/                     ← 架构决策记录（Claude Code 起草，Human 确认）
│   │   └── ADR-00N-[name].md
│   └── architecture/
│       └── c4-container.md      ← C4 架构图（Claude Code 维护）
├── SPEC_Vx.md                   ← 版本规格（每版本一个）
└── INSTRUCTIONS_Vx.md           ← 执行指令（每版本一个）
```

### 8.2 文档维护责任

| 文档 | 维护责任 | 触发时机 |
|---|---|---|
| CLAUDE.md | Claude Code | 每个 Step 完成后 |
| c4-container.md | Claude Code | 架构新增/删除模块时 |
| BUG_LOG.md | Claude Code | Bug 修复完成后 |
| docs/adr/ | Claude Code 起草，Human 确认 | 做了重要技术决策时 |
| ROADMAP.md | Human | 每次版本验收后 |

---

## 九、工作规则

Claude Code 执行版本开发时必须遵守：

1. 按 Step 顺序执行，不跳步
2. 每个 Step = 实现代码 + 自测脚本，测试全部 PASS 才进入下一步
3. 测试未通过则自行修复，直到全绿
4. 所有 pip install 在激活的 venv 中执行
5. 测试数据使用独立 user_id（如 `test_user_v0Xb_stepN`），每个测试后清理
6. 不修改已完成版本的代码和测试（除非 Human 明确要求）
7. mock 策略：只 mock 外部 LLM 调用，不 mock 内部服务
8. 断言必须用具体值，禁止模糊断言（如 `assert result is not None`）
9. 每个 Step 完成后：
   · 终端打印 `✅ Step N 完成`
   · 将 CLAUDE.md 中对应 Step 的 `⬜ 未开始` 更新为 `✅ 完成`
   · 如涉及架构变更，同步更新 docs/architecture/c4-container.md
10. 每完成 3 个 Step，重新阅读 SPEC 第一章（User Stories）和第二章（BDD Scenarios），
    确认后续 Step 仍与 Story 对齐
11. 遇到文档未覆盖的情况：
    · 涉及需求/Scenario 的不确定性 → 停下来，明确向 Human 提问
    · 涉及技术实现的不确定性 → 选择最保守方案，在汇报中说明
    · Human 直接要求修改需求 → 接受修改，在汇报中记录"需求变更：原 Scenario X → 新描述"
12. **生成 Instructions 时必须执行 SPEC 覆盖检查**

    1. 读取 SPEC 文件，提取所有 `SPEC-XX` 编号
    2. 每个 Step 标注覆盖的 SPEC ID（格式：`> SPEC 覆盖：SPEC-01 · SPEC-02`）
    3. 所有 Step 汇总后，输出未被任何 Step 覆盖的 SPEC ID 清单
    4. 清单非空时：暂停执行，在汇报中标注 `⚠️ 以下 SPEC ID 未被覆盖：SPEC-XX`，等待 Human 确认处理方式
    5. Human 确认后方可继续

    目的：从结构上防止 SPEC → Instructions 转化时遗漏功能点（参见 BUG-002 根因）

---

## 十、测试规范

### 10.1 测试数据隔离

- 测试数据使用独立 user_id：`test_user_[版本号]_[step号]`
- 每个测试有 `autouse fixture` 保证前后清理
- 不使用真实用户数据

### 10.2 断言规范

```python
# ✅ 正确：具体值断言
assert card.status == "pending"
assert card.frequency == 2
assert "go_went" in [c.key for c in cards]

# ❌ 错误：模糊断言
assert result is not None
assert len(cards) > 0
```

### 10.3 Mock 范围

```python
# ✅ 正确：只 mock 外部 LLM
with patch("app.services.review_service.get_client") as mock_client:
    ...

# ❌ 错误：mock 内部服务
with patch("app.services.memory_service.update_grammar_cards"):
    ...
```

---

## 十一、常见错误

| 错误 | 原因 | 正确做法 |
|---|---|---|
| Step 中实现了下一 Step 的功能 | 没有严格按规格边界执行 | 严格按 Instructions 的 Step 范围实现 |
| 测试用真实 API 而不 mock | 测试依赖外部服务 | 只 mock 外部 LLM 调用 |
| 模糊断言通过了但实际功能错误 | 断言不严格 | 使用具体值断言 |
| 修改了上一版本的测试 | 为了让新代码通过 | 不修改已完成版本的测试，修改实现代码 |
| 数据表改动未向 Human 确认 | 认为是小改动 | 任何表结构变更都先向 Human 确认 |
| Step 完成后没有更新 CLAUDE.md | 遗忘 | Step 完成 checklist 中包含文档更新 |
| 架构变更没有更新 C4 图 | 遗忘 | 参见工作规则第 9 条 |

---

## 十二、需求变更处理规则

版本开发中途出现需求变更时：

| 变更类型 | 处理方式 |
|---|---|
| 变更影响已完成 Step | 不回退，在下一版本作为新 Story 处理，当前版本继续 |
| 变更影响未开始 Step | 更新 SPEC 中的 Story/Scenario，Claude 重新确认后继续 |
| 需求澄清（原描述不准确） | 直接更新当前 SPEC，不计为变更，不影响进度 |
| Bug 修复涉及场景缺失 | 在对应 Feature 的 BDD 中补充 Scenario，同步补充测试用例 |
| Bug 修复属于实现错误 | 不新增 Scenario，只补充测试用例 |

技术债 Step（无对应用户 Story）的标记方式：
```
> 覆盖 Story：TECH（纯技术 Step，无对应用户 Story）
> 技术目标：[描述技术目的，如性能优化/重构/迁移]
> 验收标准：[测试通过 / 性能指标 / 代码质量指标]
```

---

## 十三、版本开始标准提示词

Human 启动新版本时使用以下提示词：

```
我要开始开发 [项目名] [版本号]。

用户需求：[用自然语言描述想法，Claude 整理成 Story]

前置条件：[上一版本] 已验收完成

请按照 CLAUDE_CODE_DOC_STANDARD.md v2.1：
1. 将我的需求整理为 User Stories，展示给我确认
2. 展开 BDD Scenarios，展示给我确认（重点检查有无遗漏场景）
3. 检查是否有新 ADR 需要创建
4. 我确认后，生成完整 SPEC 和 Instructions
```

---

*CLAUDE_CODE_DOC_STANDARD.md V2.1 — 最后更新 2026-03-10*
