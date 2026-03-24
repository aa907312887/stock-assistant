"""大盘温度规则与说明服务。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.market_temperature_copywriting import MarketTemperatureCopywriting
from app.models.market_temperature_level_rule import MarketTemperatureLevelRule
from app.services.market_temperature.constants import FORMULA_VERSION, LEVEL_RULES
from app.services.market_temperature.formula_explain_text import (
    FACTOR_EXPLAIN,
    SCORE_PIPELINE_BODY,
    SCORE_PIPELINE_TITLE,
)

_FACTOR_WEIGHT = {"趋势": 0.4, "量能": 0.3, "风险": 0.3}


def ensure_default_rules(db: Session) -> None:
    """插入默认分级；若已存在则按档位名同步 visual_token 等（便于色值升级）。"""
    by_name = {r.level_name: r for r in db.query(MarketTemperatureLevelRule).all()}
    for name, lo, hi, action, hint, color_hex in LEVEL_RULES:
        row = by_name.get(name)
        if row is None:
            db.add(
                MarketTemperatureLevelRule(
                    level_name=name,
                    score_min=Decimal(str(lo)),
                    score_max=Decimal(str(hi)),
                    strategy_action=action,
                    strategy_hint=hint,
                    visual_token=color_hex,
                    is_active=1,
                )
            )
        else:
            row.score_min = Decimal(str(lo))
            row.score_max = Decimal(str(hi))
            row.strategy_action = action
            row.strategy_hint = hint
            row.visual_token = color_hex
    explain = (
        db.query(MarketTemperatureCopywriting)
        .filter(
            MarketTemperatureCopywriting.content_type == "formula_explain",
            MarketTemperatureCopywriting.formula_version == FORMULA_VERSION,
            MarketTemperatureCopywriting.is_active == 1,
        )
        .first()
    )
    if not explain:
        db.add(
            MarketTemperatureCopywriting(
                content_type="formula_explain",
                title="大盘温度计算口径说明",
                content="本版本说明正文由接口内嵌的 score_pipeline 与 factors 提供；若需修订长文请改代码中文案并与 formula.md 同步。",
                formula_version=FORMULA_VERSION,
                is_active=1,
            )
        )
    db.commit()


def get_level_rules(db: Session) -> list[MarketTemperatureLevelRule]:
    return (
        db.query(MarketTemperatureLevelRule)
        .filter(MarketTemperatureLevelRule.is_active == 1)
        .order_by(MarketTemperatureLevelRule.score_min.asc())
        .all()
    )


def get_strategy_hint_by_level(db: Session, level_name: str) -> str:
    row = (
        db.query(MarketTemperatureLevelRule)
        .filter(MarketTemperatureLevelRule.level_name == level_name, MarketTemperatureLevelRule.is_active == 1)
        .first()
    )
    return row.strategy_hint if row else "保持纪律，控制风险。"


def get_formula_explain(db: Session, version: str | None) -> dict:
    version = version or FORMULA_VERSION
    row = (
        db.query(MarketTemperatureCopywriting)
        .filter(
            MarketTemperatureCopywriting.content_type == "formula_explain",
            MarketTemperatureCopywriting.formula_version == version,
            MarketTemperatureCopywriting.is_active == 1,
        )
        .first()
    )
    levels = get_level_rules(db)
    factors = [
        {
            "factor_name": fe["factor_name"],
            "weight": _FACTOR_WEIGHT[fe["factor_name"]],
            "description": fe["summary"],
            "calculation_detail": fe["calculation_detail"],
            "design_rationale": fe["design_rationale"],
        }
        for fe in FACTOR_EXPLAIN
    ]
    return {
        "formula_version": version,
        "score_pipeline": {
            "title": SCORE_PIPELINE_TITLE,
            "body": SCORE_PIPELINE_BODY,
        },
        "factors": factors,
        "levels": [
            {
                "level_name": x.level_name,
                "score_range": f"{x.score_min}-{x.score_max}",
                "action": x.strategy_action,
                "color": x.visual_token,
            }
            for x in levels
        ],
        "content": row.content if row else "",
        "updated_at": datetime.now(),
    }
