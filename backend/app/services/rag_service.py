import os
from typing import AsyncIterator
from datetime import datetime

from app.config import settings
from app.database import query_logs_collection
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_llm():
    if settings.USE_OLLAMA:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0
        )
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o", temperature=0, openai_api_key=settings.OPENAI_API_KEY)


def _get_retriever():
    """Return a retriever from MongoDB Atlas vector store, or a mock for local dev."""
    if settings.MONGODB_URI and settings.MONGODB_URI != "your_mongodb_atlas_uri_here":
        from pymongo import MongoClient
        from langchain_mongodb import MongoDBAtlasVectorSearch
        
        sync_client = MongoClient(settings.MONGODB_URI)
        collection = sync_client[settings.MONGODB_DB_NAME]["chunks"]
        
        if settings.USE_OLLAMA:
            from langchain_ollama import OllamaEmbeddings
            embeddings = OllamaEmbeddings(
                model=settings.OLLAMA_EMBEDDING_MODEL,
                base_url=settings.OLLAMA_BASE_URL
            )
        else:
            from langchain_openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
        
        vector_store = MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=embeddings,
            index_name="default"
        )
        return vector_store.as_retriever(search_kwargs={"k": 4})
    return None


async def run_rag_pipeline(
    query: str,
    user_email: str,
    document_ids: list = None
) -> AsyncIterator[dict]:
    """
    Run the CRAG pipeline and yield SSE-compatible events.
    Logs query + answer to MongoDB for analytics.
    """
    from rag_pipeline import crag_app
    import json
    import asyncio
    
    start_time = datetime.utcnow()
    state = {
        "question": query,
        "documents": [],
        "logs": [],
        "document_ids": document_ids,
        "web_search_required": False
    }
    yielded_logs = set()
    final_generation = "No answer generated."
    retrieved_documents = []
    web_search_used = False

    try:
        for output in crag_app.stream(state):
            node_name = list(output.keys())[0]
            current_state = output[node_name]

            # Track documents and logs
            retrieved_documents = current_state.get("documents", [])
            web_search_used = current_state.get("web_search_required", False) or web_search_used

            new_logs = current_state.get("logs", [])
            for log in new_logs:
                if log not in yielded_logs:
                    yield {"event": "log", "data": log}
                    yielded_logs.add(log)

        final_generation = current_state.get("generation", "No answer generated.")

        # Calculate Confidence Score
        if web_search_used:
            confidence = 45.0  # Web search fallback has lower confidence
        elif not retrieved_documents:
            confidence = 10.0  # No source context
        else:
            # High confidence based on document matching
            confidence = 85.0 + min(len(retrieved_documents) * 3.0, 10.0)

        # Emit Metadata for Source Preview and Confidence Meter
        sources_meta = []
        for doc in retrieved_documents:
            meta = doc.get("metadata", {})
            sources_meta.append({
                "source": meta.get("source", "Unknown"),
                "page": meta.get("page", "1"),
                "text": doc.get("page_content", ""),
            })

        metadata_payload = {
            "confidence_score": confidence,
            "sources": sources_meta
        }
        yield {"event": "metadata", "data": json.dumps(metadata_payload)}

        # Stream answer token-by-token (word-by-word)
        words = final_generation.split(" ")
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            yield {"event": "token", "data": token}
            await asyncio.sleep(0.02)  # Short typing animation delay

        # Final result event (for backward compatibility)
        yield {"event": "result", "data": final_generation}
        logger.info("rag_query_complete", user=user_email, query=query[:60], confidence=confidence)

    except Exception as e:
        logger.error("rag_pipeline_error", error=str(e), user=user_email)
        yield {"event": "log", "data": f"Pipeline error: {str(e)}"}
        yield {"event": "result", "data": "Failed to process your query due to an internal error."}
    finally:
        # Log to DB for analytics if MongoDB is configured
        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        try:
            if settings.MONGODB_URI and settings.MONGODB_URI != "your_mongodb_atlas_uri_here":
                import asyncio
                await asyncio.wait_for(
                    query_logs_collection.insert_one({
                        "user_email": user_email,
                        "query": query,
                        "answer": final_generation,
                        "latency_ms": round(latency_ms, 2),
                        "created_at": datetime.utcnow(),
                    }),
                    timeout=0.5
                )
        except Exception as e:
            logger.warning("query_log_skipped", reason=str(e))
