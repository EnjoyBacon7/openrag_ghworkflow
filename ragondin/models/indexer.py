from pydantic import BaseModel
from typing import Optional, List

class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5  # default to 5 if not provided


class DeleteFilesRequest(BaseModel):
    file_names: List[str]