from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

VisualCategory = Literal['色彩与氛围','场景与空间','构图与镜头','人物与造型','其他']


class VisualObservation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    image_id: int = Field(gt=0)
    readable: bool
    description: str = Field(min_length=1,max_length=300)
    scene: str = Field(max_length=200)
    lighting: str = Field(max_length=200)
    colors: list[str] = Field(max_length=6)
    composition: str = Field(max_length=250)
    category: VisualCategory
    fit: Literal['MATCH','PARTIAL','NOT_MATCH']
    purpose_relevance: str = Field(min_length=1,max_length=400)
    suggestion: str = Field(max_length=400)
    uncertainty: str = Field(max_length=300)
    watermark: Literal['VISIBLE','NOT_VISIBLE','UNCERTAIN']


class VisualGroup(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: VisualCategory
    summary: str = Field(min_length=1,max_length=600)
    key_points: list[str] = Field(min_length=1,max_length=3)
    suggested_action: str = Field(max_length=400)
    image_ids: list[int] = Field(min_length=1,max_length=12)


class VisualModelReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    overview: str = Field(min_length=1,max_length=1200)
    observations: list[VisualObservation] = Field(min_length=1,max_length=12)
    groups: list[VisualGroup] = Field(max_length=5)


class VisualReportOutput(VisualModelReport):
    run_id: int
    model: str
    analyzed_at: datetime
    analyzed_count: int
    candidate_count: int
    input_hash: str
    image_hashes: dict[str,str]
    errors: list[dict]
    usage: dict[str,int] | None = None
    cached: bool = False
