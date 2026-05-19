# Article Explain → Vocab 自动入库流

> V0.8 引入。spec: docs/superpowers/specs/2026-05-19-articles-vocab-tag-design.md

## 触发

用户在 `/articles` 文章页点击词/句子触发 ExplanationModal，发起以下三种请求之一：
- `POST /articles/explain` (单次词解读)
- `POST /articles/explain/phonetic` (IPA 本地秒出)
- `POST /articles/explain/stream` (流式句子解读)

请求体携带 `source_type='bbc_eaw'`、`source_ref=<slug>`、`item_type`。

## 路由层流程

1. 入口处调 `_auto_save_vocab(...)` 占位写入 vocabulary（`explanation_json=NULL`）
   - 唯一键 `(user_id, source_text, source_ref)` 命中 → 复活已删除条目，否则保持现状
   - 写入失败仅 `logger.warning`，不影响后续解读返回
2. 调用 explain_service 拿解读结果（缓存命中或流式）
3. 解读完成 → 调 `vocab_service.update_explanation(..., force=req.refresh)` 回填 `explanation_json`
   - `force=False`（默认）：仅在原值为 NULL 时填入
   - `force=True`（用户带 refresh）：强制覆盖

## 可靠性边界（best-effort）

- **入口占位写入**：与前端生命周期解耦，地铁断网/切走依然有 pending 记录
- **流末尾回填**：耦合在 generator 末尾，**best-effort**。客户端在流式过程中断开 → Starlette 抛 `ClientDisconnect` → generator 未跑到末尾 → 回填不执行
- **断流恢复路径**：pending 留存 → 用户从 `/vocabulary` 点开条目 → 前端再次调 `/articles/explain` → 这次客户端正常消费完整响应 → 后端回填
- 不引入 background task / Celery：与本项目规模匹配，少做不少错

## 数据语义

- `vocabulary.status='active' AND explanation_json IS NULL` → pending（生词本前端显示"⚠ 解读生成中"）
- pending 条目用户点开 → 前端再次调 `/articles/explain*` → 回填

## 关键日志锚点

- `vocab_auto_save_attempt`
- `vocab_explanation_backfill` / `vocab_explanation_backfill_miss`
- `vocab_auto_save_failed`
