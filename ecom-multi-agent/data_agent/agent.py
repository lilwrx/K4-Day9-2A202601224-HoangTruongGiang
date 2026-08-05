"""
data_agent: understands the Olist data schema and fetches/joins records
from data/ for one order_id, so downstream agents (Customer, Order &
Product, Payment, Delivery, Policy, ...) work from verified data instead of
the customer's claim text.

Two ways to use it:

1. Deterministic, no LLM (what the rest of the pipeline should call):

    from data_agent.agent import DataAgent
    agent = DataAgent()
    bundle = agent.investigate(order_id)   # dict, see DataStore.fetch_order_bundle

2. Natural-language tool-calling agent (for ad-hoc questions / a
   Coordinator that hands off free-text asks instead of a structured call):

    answer = agent.chat("What products were in order <order_id> and were "
                         "any of them shipped by more than one seller?")

Model: OpenAI gpt-4o-mini via OPENAI_API_KEY in .env. Only used by chat();
investigate() never calls the LLM, so it can't hallucinate a row that isn't
in the CSVs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

if __package__ in (None, ""):
    # Allows `python agent.py` to work directly, not just `python -m data_agent.agent`.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from tools import ALL_TOOLS, get_data_store, get_schema_overview
else:
    from .tools import ALL_TOOLS, get_data_store, get_schema_overview

load_dotenv()

MODEL_NAME = "gpt-4o-mini"

SYSTEM_PROMPT = """You are data_agent, the data-access agent in an e-commerce \
dispute investigation pipeline for the Olist Brazilian e-commerce dataset.

Your only job is to answer questions about orders, customers, items, \
payments, reviews, products, and sellers by calling tools that read the \
CSVs in data/. You have no knowledge of this dataset beyond what the tools \
return.

Rules:
- Never invent an order_id, customer_id, product_id, seller_id, amount, or \
timestamp. If a tool returns null/None or an empty list, say so plainly \
instead of filling in a plausible-looking value.
- Call get_schema first if you are unsure which table or column holds a \
piece of information.
- Prefer fetch_order_bundle for "investigate this order" style questions \
instead of many single-table calls.
- Quote fields exactly as the tools return them (same timestamp format, \
same casing); do not reformat or convert timezones.

{schema_overview}
"""


class DataAgent:
    """Schema-aware, tool-calling wrapper around DataStore."""

    def __init__(self, model_name: str = MODEL_NAME, temperature: float = 0.0):
        self.store = get_data_store()
        self.model_name = model_name

        if not os.getenv("OPENAI_API_KEY"):
            self._executor = None
        else:
            llm = ChatOpenAI(model=model_name, temperature=temperature)
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", SYSTEM_PROMPT.format(schema_overview=get_schema_overview())),
                    ("human", "{input}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ]
            )
            agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
            self._executor = AgentExecutor(agent=agent, tools=ALL_TOOLS, verbose=False)

    # ---- deterministic path (no LLM) -------------------------------------

    def investigate(self, order_id: str) -> dict:
        """Fetch the full joined data bundle for one order_id. Deterministic:
        same input always returns the same output, no model call involved."""
        return self.store.fetch_order_bundle(order_id)

    # ---- natural-language path (LLM + tools) -----------------------------

    def chat(self, query: str) -> str:
        """Answer a free-text question by letting the LLM call data tools.
        Raises RuntimeError if OPENAI_API_KEY is not configured."""
        if self._executor is None:
            raise RuntimeError(
                "OPENAI_API_KEY is not set in .env — DataAgent.chat() needs it. "
                "Use DataAgent.investigate(order_id) for the deterministic, "
                "no-LLM data fetch instead."
            )
        result = self._executor.invoke({"input": query})
        return result["output"]


if __name__ == "__main__":
    import json
    import sys

    order_id = sys.argv[1] if len(sys.argv) > 1 else None
    agent = DataAgent()
    if order_id:
        print(json.dumps(agent.investigate(order_id), indent=2, ensure_ascii=False))
    else:
        print("Usage: python agent.py <order_id>")
