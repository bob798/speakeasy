# Translate 自动入生词本 — 设计

- 状态: Draft
- 日期: 2026-05-20
- 范围: Translate 页 + 后端 `/translate/text` + `vocab_service`
- 对齐: V0.8 「解读发起即自动写入 vocabulary」的同构模式

---

## 1. 目标

让 Translate 页和文章学习的解读体验对齐:**用户翻译过的内容自动进入生词本**,不再需要手动点「⭐ 收藏到生词本」。同时在 UI 上把这条能力讲明白。

非目标:
- 不重做生词本页的 tab/标签/列表
- 不改去重逻辑(UNIQUE(user_id, source_text, source_ref) 保持原样)
- 不引入新的生词本来源类型(仍为 `source_type='translate'`)

---

## 2. 用户场景

| 状态 | 行为 |
|---|---|
| 已登录用户输入文本 → 点「翻译」 | 译文显示;后台已把这条以 sentence/translate 入库;UI 一句「⭐ 已加入生词本」提示 |
| 已登录用户翻译同一文本第二次 | 译文显示;生词本中仍是同一条,translated_text 用最新译文覆盖 |
| 已登录用户翻译曾软删的文本 | 译文显示;原条目复活(status='active'),translated_text 回填 |
| 匿名用户点「翻译」 | 译文正常显示;生词本不入库;页面顶部提示「登录后翻译会自动收藏」 |
| 翻译服务报错 | 503 提示用户重试;若占位行已写,留存(下次重试自动回填) |
| 携带非法/过期 JWT | 视作匿名,不抛 401,翻译仍可用 |

---

## 3. 后端契约

### 3.1 `POST /translate/text` 升级

```
Auth        Optional JWT (使用新的 get_optional_user_id 依赖)
Request     { text: str, direction: 'zh2en'|'en2zh' }
Response    {
              translated_text: str,
              saved_to_vocab: bool,
              vocab_id: int | null
            }
```

**向后兼容:** 新增字段为可选,旧调用方忽略即可。

### 3.2 路由内部流程

```python
1. 参数校验(空 / >1000 字符)— 现状不变
2. direction 白名单校验(必为 'zh2en' | 'en2zh',非法即 400)
   ↑ 提前到占位写入之前,避免非法 direction 在 vocab 表留空白行
3. user_id = await get_current_user_id_optional(authorization)
4. vocab_id = None
   if user_id:
       try:
           item = save_item(
               user_id=user_id,
               source_text=req.text,
               translated_text="",
               direction=req.direction,
               item_type="sentence",
               source_type="translate",
               source_ref=None,
           )
           vocab_id = item["id"]
       except Exception as e:
           logger.warning("translate_placeholder_save_fail user=%s err=%s", user_id, e)
           vocab_id = None  # 降级:翻译继续,不入库
5. translated = await translate_text(req.text, req.direction)
6. if user_id and vocab_id and translated:
       try:
           update_translated_text(
               user_id=user_id,
               source_text=req.text,
               source_ref=None,
               translated_text=translated,
               force=True,
           )
       except Exception as e:
           # 回填失败不能把已成功的翻译降级成 503
           logger.warning(
               "translate_backfill_fail user=%s vocab_id=%s err=%s",
               user_id, vocab_id, e,
           )
7. return {
       "translated_text": translated,
       "saved_to_vocab": bool(vocab_id),
       "vocab_id": vocab_id,
   }
```

> **direction 校验**:现状 `translate_service.translate_text()` 内部抛 `ValueError`。本次把校验前置到路由层(白名单 set 比对),service 校验保留作兜底。

### 3.3 复用现有 `get_current_user_id_optional`

位置: `app/routers/auth.py:73-80`(已存在,无需新增)

```python
async def get_current_user_id_optional(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """同 get_current_user_id 但未提供 token 时返回 None 而不抛异常"""
```

- 直接 `Depends(get_current_user_id_optional)`
- 不引入第二个 optional auth 依赖(避免 auth 行为分裂在两处维护)

### 3.4 新增 service 函数 `update_translated_text`

位置: `app/services/vocab_service.py`

```python
def update_translated_text(
    user_id: str,
    source_text: str,
    source_ref: Optional[str],
    translated_text: str,
    force: bool = True,
) -> bool:
    """回填 translated_text。

    默认覆盖(force=True),保持「页面看到啥 = 生词本里是啥」。
    找不到记录返回 False,不抛异常。
    """
```

- 与 `update_explanation` 同构,只换字段
- `save_item` 命中已存在条目时不更新 translated_text 的语义保留,回填走专门函数

---

## 4. 前端 UI 改动

文件: `frontend/src/views/Translate.vue`

### 4.1 顶部能力说明条(新)

位置: `<header class="topbar">` 之下,`<section class="pair">` 之上。

- 登录态: `✨ 翻译过的内容会自动加入生词本`
- 匿名态: `✨ 登录后翻译会自动加入生词本 [去登录]`

「去登录」走现有登录入口(项目已有 RouterLink 或 modal,实施时沿用)。

### 4.2 译文卡片下方状态行(替换原按钮)

- **删除:** 现有 `<button class="save" @click="onSave">⭐ 收藏到生词本</button>`
- **新增(仅登录态、且 `saved_to_vocab === true` 时):**
  ```
  ⭐ 已加入生词本 · 查看生词本 →
  ```
  「查看生词本」链接到 `/vocabulary`。

匿名态:不显示状态行,顶部说明条已经说明了原因。

### 4.3 底部 vocab-hint

保持现状不动:「收藏的译文可在 [生词本] 中查看与复习」。

### 4.4 JS 改动

```js
const savedToVocab = ref(false)

async function onTranslate() {
  // ...
  const data = await authFetchJson(`${API.TRANSLATE}/text`, { text, direction })
  translated.value = data.translated_text || ''
  savedToVocab.value = !!data.saved_to_vocab
}
```

- 删除 `onSave()` 函数及相关 toast 分支
- 登录态判定:沿用项目现有约定(token 存在性或 `useAuth` composable),实施时按现有代码风格读取

---

## 5. 测试计划

### 5.1 后端 `tests/test_translate_auto_vocab.py` (新文件)

| 用例 | 期望 |
|---|---|
| `test_anonymous_translate_no_vocab` | 200, saved_to_vocab=False, vocab_id=None;vocabulary 表无新增 |
| `test_logged_in_translate_creates_vocab` | 200, saved_to_vocab=True;库内有一条 (user_id, source_text, source_ref=None),translated_text 已回填,item_type='sentence', source_type='translate' |
| `test_logged_in_translate_idempotent` | 同一用户连续翻译两次同一文本,vocab_id 相同;表内仅 1 行;translated_text 为第二次结果(force 覆盖) |
| `test_logged_in_translate_resurrects_deleted` | 预先 soft-delete 一条同 source_text → 翻译后 status='active' 复活、translated_text 已回填 |
| `test_translate_failure_keeps_placeholder` | mock `translate_text` 抛异常 → 503;占位条目仍在(translated_text="") |
| `test_invalid_token_falls_back_anonymous` | 非法 Authorization → 200, saved_to_vocab=False(不抛 401) |
| `test_save_placeholder_failure_degrades` | mock `save_item` 抛异常 → 翻译仍 200 返回译文,saved_to_vocab=False;有 warning 日志 |
| `test_backfill_failure_degrades` | mock `update_translated_text` 抛异常 → 翻译仍 200 返回译文,saved_to_vocab=True(占位仍在),vocab_id 有值;有 warning 日志 |
| `test_invalid_direction_no_placeholder` | 登录态 + direction='xx' → 400;vocabulary 表无新增空白行 |

测试规范遵循 `.claude/CLAUDE.md`:
- 独立 user_id (`test_user_translate_autovocab_xxx`)
- autouse fixture 清理 vocabulary 表对应 user_id 数据
- mock 仅作用于外部 LLM 调用(`translate_text` 的 LLM 部分);DB 用真实 SQLite

### 5.2 前端 `frontend/src/views/__tests__/Translate.spec.js`

- 匿名:渲染「登录后翻译会自动加入生词本」;翻译完成后不渲染「⭐ 已加入生词本」
- 登录 + saved_to_vocab=true:顶部渲染「翻译过的内容会自动加入生词本」;译文出现后渲染「⭐ 已加入生词本」状态行
- 登录 + saved_to_vocab=false(降级场景):状态行不显示
- 旧「⭐ 收藏到生词本」按钮在任何状态下都不存在于 DOM

### 5.3 回归

- `tests/test_translate*.py` 中匿名调用 200 路径仍通(响应多两个字段,旧断言只看 `translated_text` 不受影响)
- `tests/test_vocab*.py` 不受影响(`save_item` / `list_items` 行为未改)

---

## 6. 风险与权衡

**风险 1: 误翻译污染生词本**
- 用户随手翻一个错字 / 半句话也会被记录
- 缓解:用户可在生词本页软删;若反馈集中可在后续版本加「最小长度阈值」过滤
- 当下不做最小长度过滤,保持与 V0.8 解读模式一致

**风险 2: 占位条目残留(翻译失败时)**
- 翻译挂掉,占位条目 translated_text="" 仍在生词本中
- 当前选择:保留,以便重试时回填
- 缓解:生词本页对 `translated_text=""` 显示「—」,与现状一致

**风险 3: `translated_text` 覆盖语义改变**
- 旧:`save_item` 命中已存在条目不更新任何字段
- 新:`update_translated_text(force=True)` 主动覆盖最新译文
- 影响范围:仅 Translate 路径,BBC / explain 路径走各自的 update 函数,互不干扰

**风险 4: JWT 非法时静默降级**
- 旧 token 没失效但前端没刷新:用户以为登录态,实际匿名翻译,生词本无记录
- 缓解:顶部能力条根据本地登录态显示「翻译过的内容会自动加入生词本」,但响应 `saved_to_vocab=false` 时不显示状态行 → 用户能从「状态行没出现」感知异常
- 长期方案在 auth 体系侧统一,不在本次范围

---

## 7. 实施清单(给 writing-plans 的输入)

- [ ] 后端:`app/services/vocab_service.py` 新增 `update_translated_text`
- [ ] 后端:`app/routers/translate.py` 改造 `do_translate`
  - 复用 `get_current_user_id_optional`(无需新增 auth 依赖)
  - direction 白名单校验提前到占位写入之前
  - update_translated_text 用 try/except 包住,失败不影响翻译返回
  - 扩响应字段 `saved_to_vocab` / `vocab_id`
- [ ] 后端测试:`tests/test_translate_auto_vocab.py`(测试用例见 §5.1,新增覆盖 backfill 失败降级)
- [ ] 前端:`frontend/src/views/Translate.vue` 顶部能力条、状态行、删按钮、JS 调整
- [ ] 前端测试:`frontend/src/views/__tests__/Translate.spec.js`
- [ ] 文档:`.claude/CLAUDE.md` 接口清单中 `/translate/text` 注记响应字段扩展
- [ ] 文档:`docs/architecture/c4-container.md` 如有翻译模块视图,补一句「认证可选 + 自动入库」

---

## 8. Codex Review 回应(2026-05-20)

| Codex 反馈 | 严重度 | 处理 |
|---|---|---|
| direction 校验需在占位写入之前 | P2 | 已修 §3.2 step 2 提前 |
| update_translated_text 失败要降级,不能拖垮翻译 | P2 | 已修 §3.2 step 6 加 try/except |
| 应复用已有 `get_current_user_id_optional`,不要新增 | P3 | 已修 §3.3 改"复用" |
