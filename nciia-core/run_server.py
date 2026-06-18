import uvicorn
import os
import sys

# Add src to path
sys.path.insert(0, "src")

if __name__ == "__main__":
    # Load env vars from .env if python-dotenv is present, otherwise they are loaded by pydantic-settings
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    print("🚀 Starting N-CIIA Server...")
    print(f"🔑 Groq API Key present: {'NCIIA_LLM_API_KEY' in os.environ or os.path.exists('.env')}")
    
    uvicorn.run(
        "nciia.api.server:create_app",
        host="0.0.0.0",
        port=8000,
        factory=True,
        reload=True
    )
