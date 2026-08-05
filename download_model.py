import os
import sys
from dotenv import load_dotenv
from huggingface_hub import snapshot_download

load_dotenv()

def download_gemma():
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    repo_id = "google/gemma-2-9b-it"
    target_dir = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\models\gemma-2-9b-it"
    
    print(f"=== Downloading model weights for {repo_id} ===")
    print(f"Destination folder: {target_dir}")
    if token:
        print("Using HF_TOKEN authentication token from environment/.env")
    else:
        print("Note: Downloading gated model google/gemma-2-9b-it requires HF_TOKEN. Add HF_TOKEN=hf_xxx to .env")
    
    os.makedirs(target_dir, exist_ok=True)
    
    try:
        path = snapshot_download(
            repo_id=repo_id,
            local_dir=target_dir,
            token=token,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot", "*.onnx"]
        )
        print(f"\n[OK] Model successfully downloaded to: {path}")
        return path
    except Exception as e:
        print(f"\n[Notice]: {e}")
        print("\nFallback: Downloading open weights model (unsloth/gemma-2-9b-it)...")
        fallback_repo = "unsloth/gemma-2-9b-it"
        path = snapshot_download(
            repo_id=fallback_repo,
            local_dir=target_dir,
            token=token,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot", "*.onnx"]
        )
        print(f"\n[OK] Model successfully downloaded to: {path}")
        return path

if __name__ == "__main__":
    download_gemma()
