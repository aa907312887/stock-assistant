# 接口契约：投资逻辑（三面 · 历史 · 权重）

**基路径前缀**：`/api`（与 `main.py` 一致）。

**鉴权**：除登录外，均需 `Authorization: Bearer <access_token>`；所有操作仅针对**当前用户**的 `user_id`，路径中不出现他人 `user_id`。

---

## 1. 资源说明

- **投资逻辑条目** `InvestmentLogicEntry`：字段包括  
  `id`, `technical_content`, `fundamental_content`, `message_content`,  
  `weight_technical`, `weight_fundamental`, `weight_message`,  
  `created_at`, `updated_at`（ISO 8601 字符串或 Unix 毫秒，与项目现有 JSON 日期风格一致），  
  `extra_json`（object \| null，扩展字段，可缺省为 `null`）。约定 **`insights`**：`string[]`，表示「重要感悟」第1点、第2点…（与页面顺序一致）。

---

## 2. 查询「当前」条目（首页）

- **GET** `/api/investment-logic/current`  
- **响应 200**：  
  - 有「当前」条目：`{ "entry": { ... } }`  
  - 无任何条目：`{ "entry": null }`  

**说明**：不在 `POST /auth/login` 的 `UserOut` 中嵌入大段三面正文，避免登录响应臃肿；首页进入后调用本接口（可与 `GET /auth/me` 并行）。

---

## 3. 历史列表

- **GET** `/api/investment-logic/entries`  
- **Query（可选）**：`order` = `created_desc` | `created_asc`（默认 `created_desc`，最新在前）。  
- **响应 200**：`{ "items": [ { ... }, ... ] }`

---

## 4. 新增条目

- **POST** `/api/investment-logic/entries`  
- **请求体**（JSON）：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| technical_content | string | 否* | 技术面，* 与另两面至少一面非空 |
| fundamental_content | string | 否* | 基本面 |
| message_content | string | 否* | 消息面 |
| weight_technical | integer | 是 | 0–100 |
| weight_fundamental | integer | 是 | 0–100 |
| weight_message | integer | 是 | 0–100 |
| extra_json | object | 否 | 扩展键值，须可序列化为 JSON 对象；不传或 `null` 表示无扩展 |

- **成功 201**：`{ "entry": { ... } }`（`entry` 含 `extra_json`）

---

## 5. 修改条目

- **PUT** `/api/investment-logic/entries/{id}`  
- **路径参数**：`id` 为本用户某条条目的主键；若不存在或不属于当前用户 → **404**。  
- **请求体**：与 POST 相同字段（全量替换该条的三面正文与权重）；**`extra_json`** 若请求体中未出现该键，则**保留数据库中原有** `extra_json`；若显式传 `null` 则清空扩展字段。  
- **成功 200**：`{ "entry": { ... } }`  
- **副作用**：更新 `updated_at`。

---

## 6. 删除条目

- **DELETE** `/api/investment-logic/entries/{id}`  
- **成功 204**：无正文  
- **404**：条目不存在或无权

---

## 7. 错误约定

| HTTP | 场景 |
|------|------|
| 401 | 未认证 |
| 400 | 三面全空、权重和≠100、权重非整数或越界、正文超长、`extra_json` 非对象或不可解析 |
| 404 | 修改/删除时 id 不存在或非本人 |
| 500 | 服务错误 |

**detail** 使用中文可读短句，与现有 FastAPI 项目一致。

---

## 8. 非目标

- 不提供按其他用户查询的接口。  
- 不提供条目级「软删除」除非产品后续要求；默认物理删除。
