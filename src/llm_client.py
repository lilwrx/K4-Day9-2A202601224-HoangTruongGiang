import os
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
MODEL_NAME = os.environ.get("MODEL_NAME", "llama-3.1-8b-instant")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

def generate_agent_reasoning(agent_name: str, task_description: str, data_summary: str, conclusion: str) -> str:
    if not client:
        return f"[{agent_name} Trace]: Executed {task_description}. Data: {data_summary}. Conclusion: {conclusion}"
        
    prompt = f"""You are a summarizing assistant for a dispute resolution system. 
Please summarize what the agent '{agent_name}' did.
Task: {task_description}
Data Summary: {data_summary}
Conclusion: {conclusion}
Summary:"""
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error generating reasoning: {e}")
        return f"[{agent_name} Trace]: Executed {task_description}. Data: {data_summary}. Conclusion: {conclusion}"

def get_model_name() -> str:
    return MODEL_NAME

def get_model_params() -> str:
    return "8B"
