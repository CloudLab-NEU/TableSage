from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict
from typing import List, Any, Optional
from db.db_manager import DatabaseManager
from datetime import datetime

router = APIRouter(prefix="/api/chat", tags=["聊天历史"])

class ChatMessage(BaseModel):
    model_config = ConfigDict(extra='allow')
    
    id: Optional[Any] = None
    type: str # 'user' or 'assistant'
    content: str
    timestamp: Optional[Any] = None
    isProcessing: Optional[bool] = False
    processingSteps: Optional[List[Any]] = None

class ChatSessionSave(BaseModel):
    user_id: str
    session_id: str
    title: str
    messages: List[ChatMessage]

def get_db():
    return DatabaseManager()

@router.get("/sessions/{user_id}")
async def get_sessions(user_id: str, db: DatabaseManager = Depends(get_db)):
    sessions = db.get_user_sessions(user_id)
    # Convert MongoDB BSON formats to JSON serializable
    for s in sessions:
        s["_id"] = str(s["_id"])
        if "created_at" in s: s["created_at"] = s["created_at"].isoformat()
        if "updated_at" in s: s["updated_at"] = s["updated_at"].isoformat()
    return sessions

@router.get("/sessions/{user_id}/{session_id}")
async def get_session_detail(user_id: str, session_id: str, db: DatabaseManager = Depends(get_db)):
    session = db.get_chat_session(user_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session["_id"] = str(session["_id"])
    return session

@router.post("/sessions")
async def save_session(session: ChatSessionSave, db: DatabaseManager = Depends(get_db)):
    # Convert pydantic models to dicts for MongoDB
    messages_dict = [m.model_dump() for m in session.messages]
    db.save_chat_session(session.user_id, session.session_id, session.title, messages_dict)
    return {"message": "Session saved"}

@router.delete("/sessions/{user_id}/{session_id}")
async def delete_session(user_id: str, session_id: str, db: DatabaseManager = Depends(get_db)):
    db.delete_chat_session(user_id, session_id)
    return {"message": "Session deleted"}
