import os
from dotenv import load_dotenv
from langchain_chroma import Chroma

from src.helper import load_repo, text_splitter, load_embedding

load_dotenv()

COHERE_API_KEY = os.environ.get("COHERE_API_KEY")
os.environ["COHERE_API_KEY"] = COHERE_API_KEY

documents = load_repo("repo/")
text_chunks = text_splitter(documents)
embeddings = load_embedding()

vectordb = Chroma.from_documents(
    text_chunks,
    embedding=embeddings,
    persist_directory="./db",
)