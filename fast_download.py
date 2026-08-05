import os
import sys

# Enable HF Transfer (Rust-based multi-threaded high-speed downloader)
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

from dotenv import load_dotenv
from huggingface_hub import snapshot_download, hf_hub_download

load_dotenv()

def fast_download():
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    
    print("==========================================")
    print("   HIGH-SPEED GEMMA-2-9B DOWNLOADER       ")
    print("==========================================")
    print("\nOptions:")
    print("1. GGUF 4-bit Quantized Model (~5.4 GB) - [FASTEST DOWNLOAD & RUNS GREAT ON CPU/GPU]")
    print("2. Full Safetensors Model (~18 GB)      - [REQUIRES HIGH BANDWIDTH & 20GB+ RAM/VRAM]")
    
    # Try GGUF 4-bit first for ultra-fast speed, or prompt user choice
    repo_gguf = "bartowski/gemma-2-9b-it-GGUF"
    target_dir = r"C:\Users\DELL\Documents\GitHub\K4-Day9-2A202601224-HoangTruongGiang\models\gemma-2-9b-it"
    os.makedirs(target_dir, exist_ok=True)

    print(f"\n[Speed Boost] Downloading GGUF Q4_K_M weights (5.4 GB) to {target_dir}...")
    
    try:
        file_path = hf_hub_download(
            repo_id=repo_gguf,
            filename="gemma-2-9b-it-Q4_K_M.gguf",
            local_dir=target_dir,
            token=token
        )
        print(f"\n[OK] Fast download complete! Model file saved at: {file_path}")
        return file_path
    except Exception as e:
        print(f"\n[Notice]: {e}")
        print("Fallback: Downloading unsloth/gemma-2-9b-it...")
        return snapshot_download(
            repo_id="unsloth/gemma-2-9b-it",
            local_dir=target_dir,
            token=token,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot", "*.onnx"]
        )

if __name__ == "__main__":
    fast_download()
