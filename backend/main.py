import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sse_starlette.sse import EventSourceResponse
import asyncio
from dotenv import load_dotenv
from datetime import timedelta

from models import QueryRequest, UserCreate, Token, UserInDB, User
from auth import (
    get_password_hash,
    verify_password,
    get_user,
    create_access_token,
    get_current_active_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_db_collection
)

# Load environment variables
load_dotenv()

app = FastAPI(title="DocuTrust API")

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/register", response_model=User)
async def register(user: UserCreate):
    users_collection = get_db_collection()
    if get_user(user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    user_dict = user.model_dump()
    user_dict["hashed_password"] = hashed_password
    user_dict["is_active"] = True
    del user_dict["password"]
    
    users_collection.insert_one(user_dict)
    return User(**user_dict)

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/")
async def root():
    return {"message": "DocuTrust API is running."}

import tempfile
from document_processor import process_pdf

@app.post("/upload")
async def upload_document(file: UploadFile = File(...), current_user: User = Depends(get_current_active_user)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    # Save file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
        
    try:
        # Process it (chunking)
        chunks = process_pdf(tmp_path)
        
        # TODO: wire up store_in_mongodb_vector when DB is ready
        
        return {"filename": file.filename, "message": f"File uploaded and split into {len(chunks)} chunks successfully.", "num_chunks": len(chunks)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.remove(tmp_path)

from rag_pipeline import crag_app

@app.post("/query")
async def query_document(request: Request, body: QueryRequest, current_user: User = Depends(get_current_active_user)):
    async def event_generator():
        # Initialize state
        state = {"question": body.query, "documents": [], "logs": []}
        
        # We use a set to keep track of yielded logs so we only send new ones
        yielded_logs = set()

        try:
            # Stream the LangGraph execution
            for output in crag_app.stream(state):
                if await request.is_disconnected():
                    break
                
                # Get the state updates from the current node
                node_name = list(output.keys())[0]
                current_state = output[node_name]
                
                # Yield new logs
                new_logs = current_state.get("logs", [])
                for log in new_logs:
                    if log not in yielded_logs:
                        yield {
                            "event": "log",
                            "data": log
                        }
                        yielded_logs.add(log)
                        await asyncio.sleep(0.1) # Small delay for UI effect

            # After pipeline finishes, yield the final generated answer
            # We fetch the final state to get the generation
            # Langgraph stream yields dictionaries representing node updates.
            # The final update will come from the 'generate' node usually.
            final_generation = current_state.get("generation", "Error: No answer generated.")
            yield {
                "event": "result",
                "data": final_generation
            }

        except Exception as e:
            yield {
                "event": "log",
                "data": f"Pipeline Error: {str(e)}"
            }
            yield {
                "event": "result",
                "data": "Failed to process query due to internal error."
            }

    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
