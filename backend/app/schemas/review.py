from pydantic import BaseModel, Field


class FileDiffReviewRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    task: str = Field(default="", max_length=2000)
    before_contents: str = Field(default="", max_length=30000)
    after_contents: str = Field(default="", max_length=30000)


class FileDiffReviewResponse(BaseModel):
    summary: str
    model: str
