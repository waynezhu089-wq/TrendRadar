from typing import Literal

from pydantic import BaseModel

FeedbackValue = Literal["useful", "not_useful", "watch"]


class FeedbackInput(BaseModel):
    item_id: int
    feedback: FeedbackValue


class FeedbackOutput(BaseModel):
    item_id: int
    feedback: FeedbackValue
