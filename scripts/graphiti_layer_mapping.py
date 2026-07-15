from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SagaLayerMeta:
    legacy_saga_key: str
    saga_key: str
    saga_name: str
    layer_id: int
    layer_name: str
    fact_set_name: str
    fact_set_type: str
    fact_set_description: str

    @property
    def display_name(self) -> str:
        return f"Layer {self.layer_id} {self.layer_name} / {self.fact_set_name}"

    @property
    def source_description(self) -> str:
        return f"半导体产业链图谱 {self.display_name}"

    def as_properties(self) -> dict[str, object]:
        return {
            "legacy_saga_key": self.legacy_saga_key,
            "saga_key": self.saga_key,
            "saga_name": self.saga_name,
            "layer_id": self.layer_id,
            "layer_name": self.layer_name,
            "fact_set_name": self.fact_set_name,
            "fact_set_type": self.fact_set_type,
            "fact_set_description": self.fact_set_description,
            "display_name": self.display_name,
        }


SAGA_LAYER_MAPPING: dict[str, SagaLayerMeta] = {
    "stage3_leadership": SagaLayerMeta(
        legacy_saga_key="stage3_leadership",
        saga_key="layer3_leadership",
        saga_name="Layer 3 企业实体层 / 龙头企业判断",
        layer_id=3,
        layer_name="企业实体层",
        fact_set_name="龙头企业判断",
        fact_set_type="leadership",
        fact_set_description="按产业环节整理国内外候选企业和代表企业，说明为什么可作为该环节龙头或代表企业。",
    ),
    "stage4_company_relationship": SagaLayerMeta(
        legacy_saga_key="stage4_company_relationship",
        saga_key="layer4_company_relationship",
        saga_name="Layer 4 关系事实层 / 企业产业关系",
        layer_id=4,
        layer_name="关系事实层",
        fact_set_name="企业产业关系",
        fact_set_type="company_relationship",
        fact_set_description="供应、授权、代工、封测、合作等企业主体之间的公开事实关系。",
    ),
    "stage6_company_product": SagaLayerMeta(
        legacy_saga_key="stage6_company_product",
        saga_key="layer4_company_product",
        saga_name="Layer 4 关系事实层 / 公司-产品服务关系",
        layer_id=4,
        layer_name="关系事实层",
        fact_set_name="公司-产品服务关系",
        fact_set_type="company_product_relation",
        fact_set_description="企业与产品服务之间的生产、销售、使用、采购、集成关系。",
    ),
    "stage6_company_competition": SagaLayerMeta(
        legacy_saga_key="stage6_company_competition",
        saga_key="layer4_company_competition",
        saga_name="Layer 4 关系事实层 / 竞争候选关系",
        layer_id=4,
        layer_name="关系事实层",
        fact_set_name="竞争候选关系",
        fact_set_type="competition_candidate",
        fact_set_description="同环节同产品企业之间的候选竞争关系，保留推定来源和验证限制。",
    ),
    "stage7_digital_china": SagaLayerMeta(
        legacy_saga_key="stage7_digital_china",
        saga_key="layer5_digital_china",
        saga_name="Layer 5 业务关联层 / 神州数码业务关系",
        layer_id=5,
        layer_name="业务关联层",
        fact_set_name="神州数码业务关系",
        fact_set_type="digital_china_relation",
        fact_set_description="公开确认、潜在匹配和需内部验证的神州数码业务关系，不把推断关系表述为客户事实。",
    ),
}


def meta_for_legacy_saga(legacy_saga_key: str) -> SagaLayerMeta:
    try:
        return SAGA_LAYER_MAPPING[legacy_saga_key]
    except KeyError as exc:
        raise KeyError(f"未配置 Saga Layer 映射：{legacy_saga_key}") from exc


def meta_for_any_saga(value: str) -> SagaLayerMeta | None:
    for meta in SAGA_LAYER_MAPPING.values():
        if value in {meta.legacy_saga_key, meta.saga_key, meta.saga_name, meta.display_name}:
            return meta
    return None
