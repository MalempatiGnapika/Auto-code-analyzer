import os
import sys
from dotenv import load_dotenv
from langchain_chroma import Chroma

from src.helper import load_repo, text_splitter, load_embedding

load_dotenv()

COHERE_API_KEY = os.environ.get("COHERE_API_KEY")
os.environ["COHERE_API_KEY"] = COHERE_API_KEY

# Accept the target persist directory as a command-line argument.
# Falls back to "db" if run manually with no argument.
persist_directory = sys.argv[1] if len(sys.argv) > 1 else "db"

documents = load_repo("repo/")
text_chunks = text_splitter(documents)
print("Documents:", len(documents))
print("Chunks:", len(text_chunks))

embeddings = load_embedding()

vectordb = Chroma.from_documents(
    text_chunks,
    embedding=embeddings,
    persist_directory=persist_directory,
)

print("Indexed into:", persist_directory)