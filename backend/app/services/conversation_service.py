from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_groq import ChatGroq
from ..config import settings

_store: dict[str, InMemoryChatMessageHistory] = {}

SYSTEM_PROMPT = (
    "You are a document analysis assistant. Answer questions based ONLY on the provided document context. "
    "If the answer is not in the context, say 'I cannot find this information in the document.'"
)


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in _store:
        _store[session_id] = InMemoryChatMessageHistory()
    return _store[session_id]


class ConversationService:
    def __init__(self):
        api_key = settings.GROQ_API_KEY
        self.llm = ChatGroq(
            api_key=api_key,
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=2048,
        ) if api_key and api_key != "gsk_your_groq_api_key" else None
        self._chain = None
        self._chain_with_history = None
        self._setup_chain()

    def _setup_chain(self):
        if not self.llm:
            self._chain = None
            self._chain_with_history = None
            return

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="history"),
            ("human", "Document Context:\n{context}\n\nQuestion: {question}"),
        ])

        self._chain = prompt | self.llm

        self._chain_with_history = RunnableWithMessageHistory(
            self._chain,
            get_session_history,
            input_messages_key="question",
            history_messages_key="history",
        )

    def chat(self, question: str, context: str, session_id: str = None) -> str:
        if not self._chain_with_history:
            return "Groq API is not configured."

        config = {"configurable": {"session_id": session_id or "default"}} if session_id else \
                 {"configurable": {"session_id": "default"}}

        response = self._chain_with_history.invoke(
            {"context": context, "question": question, "history": []},
            config=config,
        )
        return response.content

    def get_history(self, session_id: str = None) -> list[dict]:
        sid = session_id or "default"
        history = _store.get(sid)
        if not history:
            return []
        msgs = history.messages
        result = []
        for m in msgs:
            if isinstance(m, HumanMessage):
                result.append({"role": "user", "content": m.content})
            elif isinstance(m, AIMessage):
                result.append({"role": "assistant", "content": m.content})
        return result


conversation_service = ConversationService()
