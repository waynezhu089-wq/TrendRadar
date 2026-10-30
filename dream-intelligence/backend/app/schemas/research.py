from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator, model_serializer
from .source_connections import SourceBinding

from app.research.websites import normalize_site_url
from app.research.image_sources import image_source_ids
from .image_vision import VisualReportOutput


class ResearchPlanInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    topics: list[str] = Field(min_length=1, max_length=8)
    websites: list[str] = Field(default_factory=list, max_length=5)
    source_bindings: list[SourceBinding] = Field(default_factory=list, max_length=5)
    purpose: str = Field(min_length=10, max_length=1000)
    collection_type: Literal['research', 'images', 'videos'] = 'research'

    @model_validator(mode='after')
    def image_source(self):
        if not self.websites and not self.source_bindings:
            raise ValueError('Choose at least one website or configured source')
        ids = [row.connection_id for row in self.source_bindings]
        if len(set(ids)) != len(ids) or len(self.websites) + len(ids) > 5:
            raise ValueError('Choose at most five distinct sources')
        if self.collection_type != 'research' and self.source_bindings:
            raise ValueError('Configured sources belong to information research')
        if self.collection_type == 'images':
            image_source_ids(self.websites)
        if self.collection_type == 'videos' and self.websites != ['https://www.youtube.com/']:
            raise ValueError('Video plans currently use https://www.youtube.com/ only')
        return self

    @model_serializer(mode='wrap')
    def legacy_shape(self, handler):
        result = handler(self)
        if not result.get('source_bindings'):
            result.pop('source_bindings', None)
        return result

    @field_validator("name", "purpose")
    @classmethod
    def strip_required(cls, value: str, info: ValidationInfo) -> str:
        value = " ".join(value.split())
        if not value or len(value) > 1000 or (info.field_name == "purpose" and len(value) < 10):
            raise ValueError("Value cannot be empty or too long")
        return value

    @field_validator("topics")
    @classmethod
    def clean_topics(cls, values: list[str]) -> list[str]:
        topics = list(dict.fromkeys(" ".join(value.split()) for value in values))
        if len(topics) != len(values) or any(not value or len(value) > 80 for value in topics):
            raise ValueError("Topics must be distinct and 1–80 characters")
        return topics

    @field_validator("websites")
    @classmethod
    def clean_websites(cls, values: list[str]) -> list[str]:
        # Website form entries may be bare public domains. Default those to
        # HTTPS here, while the lower-level fetch/redirect validator stays strict.
        sites = [normalize_site_url(value if "://" in value or value.startswith("//")
                                    else f"https://{value}") for value in values]
        if len(set(sites)) != len(sites):
            raise ValueError("Website URLs must be distinct")
        return sites


class ImageSourcesInput(BaseModel):
    websites: list[str] = Field(min_length=1, max_length=2)

    @field_validator('websites')
    @classmethod
    def supported_sources(cls, values):
        image_source_ids(values)
        return values


class ResearchPlanOutput(ResearchPlanInput):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ResearchFinding(BaseModel):
    item_id: int
    insight: str = Field(min_length=1, max_length=600)
    purpose_relevance: str = Field(min_length=1, max_length=600)
    suggested_action: str = Field(min_length=1, max_length=300)


class ResearchSection(BaseModel):
    category: Literal["模型与版本", "工具与插件", "工作流与应用", "教程与方法", "行业动态", "其他",
                      "社会与公共议题", "情感与生活", "教育与成长", "图书与阅读", "电影与影评"]
    summary: str = Field(min_length=1, max_length=1000)
    key_points: list[str] = Field(min_length=1, max_length=5)
    suggested_action: str = Field(min_length=1, max_length=300)
    item_ids: list[int] = Field(min_length=1, max_length=12)


class ResearchSummary(BaseModel):
    overview: str = Field(min_length=1, max_length=2000)
    findings: list[ResearchFinding] = Field(max_length=8)
    limitations: str = Field(max_length=1000)
    sections: list[ResearchSection] = Field(default_factory=list, max_length=6)


class ResearchItemOutput(BaseModel):
    id: int
    title: str
    url: str
    source: str
    published_at: datetime | None = None


class ResearchRunOutput(BaseModel):
    id: int
    plan_id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    received: int
    matched: int
    inserted: int
    errors: list[dict]
    summary: ResearchSummary | None
    items: list[ResearchItemOutput]
    images: list['ResearchImageOutput'] = Field(default_factory=list)
    image_summary: 'ImageSummaryOutput | None' = None
    visual_analysis: VisualReportOutput | None = None
    video_search: dict | None = None
    source_reports: list[dict] = Field(default_factory=list)


class ResearchImageOutput(BaseModel):
    id: int
    provider: str = 'openverse'
    title: str
    source_url: str
    image_url: str
    thumbnail_url: str
    creator: str
    license: str
    license_url: str
    attribution: str
    width: int | None
    height: int | None
    favorite: bool
    downloaded: bool
    recommended: bool
    reason: str
    usage_notes: str


class ImageSummaryOutput(BaseModel):
    overview: str
    limitations: str
    kind: Literal['analysis', 'search'] = 'analysis'


ResearchRunOutput.model_rebuild()
