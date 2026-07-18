"""
Chatbot que responde solo con base en los documentos indexados por
ingest.py. Usa:

- FAISS + HuggingFaceEmbeddings para recuperar los fragmentos más
  relevantes de la documentación (RAG).
- Groq (a través de langchain-groq) como modelo de lenguaje: es
  gratuito (con límites de uso razonables) y una de las APIs de
  inferencia más rápidas que existen.
"""

import os
import sys

from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains.retrieval import create_retrieval_chain

"""Cambiar esta linea una vez que el proyecto este subido en la nube de Oracle y la llave no se encuentre anonima"""
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp", ".env"))

CARPETA_INDICE = "vectorstore"
MODELO_EMBEDDINGS = "sentence-transformers/all-MiniLM-L6-v2"

MODELO_GROQ = "llama-3.3-70b-versatile"

NOMBRE_EMPRESA = "Casa de Empeño Monte de Confianza"

PROMPT_COMPORTAMIENTO = f"""Eres el asistente virtual oficial de {NOMBRE_EMPRESA}.

REGLAS DE COMPORTAMIENTO:
1. Responde SIEMPRE en español, con un tono profesional, claro y amable.
2. Responde ÚNICAMENTE con información contenida en el CONTEXTO que se
   te proporciona a continuación. No inventes datos, precios, políticas
   ni promesas que no estén en el contexto.
3. Si la pregunta no puede responderse con el contexto disponible,
   dilo explícitamente y sugiere que el usuario contacte a un asesor
   humano. No intentes adivinar.
4. No respondas preguntas que no tengan relación con {NOMBRE_EMPRESA}
   o sus productos/servicios. En esos casos, redirige amablemente la
   conversación hacia en qué puedes ayudar.
5. Sé conciso: responde en pocos párrafos, evita relleno innecesario.

CONTEXTO:
{{context}}
"""


def cargar_cadena_rag():
    if not os.getenv("GROQ_API_KEY"):
        sys.exit(
            "ERROR: No se encontró GROQ_API_KEY.\n"
        )

    if not os.path.isdir(CARPETA_INDICE):
        sys.exit(
            f"ERROR: No existe la carpeta '{CARPETA_INDICE}/'.\n"
        )

    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)
    vectorstore = FAISS.load_local(
        CARPETA_INDICE, embeddings, allow_dangerous_deserialization=True
    )
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    llm = ChatGroq(model=MODELO_GROQ, temperature=0.3)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PROMPT_COMPORTAMIENTO),
            ("human", "{input}"),
        ]
    )

    combinar_documentos_chain = create_stuff_documents_chain(llm, prompt)
    cadena_rag = create_retrieval_chain(retriever, combinar_documentos_chain)

    return cadena_rag


def main():
    """Modo terminal"""
    print(f"Cargando chatbot de {NOMBRE_EMPRESA}... (esto puede tardar unos segundos)")
    cadena_rag = cargar_cadena_rag()
    print("Listo. Escribe tu pregunta (o 'salir' para terminar).\n")

    while True:
        pregunta = input("Tú: ").strip()
        if pregunta.lower() in {"salir", "exit", "quit"}:
            print("¡Hasta luego!")
            break
        if not pregunta:
            continue

        resultado = cadena_rag.invoke({"input": pregunta})
        print(f"\nAsistente: {resultado['answer']}\n")


def iniciar_servidor_web():
    """
    Modo web: levanta un servidor Flask local que sirve chat.html y
    expone un endpoint /chat para que el navegador hable con la
    cadena de LangChain. No requiere ningún archivo adicional aparte
    de chat.html (Flask ya viene en requirements.txt).
    """
    from flask import Flask, request, jsonify, send_from_directory

    print(f"Cargando chatbot de {NOMBRE_EMPRESA}... (esto puede tardar unos segundos)")
    cadena_rag = cargar_cadena_rag()

    directorio_actual = os.path.dirname(os.path.abspath(__file__))
    app = Flask(__name__)

    @app.route("/")
    def index():
        return send_from_directory(directorio_actual, "chat.html")

    @app.route("/chat", methods=["POST"])
    def chat():
        datos = request.get_json(force=True) or {}
        pregunta = (datos.get("pregunta") or "").strip()

        if not pregunta:
            return jsonify({"error": "Falta el campo 'pregunta'."}), 400

        resultado = cadena_rag.invoke({"input": pregunta})
        return jsonify({"respuesta": resultado["answer"]})

    """Abrir http://localhost:5000 en el navegador"""

    app.run(host="0.0.0.0", port=5000, debug=False)


if __name__ == "__main__":
    if "--web" in sys.argv:
        iniciar_servidor_web()
    else:
        main()