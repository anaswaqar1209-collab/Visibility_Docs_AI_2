import time
import logging
from datetime import datetime
from ..database import SupabaseDB
from .ocr_service import ocr_service
from .agent_orchestrator import classification_agent, category_agents
from .classification_service import classification_service
from .rag_service import rag_service
from .preprocessing_service import preprocessing_service

logger = logging.getLogger("visibility-docs")

STAGE_ORDER = [
    "queued",
    "preprocessing",
    "ocr_processing",
    "ocr_done",
    "classifying",
    "classified",
    "extracting",
    "extracted",
    "embedding",
    "embedded",
    "completed",
]


class OrchestratorService:
    def get_or_create_job(self, document_id: str, organization_id: str) -> dict:
        existing = SupabaseDB.select("processing_jobs", filters={"document_id": document_id})
        data = getattr(existing, "data", existing if isinstance(existing, list) else [])
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], dict) else {}
        SupabaseDB.insert("processing_jobs", {
            "organization_id": organization_id,
            "document_id": document_id,
            "job_type": "full_pipeline",
            "stage": "queued",
            "status": "queued",
            "progress": 0,
        })
        return {"stage": "queued", "status": "queued"}

    def update_stage(self, document_id: str, organization_id: str, stage: str, progress: int = None, status: str = None, error: str = None):
        update = {"stage": stage}
        if progress is not None:
            update["progress"] = progress
        if status:
            update["status"] = status
        if error:
            update["error_message"] = error
        if status == "running":
            update["started_at"] = datetime.utcnow().isoformat()
        if status in ("completed", "failed"):
            update["completed_at"] = datetime.utcnow().isoformat()
        SupabaseDB.update("processing_jobs", update, "document_id", document_id)

    def log_agent_run(self, organization_id: str, document_id: str, agent_name: str,
                      input_summary: str, output_summary: str, confidence: float,
                      duration_ms: int, status: str = "completed", error: str = None):
        SupabaseDB.insert("agent_runs", {
            "organization_id": organization_id,
            "document_id": document_id,
            "agent_name": agent_name,
            "input_summary": input_summary[:500] if input_summary else "",
            "output_summary": output_summary[:500] if output_summary else "",
            "confidence": confidence,
            "duration_ms": duration_ms,
            "status": status,
            "error_message": error,
        })

    def _resolve_file(self, doc: dict) -> str:
        fp = doc.get("original_file_url", "")
        if not fp:
            raise FileNotFoundError("File path not found")
        import os
        if os.path.exists(fp):
            return fp
        if fp.startswith("http"):
            import tempfile, urllib.request
            resp = urllib.request.urlopen(fp, timeout=120)
            data = resp.read()
            ext = os.path.splitext(fp.split("?")[0].split("/")[-1])[1] or ".pdf"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            tmp.write(data)
            tmp.close()
            logger.info(f"Downloaded remote file to {tmp.name}")
            return tmp.name
        raise FileNotFoundError(f"File not found: {fp}")

    def classify_only(self, document_id: str, organization_id: str) -> dict:
        print(f"\n{'#'*70}")
        print(f"# [CLASSIFY-ONLY] Starting for document: {document_id}")
        print(f"{'#'*70}")
        try:
            doc_result = SupabaseDB.select("documents", filters={"id": document_id, "organization_id": organization_id})
            doc_data = getattr(doc_result, "data", [])
            if not doc_data or len(doc_data) == 0:
                raise ValueError("Document not found")
            doc = doc_data[0] if isinstance(doc_data, list) else doc_data
            file_path = self._resolve_file(doc)
            print(f"[CLASSIFY-ONLY] File path: {file_path}")

            # Try direct text extraction first (fast path for PDFs)
            direct_text = self._extract_direct_text(file_path, max_pages=2)
            print(f"[CLASSIFY-ONLY] Direct text extracted: {len(direct_text)} chars")
            if direct_text.strip():
                self.update_stage(document_id, organization_id, "ocr_processing", 20, "running")
                # Still run OCR for full text, but classify immediately
                import threading
                ocr_result = {}
                ocr_exc = [None]
                def _do_ocr():
                    try:
                        ocr_result.update(ocr_service.process_document(file_path))
                    except Exception as e:
                        ocr_exc[0] = e
                ocr_thread = threading.Thread(target=_do_ocr)
                print(f"[CLASSIFY-ONLY] Starting background OCR while classifying...")
                ocr_thread.start()

                self.update_stage(document_id, organization_id, "classifying", 50, "running")
                t0 = time.time()
                classification = classification_agent.classify(direct_text, doc.get("title", ""))
                class_duration = int((time.time() - t0) * 1000)
                print(f"[CLASSIFY-ONLY] Classification result: type={classification['document_type']}, agent={classification.get('agent_type','')}, conf={classification['confidence']:.2f}, time={class_duration}ms")

                ocr_thread.join(timeout=300)
                raw_text = ocr_result.get("text", "") or direct_text
                page_count = ocr_result.get("page_count", 0)
                print(f"[CLASSIFY-ONLY] OCR completed: {len(raw_text)} chars, {page_count} pages")
            else:
                print(f"[CLASSIFY-ONLY] No direct text, running full OCR...")
                self.update_stage(document_id, organization_id, "ocr_processing", 20, "running")
                ocr_result = ocr_service.process_document(file_path)
                raw_text = ocr_result.get("text", "")
                page_count = ocr_result.get("page_count", 0)
                print(f"[CLASSIFY-ONLY] OCR completed: {len(raw_text)} chars, {page_count} pages")

                self.update_stage(document_id, organization_id, "classifying", 50, "running")
                t0 = time.time()
                classification = classification_agent.classify(raw_text, doc.get("title", ""))
                class_duration = int((time.time() - t0) * 1000)
                print(f"[CLASSIFY-ONLY] Classification result: type={classification['document_type']}, agent={classification.get('agent_type','')}, conf={classification['confidence']:.2f}, time={class_duration}ms")

            doc_type = classification["document_type"]
            if classification.get("confidence", 0) < 0.6:
                doc_type = "other"
                print(f"[CLASSIFY-ONLY] Low confidence ({classification['confidence']:.2f}), falling back to 'other'")

            SupabaseDB.update("documents", {"document_type": doc_type, "language": classification.get("language", "en"), "status": "classified"}, "id", document_id)
            self.update_stage(document_id, organization_id, "classified", 60, "completed")
            print(f"[CLASSIFY-ONLY] Done -> document_type={doc_type}, agent={classification.get('agent_type','')}")

            return {
                "document_id": document_id,
                "document_type": doc_type,
                "agent_type": classification.get("agent_type", ""),
                "confidence": classification.get("confidence", 0),
                "reasoning": classification.get("reasoning", ""),
                "language": classification.get("language", "en"),
                "page_count": page_count,
            }
        except Exception as e:
            print(f"[CLASSIFY-ONLY] FAILED: {e}")
            logger.error(f"Classify-only failed for {document_id}: {e}")
            SupabaseDB.update("documents", {"status": "failed", "error_message": str(e)}, "id", document_id)
            self.update_stage(document_id, organization_id, stage="ocr_processing", status="failed", error=str(e))
            return {"document_id": document_id, "error": str(e)}

    def _extract_direct_text(self, file_path: str, max_pages: int = None) -> str:
        try:
            import fitz
            doc = fitz.open(file_path)
            text = ""
            for i, page in enumerate(doc):
                if max_pages and i >= max_pages:
                    break
                text += page.get_text()
            doc.close()
            return text
        except Exception:
            return ""

    def run_pipeline(self, document_id: str, organization_id: str) -> dict:
        print(f"\n{'='*70}")
        print(f"[PIPELINE] Starting pipeline for document: {document_id} | org: {organization_id}")
        print(f"{'='*70}")
        status = "failed"
        classification = {"document_type": "other", "confidence": 0.0, "reasoning": ""}
        extraction = {"extracted_data": {}, "confidence": 0.0}
        page_count = 0

        try:
            job = self.get_or_create_job(document_id, organization_id)
            print(f"[PIPELINE] Stage: {job.get('stage', 'queued')} | Status: {job.get('status', 'queued')}")
            doc_result = SupabaseDB.select("documents", filters={"id": document_id, "organization_id": organization_id})
            doc_data = getattr(doc_result, "data", [])
            if not doc_data or len(doc_data) == 0:
                raise ValueError("Document not found")
            doc = doc_data[0] if isinstance(doc_data, list) else doc_data
            file_path = self._resolve_file(doc)
            print(f"[PIPELINE] File: {file_path}")

            # Stage 1 & 2: OCR + Classification in parallel
            print(f"[PIPELINE] Stage 1/2: OCR + Classification (parallel)")
            self.update_stage(document_id, organization_id, "ocr_processing", 20, "running")

            import threading
            ocr_result = {}
            ocr_exc = [None]

            def _do_ocr():
                try:
                    print(f"[PIPELINE] OCR thread started for: {file_path}")
                    ocr_result.update(ocr_service.process_document(file_path))
                    print(f"[PIPELINE] OCR thread completed")
                except Exception as e:
                    ocr_exc[0] = e
                    print(f"[PIPELINE] OCR thread FAILED: {e}")

            ocr_thread = threading.Thread(target=_do_ocr)
            ocr_thread.start()

            # Try direct text from first 2 pages for fast classification while OCR runs
            direct_text = self._extract_direct_text(file_path, max_pages=2)
            print(f"[PIPELINE] Direct text (first 2 pages): {len(direct_text)} chars")
            if direct_text.strip():
                self.update_stage(document_id, organization_id, "classifying", 50, "running")
                t0 = time.time()
                print(f"[PIPELINE] Classifying from direct text (while OCR runs in background)...")
                classification = classification_agent.classify(direct_text, doc.get("title", ""))
                class_duration = int((time.time() - t0) * 1000)
                print(f"[PIPELINE] Classification (from direct text): type={classification['document_type']}, agent={classification.get('agent_type','')}, conf={classification['confidence']:.2f}, time={class_duration}ms")
                self.log_agent_run(organization_id, document_id, "classification_agent",
                                   f"text_len={len(direct_text)}", f"type={classification['document_type']}, conf={classification['confidence']}",
                                   classification.get("confidence", 0), class_duration)

            # Wait for OCR to finish
            print(f"[PIPELINE] Waiting for OCR to complete...")
            ocr_thread.join(timeout=300)
            if ocr_exc[0]:
                raise ocr_exc[0]

            raw_text = ocr_result.get("text", "")
            page_count = ocr_result.get("page_count", 0)
            print(f"[PIPELINE] OCR complete: {len(raw_text)} chars, {page_count} pages, source: {ocr_result.get('source', 'ocr')}")

            SupabaseDB.update("documents", {"raw_text": raw_text, "page_count": page_count, "status": "ocr_done"}, "id", document_id)
            self.update_stage(document_id, organization_id, "ocr_done", 40)

            # If no direct text was available (scanned PDF / image), classify with OCR text now
            if not direct_text.strip():
                self.update_stage(document_id, organization_id, "classifying", 50, "running")
                t0 = time.time()
                print(f"[PIPELINE] No direct text - classifying from OCR text...")
                classification = classification_agent.classify(raw_text, doc.get("title", ""))
                class_duration = int((time.time() - t0) * 1000)
                print(f"[PIPELINE] Classification (from OCR text): type={classification['document_type']}, agent={classification.get('agent_type','')}, conf={classification['confidence']:.2f}, time={class_duration}ms")
                self.log_agent_run(organization_id, document_id, "classification_agent",
                                   f"text_len={len(raw_text)}", f"type={classification['document_type']}, conf={classification['confidence']}",
                                   classification.get("confidence", 0), class_duration)

            doc_type = classification["document_type"]
            if classification.get("confidence", 0) < 0.6:
                doc_type = "other"
                print(f"[PIPELINE] Low confidence ({classification['confidence']:.2f}), falling back to 'other'")

            SupabaseDB.update("documents", {"document_type": doc_type, "language": classification.get("language", "en"), "status": "classified"}, "id", document_id)
            self.update_stage(document_id, organization_id, "classified", 60)
            print(f"[PIPELINE] Stage 2 done: classified as '{doc_type}'")

            # Stage 3 & 4: Extraction + Embedding in parallel
            self.update_stage(document_id, organization_id, "extracting", 70, "running")
            print(f"[PIPELINE] Stage 3/4: Extraction + Embedding (parallel)")

            if doc_type == "other":
                # Skip Groq extraction for 'other' type — no structured fields expected
                extraction = {"extracted_data": {}, "confidence": 0.0}
                print(f"[PIPELINE] Skipping extraction for document type 'other'")
                self.update_stage(document_id, organization_id, "extracted", 80)
                print(f"[PIPELINE] Indexing document (embedding)...")
                try:
                    rag_service.index_document(document_id, organization_id, raw_text)
                    print(f"[PIPELINE] Embedding complete")
                except Exception as e:
                    logger.warning(f"Embedding skipped for {document_id}: {e}")
                    print(f"[PIPELINE] Embedding skipped: {e}")
            else:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                    print(f"[PIPELINE] Submitting extraction (agent: {classification.get('agent_type','')}) + embedding in parallel...")
                    ext_future = pool.submit(category_agents.extract, raw_text, doc_type, classification.get("agent_type", ""))
                    emb_future = pool.submit(rag_service.index_document, document_id, organization_id, raw_text)

                    t0 = time.time()
                    extraction = ext_future.result()
                    ext_duration = int((time.time() - t0) * 1000)
                    print(f"[PIPELINE] Extraction complete: fields={list(extraction.get('extracted_data', {}).keys())[:5]}, conf={extraction.get('confidence', 0):.2f}, time={ext_duration}ms")
                    self.log_agent_run(organization_id, document_id, f"{doc_type}_agent",
                                       f"type={doc_type}, text_len={len(raw_text)}",
                                       f"fields={list(extraction.get('extracted_data', {}).keys())[:10]}",
                                       extraction.get("confidence", 0), ext_duration)

                    try:
                        emb_future.result()
                        print(f"[PIPELINE] Embedding complete")
                    except Exception as e:
                        logger.warning(f"Embedding failed in parallel: {e}")
                        print(f"[PIPELINE] Embedding FAILED: {e}")

                SupabaseDB.insert("documents_metadata", {
                    "organization_id": organization_id,
                    "document_id": document_id,
                    "document_type": doc_type,
                    "extracted_data": extraction.get("extracted_data", {}),
                    "field_confidence": extraction.get("field_confidence", {}),
                    "overall_confidence": extraction.get("confidence", 0),
                    "agent_version": "1.0.0",
                })
                SupabaseDB.insert("document_extractions", {
                    "organization_id": organization_id,
                    "document_id": document_id,
                    "extraction_type": doc_type,
                    "extracted_data": extraction.get("extracted_data", {}),
                    "confidence": extraction.get("confidence", 0),
                })
                self.update_stage(document_id, organization_id, "extracted", 80)
                print(f"[PIPELINE] Extraction data saved to DB")

            self.update_stage(document_id, organization_id, "embedded", 95)

            # Mark complete
            SupabaseDB.update("documents", {"status": "processed"}, "id", document_id)
            self.update_stage(document_id, organization_id, "completed", 100, "completed")
            status = "processed"
            print(f"[PIPELINE] {'='*50}")
            print(f"[PIPELINE] COMPLETED: {document_id} -> {status}")
            print(f"[PIPELINE] {'='*50}")

        except Exception as e:
            print(f"[PIPELINE] FAILED: {e}")
            import traceback as tb
            tb.print_exc()
            logger.error(f"Pipeline failed for {document_id}: {e}")
            SupabaseDB.update("documents", {"status": "failed", "error_message": str(e)}, "id", document_id)
            self.update_stage(document_id, organization_id, stage=job.get("stage", "queued"), status="failed", error=str(e))
            status = "failed"

        return {
            "document_id": document_id,
            "status": status,
            "classification": classification,
            "extraction": extraction,
            "page_count": page_count,
        }


orchestrator = OrchestratorService()
