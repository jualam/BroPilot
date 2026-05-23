from pydantic import BaseModel


class StartRunRequest(BaseModel):
    repo_path: str
    task: str