from pydantic import BaseModel
from typing import List, Optional, Any

class QueryRequest(BaseModel):
    query: str

class DocumentMetadata(BaseModel):
    filename: str
    num_chunks: int
    
class ChatMessage(BaseModel):
    role: str
    content: str
    
# This can be expanded based on the log structure we want to send back via SSE
class LogEvent(BaseModel):
    event_type: str  # e.g., "retrieving", "grading", "rewriting", "generating", "complete", "error"
    content: str
    data: Optional[Any] = None

# Authentication Models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class User(BaseModel):
    email: str
    is_active: Optional[bool] = True

class UserCreate(BaseModel):
    email: str
    password: str

class UserInDB(User):
    hashed_password: str
