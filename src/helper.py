import os
import shutil
import stat
from git import Repo
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers import LanguageParser
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from langchain_cohere import CohereEmbeddings


def _remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def repo_ingestion(repo_url):
    repo_path = "repo/"
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path, onerror=_remove_readonly)
    os.makedirs(repo_path, exist_ok=True)
    Repo.clone_from(repo_url, to_path=repo_path)


def load_repo(repo_path):
    # Python files: parsed with language-aware splitting
    py_loader = GenericLoader.from_filesystem(
        repo_path,
        glob="**/*",
        suffixes=[".py"],
        parser=LanguageParser(language=Language.PYTHON, parser_threshold=500),
    )
    py_documents = py_loader.load()

    # Other common text-based project files: loaded as plain text
    other_documents = []
    other_extensions = [".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".js", ".html", ".css"]
    for ext in other_extensions:
        try:
            loader = DirectoryLoader(
                repo_path,
                glob=f"**/*{ext}",
                loader_cls=TextLoader,
                loader_kwargs={"autodetect_encoding": True},
                silent_errors=True,
            )
            other_documents.extend(loader.load())
        except Exception as e:
            print(f"Skipped loading {ext} files: {e}")

    documents = py_documents + other_documents
    return documents


def text_splitter(documents):
    documents_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
    )
    text_chunks = documents_splitter.split_documents(documents)
    return text_chunks


def load_embedding():
    embeddings = CohereEmbeddings(model="embed-english-v3.0")
    return embeddings