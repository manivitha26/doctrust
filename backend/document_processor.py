import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

def process_pdf(file_path: str):
    """
    Loads a PDF and splits it into chunks.
    """
    loader = PyPDFLoader(file_path)
    docs = loader.load()

    # Advanced structural chunking (recursive character for now, can be expanded)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    
    splits = text_splitter.split_documents(docs)
    
    # Optional: Add structural metadata here (e.g. section headers)
    for split in splits:
        # Example of adding a source page to metadata
        split.metadata['source'] = os.path.basename(file_path)
        
    return splits

def store_in_mongodb_vector(splits, mongodb_uri: str, db_name: str, collection_name: str):
    """
    Stores document chunks into MongoDB Atlas Vector Search.
    """
    from langchain_mongodb import MongoDBAtlasVectorSearch
    from pymongo import MongoClient
    import os

    # Initialize MongoDB python client
    client = MongoClient(mongodb_uri)
    collection = client[db_name][collection_name]

    use_ollama = os.getenv("USE_OLLAMA", "false").lower() == "true"
    
    if use_ollama:
        from langchain_ollama import OllamaEmbeddings
        embeddings = OllamaEmbeddings(
            model=os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
    else:
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

    # Insert into Vector Store
    # Assuming the vector search index is already created in Atlas with name 'default'
    vector_search = MongoDBAtlasVectorSearch.from_documents(
        documents=splits,
        embedding=embeddings,
        collection=collection,
        index_name="default"
    )
    
    return vector_search
