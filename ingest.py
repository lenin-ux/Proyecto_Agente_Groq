"""
Lee todos los documentos de la carpeta knowledge_base/,
los divide en fragmentos ("chunks") y construye un índice vectorial
FAISS que se guarda en disco (carpeta vectorstore/).
"""

import os
import glob

import pandas as pd
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

CARPETA_DOCS = "knowledge_base"
CARPETA_INDICE = "vectorstore"
MODELO_EMBEDDINGS = "sentence-transformers/all-MiniLM-L6-v2"  # gratuito, local, ligero


def cargar_pdfs(carpeta: str) -> list[Document]:
    """Carga todos los PDF con PyPDFLoader (basado en pypdf), un Document por página."""
    documentos = []
    for ruta in glob.glob(os.path.join(carpeta, "*.pdf")):
        loader = PyPDFLoader(ruta)
        paginas = loader.load()  # cada página ya viene como Document con metadata
        for pagina in paginas:
            pagina.metadata["fuente"] = os.path.basename(ruta)
        documentos.extend(paginas)
    return documentos


def cargar_excels(carpeta: str) -> list[Document]:
    """
    Convierte cada fila de cada hoja de los archivos Excel en un
    Document independiente, con el texto en formato "columna: valor".
    """
    documentos = []
    rutas = glob.glob(os.path.join(carpeta, "*.xlsx")) + glob.glob(os.path.join(carpeta, "*.xls"))

    for ruta in rutas:
        nombre_archivo = os.path.basename(ruta)
        hojas = pd.read_excel(ruta, sheet_name=None)

        for nombre_hoja, df in hojas.items():
            df = df.dropna(how="all")
            for _, fila in df.iterrows():
                partes = [
                    f"{columna}: {valor}"
                    for columna, valor in fila.items()
                    if pd.notna(valor) and str(valor).strip() != ""
                ]
                if partes:
                    texto = ", ".join(partes)
                    documentos.append(
                        Document(
                            page_content=texto,
                            metadata={"fuente": nombre_archivo, "hoja": nombre_hoja},
                        )
                    )
    return documentos


def main():
    print("Cargando documentos desde:", CARPETA_DOCS)
    documentos = cargar_pdfs(CARPETA_DOCS) + cargar_excels(CARPETA_DOCS)

    if not documentos:
        print(
            f"No se encontró ningún .pdf ni .xlsx/.xls en '{CARPETA_DOCS}/'. "
            "Agrega tus archivos y vuelve a ejecutar este script."
        )
        return

    print(f"Documentos cargados: {len(documentos)}")

    # Dividimos los documentos (especialmente los PDF, que pueden tener
    # páginas largas) en fragmentos más pequeños para mejorar la búsqueda.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=100,
    )
    fragmentos = splitter.split_documents(documentos)
    print(f"Fragmentos generados: {len(fragmentos)}")

    print("Generando embeddings (puede tardar un poco la primera vez, "
          "porque descarga el modelo)...")
    embeddings = HuggingFaceEmbeddings(model_name=MODELO_EMBEDDINGS)

    print("Construyendo índice FAISS...")
    vectorstore = FAISS.from_documents(fragmentos, embeddings)
    vectorstore.save_local(CARPETA_INDICE)

    print(f"Listo. Índice guardado en '{CARPETA_INDICE}/'. "
          "Ahora puedes ejecutar: python chatbot.py")


if __name__ == "__main__":
    main()