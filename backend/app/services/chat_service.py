from .conversation_service import conversation_service
from .rag_service import rag_service


class ChatService:
    def chat_with_document(self, question: str, document_id: str, organization_id: str,
                           chat_history: list[dict] = None, session_id: str = None) -> dict:
        sid = session_id or f"doc_{document_id}"
        context = rag_service.get_document_context(document_id, organization_id)

        if not context:
            answer = "I cannot find this information in the document. The document may not have been processed yet."
            conversation_service.chat(question, "", session_id=sid)
        else:
            answer = conversation_service.chat(question, context, session_id=sid)

        history = conversation_service.get_history(sid)
        sources = [{"document_id": document_id, "relevance": "direct"}]

        return {
            "answer": answer,
            "sources": sources,
            "document_id": document_id,
            "history": history,
        }

    def chat_all_documents(self, question: str, organization_id: str,
                           chat_history: list[dict] = None, session_id: str = None) -> dict:
        sid = session_id or "all_docs"
        search_results = rag_service.hybrid_search(question, organization_id, limit=5)

        if not search_results:
            answer = "I could not find any relevant information in your documents."
            conversation_service.chat(question, "", session_id=sid)
            return {
                "answer": answer,
                "sources": [],
                "document_id": "",
                "history": conversation_service.get_history(sid),
            }

        context_parts = []
        sources = []
        for r in search_results:
            context_parts.append(f"[Document: {r['document_title']}]: {r['chunk_text']}")
            sources.append({
                "document_id": r["document_id"],
                "document_title": r["document_title"],
                "page_number": r["page_number"],
                "score": r["score"],
            })

        context = "\n\n".join(context_parts)

        answer = conversation_service.chat(question, context, session_id=sid)
        history = conversation_service.get_history(sid)

        return {
            "answer": answer,
            "sources": sources[:5],
            "document_id": sources[0]["document_id"] if sources else "",
            "history": history,
        }


chat_service = ChatService()
