from dotenv import load_dotenv
import os
from langchain_chroma import Chroma
from src.helper import load_embedding

load_dotenv()
os.environ["COHERE_API_KEY"] = os.environ.get("COHERE_API_KEY")

vectordb = Chroma(persist_directory="db", embedding_function=load_embedding())
data = vectordb.get()
sources = set(m["source"] for m in data["metadatas"])
print(sources)