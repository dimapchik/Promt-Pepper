import os
import sys
from typing import AsyncGenerator, Generator, Optional

import chromadb
import ollama
from dotenv import load_dotenv
from loguru import logger
from sentence_transformers import SentenceTransformer

from llm.conversation_state import Storage
from llm.utils import Singleton

logger.remove()
logger.add(sys.stdout, level="INFO")
load_dotenv()


class RAGService(metaclass=Singleton):
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    LLM_MODEL = os.getenv("LLM_MODEL", "gemma2")
    CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "recipes")
    TOP_K_RESULTS = int(os.getenv("TOP_K_RESULTS", "3"))

    def __init__(self):
        self.client = chromadb.PersistentClient(path=RAGService.CHROMA_PATH)

        try:
            self.collection = self.client.get_collection(RAGService.COLLECTION_NAME)
        except Exception as e:
            raise RuntimeError(
                f"Collection '{RAGService.COLLECTION_NAME}' not found. "
                f"Run 'python -m llm.setup_db' first to initialize the database."
            ) from e

        self.embedder = SentenceTransformer(RAGService.EMBEDDING_MODEL)
        self.model = RAGService.LLM_MODEL

    def get_context(self, query: str, top_k: int = None) -> str:
        if top_k is None:
            top_k = RAGService.TOP_K_RESULTS

        query_emb = self.embedder.encode([query])[0]

        results = self.collection.query(
            query_embeddings=[query_emb.tolist()],
            n_results=top_k
        )

        documents = results["documents"][0]
        context = "## " + "\n\n## ".join(documents)

        return context

    def query_stream(self, query: list[dict[str, str]]) -> Generator[str, None, None]:
        try:
            logger.info(f"System prompt sent to LLM: {query[0]['content']}")
            stream = ollama.chat(
                model=self.model,
                messages=query,
                stream=True
            )

            for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]

        except ollama.ResponseError as e:
            yield f"Error: LLM service unavailable - {e}"
        except Exception as e:
            yield f"Error: {e}"
