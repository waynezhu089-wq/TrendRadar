from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .research import ResearchPlanInput, ResearchPlanOutput


class AssistantMessage(BaseModel):
    role: Literal['user', 'assistant']
    content: str = Field(min_length=1, max_length=3000)

    @field_validator('content')
    @classmethod
    def nonblank_message(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Enter a requirement')
        return value


class PlanAssistantInput(BaseModel):
    messages: list[AssistantMessage] = Field(min_length=1, max_length=12)
    current_draft: ResearchPlanInput | None = None

    @model_validator(mode='after')
    def bounded_conversation(self):
        if self.messages[0].role != 'user' or self.messages[-1].role != 'user':
            raise ValueError('Conversation must begin and end with user input')
        if sum(len(message.content) for message in self.messages) > 12000:
            raise ValueError('Conversation is too long')
        return self


class DeferredSource(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=300)


class PlanProposal(BaseModel):
    status: Literal['needs_details', 'draft_ready']
    message: str = Field(min_length=1, max_length=1000)
    questions: list[str] = Field(default_factory=list, max_length=3)
    plan: ResearchPlanInput | None = None
    deferred_sources: list[DeferredSource] = Field(default_factory=list, max_length=5)

    @model_validator(mode='after')
    def consistent_state(self):
        if self.status == 'draft_ready' and (self.plan is None or self.questions):
            raise ValueError('A ready draft needs a plan and no unanswered questions')
        if self.status == 'needs_details' and (not self.questions or self.plan is not None):
            raise ValueError('Ask for missing details before producing a plan')
        if any(not question.strip() or len(question) > 300 for question in self.questions):
            raise ValueError('Invalid clarification question')
        return self


class SourceNote(BaseModel):
    url: str
    name: str
    scope: str


class PlanAssistantOutput(PlanProposal):
    sources: list[SourceNote] = Field(default_factory=list)


class ConfirmPlanInput(BaseModel):
    plan: ResearchPlanInput
    confirmed: bool = Field(strict=True)

    @field_validator('confirmed')
    @classmethod
    def require_confirmation(cls, value):
        if value is not True:
            raise ValueError('Review the draft before creating a plan')
        return value


class ConfirmPlanOutput(BaseModel):
    plan: ResearchPlanOutput
    created: bool
