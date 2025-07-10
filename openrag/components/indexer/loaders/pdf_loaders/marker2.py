import asyncio
import gc
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional, Union

import ray
import torch
from config import load_config
from langchain_core.documents.base import Document
from marker.converters.pdf import PdfConverter
from tqdm.asyncio import tqdm
from utils.logger import get_logger

from io import BytesIO
import base64


from ..base import BaseLoader

logger = get_logger()
config = load_config()

DATA_DIR = Path(config.paths.data_dir)


if torch.cuda.is_available():
    MARKER_NUM_GPUS = config.loader.get("marker_num_gpus", 0.01)
else:  # On CPU
    MARKER_NUM_GPUS = 0


@ray.remote(num_gpus=MARKER_NUM_GPUS)
class MarkerWorker2:
    def __init__(self):
        import os

        from config import load_config
        from utils.logger import get_logger

        self.logger = get_logger()
        self.config = load_config()
        self.page_sep = "[PAGE_SEP]"

        self._workers = self.config.loader.get("marker_max_processes")
        self.maxtasksperchild = self.config.loader.get("marker_max_tasks_per_child", 5)

        self.converter_config = {
            "output_format": "markdown",
            "paginate_output": True,
            "page_separator": self.page_sep,
            "pdftext_workers": 1,
            "disable_multiprocessing": True,
        }
        if "RAY_ADDRESS" not in os.environ:
            os.environ["RAY_ADDRESS"] = "auto"
        self.pool = None
        self.init_resources()

    def init_resources(self):
        from marker.models import create_model_dict

        self.model_dict = create_model_dict()
        for v in self.model_dict.values():
            if hasattr(v.model, "share_memory"):
                v.model.share_memory()

        self.setup_mp()

    def setup_mp(self):
        import torch.multiprocessing as mp

        if self.pool:
            self.logger.warning("Resetting multiprocessing pool")
            self.pool.close()
            self.pool.join()
            self.pool.terminate()
            self.pool = None
        try:
            if mp.get_start_method(allow_none=True) != "spawn":
                mp.set_start_method("spawn", force=True)
        except RuntimeError:
            self.logger.warning(
                "Process start method already set, using existing method"
            )

        self.logger.info(f"Initializing MarkerWorker with {self._workers} workers")
        ctx = mp.get_context("spawn")
        self.pool = ctx.Pool(
            processes=self._workers,
            initializer=self._worker_init,
            initargs=(self.model_dict,),
            maxtasksperchild=self.maxtasksperchild,
        )

        self.logger.info("MarkerWorker initialized with multiprocessing pool")

    @staticmethod
    def _worker_init(model_dict):
        global worker_model_dict
        worker_model_dict = model_dict
        logger.debug("Worker initialized with model dictionary")

    @staticmethod
    def _process_pdf(file_path, config):
        global worker_model_dict

        try:
            logger.debug("Processing PDF", path=file_path)
            converter = PdfConverter(
                artifact_dict=worker_model_dict,
                config=config,
            )
            render = converter(file_path)
            return render
        except Exception:
            logger.exception("Error processing PDF", path=file_path)
            raise
        finally:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()

    async def process_pdf(self, file_path: str):
        config = self.converter_config.copy()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: self.pool.apply(self._process_pdf, (file_path, config))
        )
        return result.markdown, result.images

    def get_current_pool_size(self):
        return len([p for p in self.pool._pool if p.is_alive()])


@ray.remote
class MarkerPool2:
    def __init__(self):
        from config import load_config
        from utils.logger import get_logger

        self.logger = get_logger()
        self.config = load_config()
        self.min_processes = self.config.loader.get("marker_min_processes")
        self.max_processes = self.config.loader.get("marker_max_processes")
        self.pool_size = config.loader.get("marker_pool_size")
        self.actors = [MarkerWorker2.remote() for _ in range(self.pool_size)]
        self._queue: asyncio.Queue[ray.actor.ActorHandle] = asyncio.Queue()

        for _ in range(self.pool_size):
            for actor in self.actors:
                self._queue.put_nowait(actor)

        self.logger.info(
            f"Marker pool: {self.pool_size} actors × {self.max_processes} slots = "
            f"{self.pool_size * self.max_processes} PDF concurrency"
        )

    async def ensure_worker_pool_healthy(self, worker):
        current_alive = await worker.get_current_pool_size.remote()
        if current_alive < self.min_processes:
            self.logger.warning(
                f"Only {current_alive}/{self.min_processes} worker processes alive. Reinitializing pool..."
            )
            await worker.setup_mp.remote()

    async def process_pdf(self, file_path: str):
        # Wait until any slot is free
        worker = await self._queue.get()
        if worker:
            self.logger.info("MarkerWorker allocated")
            # Ensure the worker pool is healthy
            await self.ensure_worker_pool_healthy(worker)
        try:
            markdown, images = await worker.process_pdf.remote(file_path)
            return markdown, images
        except Exception as e:
            self.logger.exception(
                "Error processing PDF with MarkerWorker", error=str(e)
            )
            raise
        finally:
            await self._queue.put(worker)
            self.logger.debug("MarkerWorker returned to pool")


class MarkerLoader2(BaseLoader):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.page_sep = "[PAGE_SEP]"
        self.worker = ray.get_actor("MarkerPool2", namespace="openrag")

    async def aload_document(
        self,
        file_path: Union[str, Path],
        metadata: Optional[Dict] = None,
        save_markdown: bool = False,
    ) -> Document:
        if metadata is None:
            metadata = {}

        file_path_str = str(file_path)
        start = time.time()

        try:
            markdown, images = await self.worker.process_pdf.remote(file_path_str)
            if not markdown:
                raise RuntimeError(f"Conversion failed for {file_path_str}")

            imgref2path = {}
            # get filename without extension
            filename = Path(file_path_str).stem
            for key, pil_img in images.items():
                os.makedirs(f"{DATA_DIR}/{filename}", exist_ok=True)
                path = f"{DATA_DIR}/{filename}/{key}.png"
                pil_img.save(path, format="PNG")
                imgref2path[key] = path

            markdown = markdown.split(self.page_sep, 1)[1]
            markdown = re.sub(
                r"\{(\d+)\}" + re.escape(self.page_sep), r"[PAGE_\1]", markdown
            )
            markdown = markdown.replace("<br>", " <br> ").strip()

            doc = Document(
                page_content=markdown,
                metadata={**metadata, "imgref2path": imgref2path},
            )

            if save_markdown:
                self.save_document(doc, file_path_str)

            duration = time.time() - start
            logger.info(f"Processed {file_path_str} in {duration:.2f}s")
            return doc

        except Exception:
            logger.exception("Error in aload_document", path=file_path_str)
            raise
