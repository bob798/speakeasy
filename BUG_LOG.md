# Speakeasy Bug Log

> 维护规则：
> · Human 发现 Bug → Claude 在此记录
> · Claude Code 修复完成 → 自动将状态更新为 ✅ 已修复
> · 版本验收时确认本版本所有 Bug 均已修复或有明确说明

---

## Bug 记录

### BUG-001：Alex 包装式显性纠错

**状态**：⬜ 待修复（指令已生成，等待 Claude Code 执行）
**发现版本**：V0.2a
**严重程度**：P0（违反核心产品原则）
**发现时间**：2025-03-01

**现象**：
Alex 在回复中以夸赞形式引用用户的错误表达，例如：
> "I love how you said 'I am very happy to meeting you' — let me share how natives might put it..."

**根因**：
SYSTEM_PROMPT 只禁止了直接纠错，未覆盖"包装式纠错"场景。
Alex 通过"夸赞用户的错误表达"来引出正确表达，本质上仍是显性纠错。

**修复方案**：
在 `app/services/chat_service.py` 的 SYSTEM_PROMPT 末尾追加三条绝对禁令：
1. 禁止以任何形式引用用户刚才说的话（无论夸赞还是批评）
2. 禁止用"how you said..."、"the way you put it..."等句式
3. 禁止任何"先引用错误，再示范正确"的结构

**执行指令文件**：`CLAUDE_CODE_BUGFIX_001_INSTRUCTIONS.md`

**修复验证**：
运行 `pytest tests/test_alex_behavior.py -v`
验收门槛：D1 维度（禁止行为）6个用例全部通过

---

### BUG-002：历史会话缺少「查看复盘」入口

**状态**：⬜ 待修复（已并入 V0.2b Step 8）
**发现版本**：V0.2b 开发中
**严重程度**：P1（需求遗漏）
**发现时间**：2025-03-01

**现象**：
从历史记录进入旧对话时，无法找到「查看复盘」按钮。

**根因**：
需求追溯缺口（Requirements Traceability Gap）。
SPEC_V02B.md 的 BDD Scenario 中有"历史对话的复盘随时可访问"场景，
但 Step 8 的执行指令生成时漏掉了这条场景的实现要求。

**修复方案**：
在 `CLAUDE_CODE_V02B_INSTRUCTIONS.md` 的 Step 8 中追加：
- 进入历史会话时，调用 `GET /review/{session_id}`
- 返回 200 → 右上角渲染「查看复盘」按钮
- 返回 404 → 静默处理，不显示按钮

**预防措施**：
CLAUDE_CODE_DOC_STANDARD V2.1 已在 BDD 层新增反问检查机制，此类问题将在最上游被拦截。

---

## 模板（新 Bug 记录格式）

```
### BUG-XXX：[简短描述]

**状态**：⬜ 待修复 / 🔄 修复中 / ✅ 已修复
**发现版本**：VX.X
**严重程度**：P0（阻断）/ P1（主流程）/ P2（体验）
**发现时间**：YYYY-MM-DD

**现象**：[用户看到了什么]

**根因**：[技术层面的原因]

**修复方案**：[怎么修复]

**修复验证**：[如何确认修复有效]
```
