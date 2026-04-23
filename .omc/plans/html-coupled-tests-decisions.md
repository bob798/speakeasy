# P0-T1 产物 · HTML 耦合测试决策表

> 由 `scripts/scan_html_coupled_tests.sh` 扫描产生，9 个文件与 Critic Pass 2 B1 fix 预期吻合。
>
> 每个文件的处置决策（保留 / 改写 / 废弃）及落点 Phase。

## 扫描命令

```bash
bash scripts/scan_html_coupled_tests.sh
# 输出: 耦合测试文件数 = 9，闸门 ✅ 通过
```

## 耦合模式

全部 9 个测试都是 V0.7 step 集成测试，通过 `Path("static/practice.html").read_text()` 或 `Path("static/js/ask-panel.js").read_text()` 读取文件内容，断言特定 UI 元素/函数存在。具体耦合点：

| 文件 | 耦合对象 | 行号 | 断言主题 |
|---|---|---|---|
| `test_v07_followup.py` | `static/practice.html` | 12 | V0.7 AskPanel 第二轮追问 |
| `test_v07_followup2.py` | `static/practice.html` | 9 | AskPanel 持久化 thread |
| `test_v07_step4.py` | `static/js/ask-panel.js` | 7 | AskPanel 组件契约 |
| `test_v07_step5.py` | `static/practice.html` + `static/js/ask-panel.js` | 6, 11 | AskPanel 脚本引入 |
| `test_v07_step6.py` | `static/practice.html` | 104 | 解读弹窗 UI 集成 |
| `test_v07_step7.py` | `static/practice.html` | 6 | 流式解读渲染 |
| `test_v07_step8.py` | `static/practice.html` | 76 | 发音卡片 FSRS 集成 |
| `test_v07_step9.py` | `static/practice.html` | 71 | 生词本联动 |
| `test_v07_step10.py` | `static/practice.html` | 168 | 完整 V0.7 回归 |

## 决策表

### 决策规则

- **保留**：Phase 0–4 期间不动；Phase 5 切挂载时把断言路径从 `static/` 改为 `legacy/static/`（`/legacy/*` 回滚路径下仍可达）
- **改写**：业务语义移到前端，后端测试废弃；由 Vitest 在 `frontend/src/__tests__/` 等价覆盖
- **废弃**：测试已失去意义（如断言旧 DOM 结构），直接删除，Vue 版本不存在对应 DOM

### 每文件决策

| 文件 | 决策 | 落点 Phase | 理由 |
|---|---|---|---|
| `test_v07_followup.py` | **保留** | Phase 5-T4 改路径 | 业务场景（AskPanel 续问）仍有效，但 DOM 路径变化 → 断言指向 `/legacy/static/practice.html` |
| `test_v07_followup2.py` | **保留** | Phase 5-T4 改路径 | 同上 |
| `test_v07_step4.py` | **改写** | Phase 2b AskPanel 迁移时 | 断言 `ask-panel.js` 具体实现 → Vue SFC 后用 Vitest 组件测试替代，后端测试废弃 |
| `test_v07_step5.py` | **改写** | Phase 2b AskPanel 迁移时 | 断言 `<script src="/static/js/ask-panel.js">` 存在 → Vue SFC 模式无此标签，Vitest 组件 mount 测试替代 |
| `test_v07_step6.py` | **保留** | Phase 5-T4 改路径 | ExplanationModal 业务场景不变，改路径即可 |
| `test_v07_step7.py` | **保留** | Phase 5-T4 改路径 | 流式解读 NDJSON 后端契约不变，前端 DOM 断言改路径 |
| `test_v07_step8.py` | **保留** | Phase 5-T4 改路径 | 发音卡片 + FSRS 后端逻辑稳定 |
| `test_v07_step9.py` | **保留** | Phase 5-T4 改路径 | 生词本联动业务稳定 |
| `test_v07_step10.py` | **保留** | Phase 5-T4 改路径 | 完整回归套件，路径替换即可 |

### 汇总

- **保留**：7 个（路径替换，工作量 ~0.5d）
- **改写**：2 个（`step4` + `step5` → Vitest 组件测试等价覆盖，工作量 ~1d，落 Phase 2b）
- **废弃**：0 个

## 预期动作时序

```
Phase 2b（D13–D16 Chat 高复杂度 + AskPanel 迁移）
  └─ step4 + step5 改写为 Vitest（frontend/src/components/chat/__tests__/AskDrawer.spec.js）
     删除 tests/test_v07_step4.py / test_v07_step5.py
     commit: "test(v07): migrate AskPanel assertions from pytest to Vitest"

Phase 5-T4（D30 附近 挂载切换）
  └─ 7 个保留文件 sed -i 's|static/practice.html|legacy/static/practice.html|g'
     同步改写 pytest fixture
     commit: "test(v07): redirect HTML-coupled assertions to /legacy path"
     验证: pytest tests/ -v 全绿
```

## 闸门达成判据

- [x] 扫描脚本落盘（`scripts/scan_html_coupled_tests.sh`）
- [x] 清单输出（`.omc/plans/html-coupled-tests.txt`）
- [x] 数量 = 9（Critic B1 预期吻合）
- [x] 每个文件标注保留/改写/废弃决策
- [x] 决策表落盘（本文件）

**P0-T1 完成 ✅**
