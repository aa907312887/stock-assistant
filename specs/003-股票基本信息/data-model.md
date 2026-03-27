# 数据模型：股票基本信息（003）

**功能**: 003-股票基本信息 | **日期**: 2026-03-21

## 1. 概述

本功能**不新增**核心业务表，读写现有表 **`stock_basic`**（与 `002`、数据库设计文档一致）。同步任务仅对该表做 **INSERT/UPDATE**（按 `code` 唯一键语义）。

## 2. 实体：股票基本信息（`stock_basic`）

| 逻辑字段 | 物理列（参考） | 类型 | 说明 |
|----------|----------------|------|------|
| 证券代码 | `code` | VARCHAR(20) UNIQUE | 主业务键，如 `000001.SZ` |
| 名称 | `name` | VARCHAR(100) | 股票简称 |
| 交易所 | `exchange` | VARCHAR(10) | Tushare `exchange`（SSE/SZSE/BSE） |
| 板块 | `market` | VARCHAR(20) | Tushare `market`（主板/创业板/科创板/北交所等） |
| 行业代码 | `industry_code` | VARCHAR(20) | 可选，来自数据源 |
| 行业名称 | `industry_name` | VARCHAR(100) | 展示与筛选 |
| 地域 | `region` | VARCHAR(50) | 对应 Tushare `area` |
| 上市日期 | `list_date` | DATE | 展示 |
| 数据来源 | `data_source` | VARCHAR(32) | 默认 `tushare` |
| 同步批次 | `sync_batch_id` | VARCHAR(64) | 基础同步可带 `basic-` 前缀便于区分 |
| 同步时间 | `synced_at` | DATETIME | 行级刷新时间；列表接口取 **MAX** 作整表新鲜度参考 |
| 创建/更新 | `created_at` / `updated_at` | DATETIME | ORM 维护 |

**唯一约束**: `code` 唯一。

**索引**: 已有 `code`、`exchange`、`market`、`industry_code`、`list_date` 等索引，支持筛选与排序。

## 3. 关系

- 与 `stock_daily_quote`、`stock_financial_report` 等**无外键**，通过 `code` / `stock_code` 逻辑关联（本功能不修改从表）。

## 4. 校验与口径

- `code` 非空；其余字段允许为空（数据源缺失时）。
- 上市日期、行业等以数据源为准；本功能不负责财务或行情校验。

## 5. 数据量与性能

- 全市场约数千行；分页查询使用 `LIMIT` + `OFFSET`（或等价），单页默认 20 条、最大 100 条。
