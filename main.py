from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
from pydantic import BaseModel
from dotenv import load_dotenv
import os

# Load environment variables from the parent directory's .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

app = FastAPI(title="Streaming Avatar FastAPI Backend")

# CORS middleware to allow requests from Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEYGEN_API_KEY = os.getenv("HEYGEN_API_KEY")
HEYGEN_BASE_URL = os.getenv("HEYGEN_BASE_URL", "https://api.heygen.com")

# Global variable to store default KB ID
default_kb_id = None

@app.on_event("startup")
async def startup_event():
    """Create default knowledge base on server startup"""
    global default_kb_id
    if not HEYGEN_API_KEY:
        print("WARNING: Cannot create default KB - API key missing")
        return

    async with httpx.AsyncClient() as client:
        try:
            print("Creating default knowledge base...")
            response = await client.post(
                f"{HEYGEN_BASE_URL}/v1/streaming/knowledge_base/create",
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                    "x-api-key": HEYGEN_API_KEY
                },
                json={
                    "name": "Office Query Solver",
                    "opening": "starts with a greeting",
                    "prompt": "You are an IT industry office query solver. Help users with workplace-related queries in the IT industry, such as software development, project management, team collaboration, and technical challenges."
                }
            )
            response.raise_for_status()
            data = response.json()
            default_kb_id = data.get("data", {}).get("knowledge_base_id") or data.get("data", {}).get("id")

            if not default_kb_id:
                # Try to find existing one
                list_response = await client.get(
                    f"{HEYGEN_BASE_URL}/v1/streaming/knowledge_base/list",
                    headers={
                        "accept": "application/json",
                        "x-api-key": HEYGEN_API_KEY
                    }
                )
                list_response.raise_for_status()
                list_data = list_response.json()
                kb_list = list_data.get("data", {}).get("list", [])

                for kb in kb_list:
                    if (kb.get("name") == "Office Query Solver" and
                        kb.get("opening") == "starts with a greeting" and
                        kb.get("prompt") == "You are an IT industry office query solver. Help users with workplace-related queries in the IT industry, such as software development, project management, team collaboration, and technical challenges."):
                        default_kb_id = kb.get("id")
                        break

            if default_kb_id:
                print(f"Default KB created/found with ID: {default_kb_id}")
            else:
                print("WARNING: Failed to create or find default KB")

        except Exception as e:
            print(f"Error creating default KB on startup: {e}")
            default_kb_id = None

class KnowledgeBaseRequest(BaseModel):
    name: str
    opening: str
    prompt: str



@app.post("/get-access-token")
async def get_access_token():
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="API key is missing from environment")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{HEYGEN_BASE_URL}/v1/streaming.create_token",
                headers={"x-api-key": HEYGEN_API_KEY}
            )
            response.raise_for_status()
            data = response.json()
            token = data["data"]["token"]
            print(f"Generated token: {token[:50]}...")  # Log partial token for debugging
            return {"token": token}
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code}, {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail="Failed to retrieve access token")
        except Exception as e:
            print(f"Exception: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/create-knowledge-base")
async def create_knowledge_base(request: KnowledgeBaseRequest):
    if not HEYGEN_API_KEY:
        raise HTTPException(status_code=500, detail="API key is missing from environment")

    async with httpx.AsyncClient() as client:
        try:
            # Create the knowledge base
            response = await client.post(
                f"{HEYGEN_BASE_URL}/v1/streaming/knowledge_base/create",
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                    "x-api-key": HEYGEN_API_KEY
                },
                json={
                    "name": request.name,
                    "opening": request.opening,
                    "prompt": request.prompt
                }
            )
            response.raise_for_status()
            data = response.json()
            kb_id = data.get("data", {}).get("knowledge_base_id") or data.get("data", {}).get("id")

            # If ID is not in response, fetch the list and match
            if not kb_id:
                list_response = await client.get(
                    f"{HEYGEN_BASE_URL}/v1/streaming/knowledge_base/list",
                    headers={
                        "accept": "application/json",
                        "x-api-key": HEYGEN_API_KEY
                    }
                )
                list_response.raise_for_status()
                list_data = list_response.json()
                kb_list = list_data.get("data", {}).get("list", [])

                # Match by name, opening, and prompt
                for kb in kb_list:
                    if (kb.get("name") == request.name and
                        kb.get("opening") == request.opening and
                        kb.get("prompt") == request.prompt):
                        kb_id = kb.get("id")
                        break

            if not kb_id:
                raise HTTPException(status_code=500, detail="Failed to retrieve knowledge base ID")

            return {"knowledge_base_id": kb_id}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="Failed to create or retrieve knowledge base")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))



@app.get("/get-default-config")
async def get_default_config():
    """Get default avatar configuration with default KB ID"""
    global default_kb_id

    config = {
        "quality": "Low",
        "avatar_name": "Elenora_IT_Sitting_public",
        "voice": {
            "rate": 1.5,
            "emotion": "EXCITED",
            "model": "eleven_flash_v2_5"
        },
        "language": "en",
        "voice_chat_transport": "WEBSOCKET",
        "stt_settings": {
            "provider": "DEEPGRAM"
        },
        "opening_message": "Hello! I am ready to chat."
    }

    if default_kb_id:
        config["knowledge_id"] = default_kb_id
    else:
        config["knowledge_id"] = None

    return config



@app.get("/")
async def root():
    return {"message": "Streaming Avatar FastAPI Backend"}
