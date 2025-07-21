from langchain_core.documents.base import Document
from openai import AsyncOpenAI
from tqdm.asyncio import tqdm
from utils.logger import get_logger

from .utils import llmSemaphore

logger = get_logger()

system_prompt_map = """
Vous êtes un modèle de langage spécialisé dans l’analyse et la synthèse d’informations. Ton rôle est d’examiner un texte fourni et d’en extraire les éléments nécessaires pour répondre à une question utilisateur.
Analyse le texte en profondeur.
Synthétise les informations essentielles qui peuvent aider à répondre à la requête.
Si le texte ne contient aucune donnée pertinente pour répondre à la question, réponds simplement : "Not pertinent" et n'ajoute pas de commentaires.
"""

class RAGMapReduce:
    def __init__(self, config):
        self.config = config
        self.client = AsyncOpenAI(
            base_url=self.config.llm["base_url"], api_key=self.config.llm["api_key"]
        )
        self.model = self.config.llm["model"]

    async def infer_llm_map_reduce(self, query, chunk: Document):
        async with llmSemaphore:
            user_prompt_map = (
                "Voici un texte :\n" + chunk.page_content + "\n"
                "À partir de ce document, identifie et résume de manière complète les informations utiles pour répondre à la question suivante :\n"
                + query
            )
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt_map},
                    {"role": "user", "content": user_prompt_map},
                ],
                stream=False,
                max_tokens=512,
                temperature=0.3,
            )
            resp = response.choices[0].message.content.strip()
            logger.info(f"response map: {resp}")
            relevancy = "Not pertinent" not in resp
            return relevancy, resp

    async def map_reduce(self, query: str, chunks: list[Document]):
        logger.debug("Running map reduce", chunk_count=len(chunks), query=query)
        tasks = [self.infer_llm_map_reduce(query, chunk) for chunk in chunks]
        output = await tqdm.gather(
            *tasks, desc="MAP-REDUCE Processing chunks", total=len(chunks)
        )
        relevant_chunks_syntheses = [
            (synthesis, chunk)
            for chunk, (relevancy, synthesis) in zip(chunks, output)
            if relevancy
        ]
        logger.debug(
            "Map reduce completed",
            relevant_chunk_count=len(relevant_chunks_syntheses),
            query=query,
        )
        # final_response = await infer_llm_reduce("\n".join(syntheses))
        return relevant_chunks_syntheses
