import os
from dotenv import load_dotenv

load_dotenv()

class BaseAgent:
    def __init__(self, name: str, model_name: str = "gemma-2-9b-it"):
        self.name = name
        self.model_name = model_name
        self.hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
        self.client = None

        if self.hf_token:
            try:
                from huggingface_hub import InferenceClient
                self.client = InferenceClient(model="google/gemma-2-9b-it", token=self.hf_token)
            except Exception as e:
                self.client = None

    def generate_llm_response(self, prompt: str, max_tokens: int = 512) -> str:
        if self.client:
            try:
                response = self.client.text_generation(
                    prompt,
                    max_new_tokens=max_tokens,
                    temperature=0.1
                )
                return response
            except Exception as e:
                print(f"[{self.name}] HF API Call ({e}). Utilizing agent engine.")
                return ""
        return ""

    def process(self, input_data: dict, logger=None) -> dict:
        raise NotImplementedError("Subclasses must implement process()")
