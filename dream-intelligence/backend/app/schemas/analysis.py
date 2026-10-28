from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Score = Annotated[int, Field(strict=True, ge=0, le=100)]
Text = Annotated[str, Field(strict=True, min_length=1, max_length=2000)]

class AnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    category: Literal["AI", "AI_VIDEO", "GITHUB", "CHINA_TRENDS", "MARKET", "OTHER"]
    summary: Text
    why_it_matters: Text
    importance: Score
    novelty: Score
    credibility: Score
    personal_relevance: Score
    dreamstream_relevance: Score
    actionability: Score
    tags: list[Annotated[str, Field(strict=True, min_length=1, max_length=100)]] = Field(max_length=20)
    recommended_action: Literal["READ", "WATCH", "IGNORE"]
