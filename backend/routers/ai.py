import os
import json
import anthropic
from openai import OpenAI
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
from models.schemas import AIGenerateRequest

router = APIRouter()

# ── Provider config ──────────────────────────────────────
# AI_PROVIDER: "anthropic" or "nvidia"
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic").lower()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

SYSTEM_PROMPT = """
You are an experienced QA Engineer.

I will provide a Swagger UI screenshot or API endpoint details.

Your task is to:

1. Identify all API endpoints from the input.
2. Generate comprehensive API test cases for each endpoint.

Test case requirements:

* Include Positive, Negative, and Edge cases.
* Generate at least 20–30 test cases (unless specified otherwise).
* Focus on real-world scenarios including:

  * Valid inputs
  * Invalid inputs
  * Missing parameters
  * Unauthorized access (401)
  * Forbidden access (403)
  * Duplicate requests
  * Expired or invalid data
  * Boundary conditions

STRICT FORMAT REQUIREMENT:

* Output must be in JSON format only.
* Each test case must follow this exact structure:

{
"title": "<Test Case Title>",
"preconditions": "Postman application is open",
"steps": [
{
"action": "Navigate to the Swagger page URL and ensure correct version is selected.",
"expected": "The Swagger page should load successfully."
},
{
"action": "Click Authorize and enter a valid Bearer token (or skip for unauthorized scenarios).",
"expected": "Authorization should be handled as per scenario."
},
{
"action": "Execute the API request with appropriate endpoint and data.",
"expected": "Validate response based on the scenario (200, 400, 401, 403, etc.)."
}
]
}

Important rules:

* Always use the actual Swagger URL from the input.
* Always follow the 3-step format (Navigate → Authorize → Execute).
* Do not add extra explanations outside JSON.
* Ensure consistency across all test cases.
* Make output directly usable for Azure DevOps or automation scripts.

If the user specifies:

* “only positive” → generate only positive test cases
* “only negative” → generate only negative test cases
* “reduce count” → limit number of test cases accordingly

Wait for the input screenshot or API details before generating output.

"""

def _build_user_message(req: AIGenerateRequest) -> list:
    content = []

    if req.image_base64:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": req.image_media_type or "image/png",
                "data": req.image_base64,
            },
        })

    prompt_parts = [f"Generate {req.count} test cases"]
    if req.description:
        prompt_parts.append(f"for the following feature/screen: {req.description}")
    if req.image_base64:
        prompt_parts.append("Use the screenshot above as the primary reference.")
    if req.context:
        prompt_parts.append(f"Additional context: {req.context}")

    prompt_parts.append(
        'Return ONLY a JSON array with this structure:\n'
        '[{"title":"...","preconditions":"...","steps":[{"action":"...","expected":"..."}]}]'
    )

    content.append({"type": "text", "text": " ".join(prompt_parts)})
    return content


@router.post("/generate")
async def generate_testcases(req: AIGenerateRequest):
    """
    Generate test cases using AI (Anthropic Claude or NVIDIA NIM).
    Set AI_PROVIDER env var to 'nvidia' and NVIDIA_API_KEY to use NVIDIA.
    """
    if not req.description and not req.image_base64:
        raise HTTPException(
            status_code=400,
            detail="Provide at least a description or an image."
        )

    if AI_PROVIDER == "nvidia":
        return await _generate_nvidia(req)
    else:
        return await _generate_anthropic(req)


async def _generate_anthropic(req: AIGenerateRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured on server. Set it in your .env file."
        )
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_message(req)}],
        )

        raw = message.content[0].text.strip()
        testcases = _parse_json_response(raw)

        return {
            "success": True,
            "count": len(testcases),
            "testcases": testcases,
            "model": "claude-sonnet-4-20250514",
            "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"AI returned invalid JSON: {e}")
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _generate_nvidia(req: AIGenerateRequest):
    if not NVIDIA_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="NVIDIA_API_KEY not configured on server. Set it in your .env file."
        )
    try:
        client = OpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)

        # Build message content for OpenAI-compatible API
        user_content = _build_nvidia_user_content(req)

        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.4,
        )

        raw = response.choices[0].message.content.strip()
        testcases = _parse_json_response(raw)

        tokens_used = 0
        if response.usage:
            tokens_used = (response.usage.prompt_tokens or 0) + (response.usage.completion_tokens or 0)

        return {
            "success": True,
            "count": len(testcases),
            "testcases": testcases,
            "model": NVIDIA_MODEL,
            "tokens_used": tokens_used,
        }

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"AI returned invalid JSON: {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"NVIDIA API error: {e}")


def _build_nvidia_user_content(req: AIGenerateRequest):
    """Build OpenAI-compatible message content for NVIDIA NIM."""
    parts = []

    if req.image_base64:
        # Vision-capable models accept image_url content parts
        data_url = f"data:{req.image_media_type or 'image/png'};base64,{req.image_base64}"
        parts.append({"type": "image_url", "image_url": {"url": data_url}})

    prompt_parts = [f"Generate {req.count} test cases"]
    if req.description:
        prompt_parts.append(f"for the following feature/screen: {req.description}")
    if req.image_base64:
        prompt_parts.append("Use the screenshot above as the primary reference.")
    if req.context:
        prompt_parts.append(f"Additional context: {req.context}")
    prompt_parts.append(
        'Return ONLY a JSON array with this structure:\n'
        '[{"title":"...","preconditions":"...","steps":[{"action":"...","expected":"..."}]}]'
    )
    parts.append({"type": "text", "text": " ".join(prompt_parts)})

    # If no image, return plain text string (works with all models)
    if not req.image_base64:
        return " ".join(prompt_parts)

    return parts


def _parse_json_response(raw: str) -> list:
    """Parse JSON from AI response, stripping markdown fences if present."""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    testcases = json.loads(raw)
    if not isinstance(testcases, list):
        raise ValueError("Response is not a JSON array")
    return testcases


@router.post("/generate-from-image")
async def generate_from_image(
    image: UploadFile = File(...),
    description: str = Form(""),
    count: int = Form(5),
    context: str = Form(""),
):
    """
    Convenience endpoint: upload an image file directly (multipart form).
    Wraps /generate with base64 encoding handled server-side.
    """
    import base64
    img_bytes = await image.read()
    img_b64 = base64.b64encode(img_bytes).decode()

    media_type = image.content_type or "image/png"
    req = AIGenerateRequest(
        description=description or f"UI screen: {image.filename}",
        image_base64=img_b64,
        image_media_type=media_type,
        count=count,
        context=context or None,
    )
    return await generate_testcases(req)
