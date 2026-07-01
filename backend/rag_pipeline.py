import os
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from sentence_transformers import CrossEncoder
from langchain_community.tools import DuckDuckGoSearchRun

from dotenv import load_dotenv

load_dotenv()

class GraphState(TypedDict):
    """
    Represents the state of our graph.
    """
    question: str
    generation: str
    web_search_required: bool
    documents: List[dict]
    logs: List[str]
    document_ids: Optional[List[str]]

# Initialize models dynamically based on env
use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
if use_ollama:
    from langchain_ollama import ChatOllama
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0
    )
else:
    llm = ChatOpenAI(model="gpt-4", temperature=0)
# Local cross-encoder for grading chunk relevance
try:
    grader_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)
except Exception as e:
    grader_model = None
    print("Warning: Cross-encoder could not be loaded locally.", e)

def retrieve(state: GraphState):
    """Retrieve documents from Vector Store"""
    print("---RETRIEVE---")
    question = state["question"]
    logs = state.get("logs", [])
    
    mongodb_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "docutrust_db")
    collection_name = os.getenv("MONGODB_COLLECTION", "documents")
    
    documents = []
    
    document_ids = state.get("document_ids", None)
    
    # Check in-memory DB first
    try:
        from app.services.doc_service import IN_MEMORY_DB
    except ImportError:
        IN_MEMORY_DB = []

    in_memory_chunks = []
    for doc in IN_MEMORY_DB:
        # Filter by selected document IDs if provided
        if document_ids is not None and doc.get("id") not in document_ids:
            continue
        in_memory_chunks.extend(doc.get("chunks", []))

    documents = []

    if in_memory_chunks:
        # Score chunks by term frequency / keyword overlap
        query_words = [w.strip("?,.!-()\"'") for w in question.lower().split() if len(w) > 2]
        if not query_words:
            query_words = question.lower().split()
        scored_chunks = []
        for chunk in in_memory_chunks:
            content = chunk.get("page_content", "")
            content_lower = content.lower()
            score = sum(content_lower.count(word) for word in query_words)
            if score > 0:
                scored_chunks.append((score, chunk))
        
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        documents = [item[1] for item in scored_chunks[:4]]
        logs.append(f"Retrieved {len(documents)} chunks from in-memory PDFs using term frequency relevance.")
    elif mongodb_uri and mongodb_uri != "your_mongodb_atlas_uri_here":
        from pymongo import MongoClient
        from langchain_mongodb import MongoDBAtlasVectorSearch
        
        client = MongoClient(mongodb_uri)
        collection = client[db_name][collection_name]
        
        if use_ollama:
            from langchain_ollama import OllamaEmbeddings
            embeddings = OllamaEmbeddings(
                model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            )
        else:
            from langchain_openai import OpenAIEmbeddings
            embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))
            
        vector_search = MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=embeddings,
            index_name="default"
        )
        
        # Perform similarity search
        results = vector_search.similarity_search(question, k=4)
        documents = [{"page_content": r.page_content, "metadata": r.metadata} for r in results]
        logs.append(f"Retrieved {len(documents)} chunks from MongoDB Atlas vector store.")
    else:
        # Fallback to mock documents if no PDFs are uploaded and no MongoDB
        documents = [
            {"page_content": "The company's PTO policy guarantees 20 days of paid time off.", "metadata": {"source": "policy.pdf", "page": 1}},
            {"page_content": "Employees must submit expense reports within 30 days.", "metadata": {"source": "policy.pdf", "page": 5}}
        ]
        logs.append(f"No documents uploaded and MongoDB not configured. Retrieved {len(documents)} mocked chunks.")
        
    return {"documents": documents, "question": question, "logs": logs}

def grade_documents(state: GraphState):
    """
    Determines whether the retrieved documents are relevant to the question
    using a local Cross-Encoder.
    """
    print("---CHECK RELEVANCE---")
    question = state["question"]
    documents = state["documents"]
    logs = state.get("logs", [])
    
    filtered_docs = []
    web_search = False
    
    if grader_model:
        for d in documents:
            # Score the pair (Query, Document Content)
            score = grader_model.predict([question, d["page_content"]])
            # Thresholding for relevance (can be tuned)
            if score > 0.5:
                filtered_docs.append(d)
    else:
        # Fallback if model not loaded
        filtered_docs = documents

    if not filtered_docs:
        logs.append("Grading complete. All documents irrelevant. Marking for web search fallback.")
        web_search = True
    else:
        logs.append(f"Grading complete. Found {len(filtered_docs)} relevant chunks.")

    return {"documents": filtered_docs, "question": question, "web_search_required": web_search, "logs": logs}

def generate(state: GraphState):
    """
    Generate answer using RAG with strict citations.
    """
    print("---GENERATE---")
    question = state["question"]
    documents = state["documents"]
    logs = state.get("logs", [])
    
    # Format docs for prompt
    docs_text = "\n\n".join([f"Content: {d['page_content']}\nSource: {d['metadata']['source']} (Page {d['metadata'].get('page', 'Unknown')})" for d in documents])
    
    prompt = PromptTemplate(
        template="""You are an assistant for question-answering tasks. 
        Use the following pieces of retrieved context to answer the question. 
        If you don't know the answer, just say that you don't know. 
        You MUST provide strict citations for every claim you make in the format [Source: filename, Page X].
        
        Question: {question} 
        
        Context: {context} 
        
        Answer:""",
        input_variables=["question", "context"],
    )
    
    try:
        rag_chain = prompt | llm | StrOutputParser()
        generation = rag_chain.invoke({"context": docs_text, "question": question})
        logs.append("Generated final answer using primary LLM with strict citations.")
    except Exception as e:
        logs.append(f"Primary LLM unavailable ({e}). Using local fallback generation.")
        if documents:
            answers = []
            for d in documents:
                src = d['metadata'].get('source', 'Unknown')
                pg = d['metadata'].get('page', 'N/A')
                content = d['page_content']
                answers.append(f"{content} [Source: {src}, Page {pg}]")
            generation = "Based on the retrieved context: " + " ".join(answers)
        else:
            generation = "I could not find any relevant information in the documents to answer your question."
            
    return {"documents": documents, "question": question, "generation": generation, "logs": logs}

def rewrite(state: GraphState):
    """
    Rewrite the question to produce a better query for web search.
    """
    print("---REWRITE QUESTION---")
    question = state["question"]
    logs = state.get("logs", [])
    
    msg = [
        ("system", "You are a query rewriter. Your task is to optimize the query for a web search engine to find the missing information."),
        ("human", f"Original query: {question}\n\nRewritten query:"),
    ]
    
    try:
        response = llm.invoke(msg)
        rewritten_question = response.content
        logs.append(f"Rewrote query to: '{rewritten_question}' for web fallback.")
    except Exception as e:
        logs.append(f"Primary LLM unavailable for rewrite ({e}). Using original query.")
        rewritten_question = question
    
    return {"question": rewritten_question, "logs": logs}

def web_search(state: GraphState):
    """
    Live web search fallback using DuckDuckGo.
    """
    print("---WEB SEARCH---")
    question = state["question"]
    logs = state.get("logs", [])
    
    try:
        search = DuckDuckGoSearchRun()
        search_result = search.invoke(question)
        web_results = [{"page_content": search_result, "metadata": {"source": "DuckDuckGo Web Search", "page": "N/A"}}]
        logs.append("Performed live web search via DuckDuckGo and appended results.")
    except Exception as e:
        web_results = [{"page_content": "Error performing web search.", "metadata": {"source": "System Error", "page": "N/A"}}]
        logs.append(f"Web search failed: {e}")
        
    documents = state["documents"]
    documents.extend(web_results)
    
    return {"documents": documents, "question": question, "logs": logs}

def decide_to_generate(state: GraphState):
    """
    Determines whether to generate an answer or fall back to web search.
    """
    print("---DECIDE TO GENERATE---")
    web_search_required = state["web_search_required"]
    
    if web_search_required:
        return "rewrite"
    else:
        return "generate"

# Build the Graph
workflow = StateGraph(GraphState)

# Add nodes
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("generate", generate)
workflow.add_node("rewrite", rewrite)
workflow.add_node("web_search", web_search)

# Build edges
workflow.set_entry_point("retrieve")
workflow.add_edge("retrieve", "grade_documents")
workflow.add_conditional_edges(
    "grade_documents",
    decide_to_generate,
    {
        "rewrite": "rewrite",
        "generate": "generate",
    }
)
workflow.add_edge("rewrite", "web_search")
workflow.add_edge("web_search", "generate")
workflow.add_edge("generate", END)

# Compile
crag_app = workflow.compile()
