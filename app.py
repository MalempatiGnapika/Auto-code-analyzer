from langchain_chroma import Chroma
from langchain.prompts import PromptTemplate
from src.helper import load_embedding, repo_ingestion
from dotenv import load_dotenv
import os
import shutil
import stat
import subprocess
import sys
import time
from flask import Flask, render_template, jsonify, request
from langchain_cohere import ChatCohere
from langchain.memory import ConversationSummaryMemory
from langchain.chains import ConversationalRetrievalChain

app = Flask(__name__)
load_dotenv()

COHERE_API_KEY = os.environ.get('COHERE_API_KEY')
os.environ["COHERE_API_KEY"] = COHERE_API_KEY

embeddings = load_embedding()
llm = ChatCohere(model="command-a-03-2025", temperature=0.4)

qa_prompt = PromptTemplate(
    template=(
        "You are Code Guardian AI, an assistant that answers questions about a codebase. "
        "Always answer in English, clearly and concisely, using only the context below. "
        "Each piece of context is labeled with the file it came from — always cite the "
        "exact file name for every fact you state. If something is not present in the "
        "context, say so rather than guessing.\n\n"
        "Context:\n{context}\n\n"
        "Chat History:\n{chat_history}\n\n"
        "Question: {question}\n"
        "Answer in English, citing file names:"
    ),
    input_variables=["context", "chat_history", "question"],
)

document_prompt = PromptTemplate(
    input_variables=["page_content", "source"],
    template="File: {source}\n---\n{page_content}"
)

state = {"vectordb": None, "qa": None, "persist_directory": None}


def _remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def load_qa_chain(persist_directory):
    memory = ConversationSummaryMemory(llm=llm, memory_key="chat_history", return_messages=True)
    vectordb = Chroma(persist_directory=persist_directory, embedding_function=embeddings)
    qa = ConversationalRetrievalChain.from_llm(
        llm,
        retriever=vectordb.as_retriever(search_type="mmr", search_kwargs={"k": 8, "fetch_k": 20}),
        memory=memory,
        combine_docs_chain_kwargs={
            "prompt": qa_prompt,
            "document_prompt": document_prompt,
        },
    )
    state["vectordb"] = vectordb
    state["qa"] = qa
    state["persist_directory"] = persist_directory


def cleanup_old_indexes(keep_directory, base="db_store"):
    if not os.path.exists(base):
        return
    for name in os.listdir(base):
        full_path = os.path.join(base, name)
        if full_path == keep_directory:
            continue
        try:
            shutil.rmtree(full_path, onerror=_remove_readonly)
        except Exception as e:
            print(f"Skipped cleanup of {full_path}: {e}")


def get_known_sources():
    if state["vectordb"] is None:
        return []
    data = state["vectordb"].get()
    return sorted(set(m["source"] for m in data["metadatas"]))


def find_matching_source(question, known_sources):
    q_lower = question.lower()
    for src in known_sources:
        basename = os.path.basename(src).lower()
        if basename and basename in q_lower:
            return src
    return None


def answer_whole_file(question, source):
    data = state["vectordb"].get(where={"source": source})
    chunks = data["documents"]
    full_context = f"File: {source}\n---\n" + "\n\n".join(chunks)

    prompt = (
        "You are Code Guardian AI. Using ONLY the following complete file content, "
        "answer the question thoroughly and in English, covering every relevant part "
        "of the file, not just one section.\n\n"
        f"{full_context}\n\n"
        f"Question: {question}\n"
        "Answer in English:"
    )
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


@app.route('/', methods=["GET", "POST"])
def index():
    return render_template('index.html')


@app.route('/chatbot', methods=["GET", "POST"])
def gitRepo():
    if request.method == 'POST':
        user_input = request.form['question']

        repo_ingestion(user_input)

        new_persist_directory = os.path.join("db_store", f"index_{int(time.time())}")
        subprocess.run(
            [sys.executable, "store_index.py", new_persist_directory],
            check=True,
        )

        load_qa_chain(new_persist_directory)
        cleanup_old_indexes(new_persist_directory)

    return jsonify({"response": str(user_input)})


@app.route("/get", methods=["GET", "POST"])
def chat():
    msg = request.form["msg"]
    input_text = msg
    print(input_text)

    if input_text == "clear":
        if os.path.exists("repo"):
            shutil.rmtree("repo", onerror=_remove_readonly)
        return "Repository cleared."

    if state["qa"] is None:
        return "Please index a repository first."

    known_sources = get_known_sources()
    matched_source = find_matching_source(input_text, known_sources)

    if matched_source:
        answer = answer_whole_file(input_text, matched_source)
        print(answer)
        return str(answer)

    result = state["qa"](input_text)
    print(result['answer'])
    return str(result["answer"])


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True, use_reloader=False)