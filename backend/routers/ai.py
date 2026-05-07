import os
import json
import anthropic
from openai import AsyncOpenAI
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address
from models.schemas import AIGenerateRequest

router = APIRouter()

limiter = Limiter(key_func=get_remote_address)

# Max image size: 10 MB
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

# ── Provider config ──────────────────────────────────────
# AI_PROVIDER: "anthropic" or "nvidia"
AI_PROVIDER = os.getenv("AI_PROVIDER", "anthropic").lower()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.1-70b-instruct")
NVIDIA_VISION_MODEL = os.getenv("NVIDIA_VISION_MODEL", "meta/llama-3.2-90b-vision-instruct")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

# ── Type-specific system prompts ─────────────────────────

SYSTEM_PROMPT_UI = """
You are a Senior QA Engineer.

I will provide:

1. A screenshot of a web application page
2. A brief explanation of what the page does and how it works

Your task is to generate comprehensive test cases for that page.

Follow these STRICT rules:

1. FORMAT:

* Output must be in JSON format
* Structure must be:
  [
  {
  "title": "...",
  "preconditions": "...",
  "steps": [
  {
  "action": "...",
  "expected": "..."
  }
  ]
  }
  ]

2. NAMING CONVENTION:

* Title must follow:
  "<App Name> - <Page Name> - <Scenario Name>"
  where <App Name> is derived from the user's description.

3. COMMON STEP (MANDATORY):

* Every test case MUST include this as Step 1:
  Action: Log in to the application using valid credentials
  Expected: The application page should be opened successfully.

4. COVERAGE:
   Generate a mix of:

* Positive test cases (valid flows)
* Negative test cases (invalid inputs, failures)
* Edge cases (boundary conditions, unusual scenarios)

5. INCLUDE TESTING FOR:

* Page load
* UI elements visibility
* Input fields validation
* Buttons (enabled/disabled behavior)
* Dropdowns / filters
* Search functionality (if available)
* Table data validation (if available)
* Actions (create/update/delete/cancel/etc.)
* Error handling
* Empty states
* API failure scenarios (UI behavior)
* Permissions (if applicable)
* Responsiveness (basic)

6. BEHAVIOR RULES:

* Do NOT skip important scenarios
* Do NOT give explanations outside JSON
* Keep steps clear and concise
* Each step must have action + expected result
* Use realistic QA language

7. OUTPUT SIZE:

* Generate at least 12-20 test cases
* Ensure good coverage (not repetitive)

Now based on the provided screenshot and explanation, generate the test cases.
"""

SYSTEM_PROMPT_SWAGGER = """
You are an experienced QA Engineer specialized in API testing.

I will provide:

* Swagger UI screenshots
* Swagger URLs
* API endpoint details

Your task is to generate comprehensive API test cases.

STRICT REQUIREMENTS:

1. Generate:

* Positive test cases
* Negative test cases
* Edge case test cases

2. Output must ALWAYS be in valid JSON array format only.

3. Every test case MUST follow this EXACT structure:

{
"title": "<Test Case Title>",
"preconditions": "Postman application is open",
"steps": [
{
"action": "Navigate to the Swagger page: <swagger-url> and ensure V3 is selected.",
"expected": "The Swagger page should load successfully."
},
{
"action": "Click Authorize and enter a valid Bearer token.",
"expected": "The Authorization Bearer token should be added successfully."
},
{
"action": "Execute the GET/POST/PUT/DELETE request <full-api-url> with valid/invalid/missing data based on scenario.",
"expected": "Expected API behavior and response code."
}
]
}

4. VERY IMPORTANT FORMAT RULES:

* Use FULL Swagger URL in every test case.
* Use FULL API endpoint URL in every Execute step.
* Do NOT shorten text like:
  * "Navigate to Swagger"
  * "Authorize"
  * "Execute GET"
* Always use complete sentences exactly like the format above.
* Keep wording consistent across ALL test cases.
* Do NOT add explanations outside JSON.
* Do NOT use markdown.
* Do NOT summarize.
* Return JSON only.

5. Test coverage must include:

* Valid requests
* Invalid IDs
* Missing parameters
* Unauthorized requests (401)
* Forbidden requests (403)
* Duplicate operations
* Expired/invalid data
* Empty request body
* Invalid request body
* Boundary/edge conditions

6. Generate at least:

* 20+ test cases by default
* unless user requests fewer

7. API-specific behavior:

* Use correct HTTP method:
  * GET
  * POST
  * PUT
  * DELETE
* Match endpoint names exactly from Swagger screenshot.

8. Example format:

{
"title": "License Service - Get Licenses by Account - Missing AccountId",
"preconditions": "Postman application is open",
"steps": [
{
"action": "Navigate to the License Swagger page: https://dev-services.trimbleplatform.ninja/licenses/swagger/index.html and ensure V3 is selected.",
"expected": "The License Swagger page should load successfully."
},
{
"action": "Click Authorize and enter a valid Bearer token.",
"expected": "The Authorization Bearer token should be added successfully."
},
{
"action": "Execute the GET request https://dev-services.trimbleplatform.ninja/licenses/v3/License/account/ without providing accountId.",
"expected": "The API should return 400 Bad Request."
}
]
}

Wait for Swagger screenshot or API details before generating output.
"""

SYSTEM_PROMPT_POSTMAN = """
Generate API test cases in JSON format for the provided endpoints.

Requirements:

1. Output Format

* Return ONLY a valid JSON array.
* Do not include markdown, explanations, notes, or extra text outside JSON.

2. JSON Structure
   Each test case must follow this exact structure:

{
"title": "",
"preconditions": "",
"steps": [
{
"action": "",
"expected": ""
}
]
}

3. Title Format
   The title must follow this format exactly:

"<Service Name> - <Endpoint Action> - <Scenario>"

Examples:

* "E2E Messenger Service - Create Topic - Create topic with valid data"
* "E2E Messenger Service - Send Message - Send message with empty payload"

4. Preconditions
   Default precondition:
   "Postman application is open"

If required, add extra conditions:
Examples:

* "Postman application is open and topic exists"
* "Postman application is open and subscription already exists"

5. Step Formatting Rules
   Each test case must contain exactly 3 steps.

Step 1 must ALWAYS follow this exact wording:

{
"action": "Open the <Service Name> API collection in Postman and enter a valid bearer token in the Auth tab",
"expected": "The bearer token should be added successfully, and the collection should be accessible."
}

Do NOT shorten this wording.
Do NOT replace it with:

* "Authorize request"
* "Access granted"
* or any simplified text.

6. Step 2 Rules
   Step 2 must:

* Mention HTTP method
* Mention FULL endpoint URL
* Mention request payload if applicable
* Mention the exact action being performed

Examples:

POST:
"Navigate to POST https://dev-trimblee2emessenger.mepdevelopment.net/Topic and send the request with valid topic payload"

GET:
"Navigate to GET https://dev-trimblee2emessenger.mepdevelopment.net/Topic/{topicName} and send the request with valid topic name"

DELETE:
"Navigate to DELETE https://dev-trimblee2emessenger.mepdevelopment.net/Message/{topic}/{subscription}/{messageId} and send the request"

If request body is provided in input, include it naturally in Step 2.

7. Step 3 Rules
   Step 3 must always inspect the response.

Examples:
{
"action": "Inspect the response body",
"expected": "It should contain the details of the newly created topic."
}

8. Test Coverage
   Generate exactly 3 test cases for EACH endpoint:

* Positive scenario
* Negative scenario
* Edge/validation scenario

Examples:

* Valid payload
* Duplicate data
* Missing fields
* Empty payload
* Invalid identifiers
* Non-existing resource

9. Expected Results
   Expected results must:

* Mention proper HTTP status codes
* Clearly describe API behavior
* Be professional and detailed

Examples:

* "The API should return a 200 OK response."
* "The API should return a 400 Bad Request response."
* "The API should return a 404 Not Found response."

10. Endpoint Coverage
    Generate test cases for ALL endpoints provided in the input.
    Do NOT skip endpoints.

11. Style Rules

* Use full professional wording
* Keep wording consistent across all test cases
* Do NOT shorten actions or expected results
* Maintain enterprise QA documentation style

12. Input Format
    Input endpoints will be provided like:

<Service Name> - <URL> - <Endpoint Action> - <Method>

Example:
E2E Messenger Service - https://dev-trimblee2emessenger.mepdevelopment.net/Topic - Create Topic - POST

Generate complete JSON test cases for all provided endpoints.
"""

SYSTEM_PROMPTS = {
    "ui": SYSTEM_PROMPT_UI,
    "swagger": SYSTEM_PROMPT_SWAGGER,
    "postman": SYSTEM_PROMPT_POSTMAN,
}


def _get_system_prompt(test_type: str) -> str:
    return SYSTEM_PROMPTS.get(test_type, SYSTEM_PROMPT_UI)


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

    prompt_parts = []
    if req.count > 0:
        prompt_parts.append(f"Generate {req.count} test cases")
    else:
        prompt_parts.append("Generate test cases based on the scenario (decide the appropriate number)")
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
@limiter.limit("10/minute")
async def generate_testcases(request: Request, req: AIGenerateRequest):
    """
    Generate test cases using AI (Anthropic Claude or NVIDIA NIM).
    Set AI_PROVIDER env var to 'nvidia' and NVIDIA_API_KEY to use NVIDIA.
    """
    if not req.description and not req.image_base64:
        raise HTTPException(
            status_code=400,
            detail="Provide at least a description or an image."
        )

    # Validate image size (base64 is ~33% larger than raw bytes)
    if req.image_base64 and len(req.image_base64) > MAX_IMAGE_SIZE_BYTES * 1.34:
        raise HTTPException(
            status_code=413,
            detail="Image too large. Maximum size is 10 MB."
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
        system_prompt = _get_system_prompt(req.test_type)
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8192,
            system=system_prompt,
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
        system_prompt = _get_system_prompt(req.test_type)
        client = AsyncOpenAI(api_key=NVIDIA_API_KEY, base_url=NVIDIA_BASE_URL)

        # Use vision model if image is provided, otherwise text model
        model = NVIDIA_VISION_MODEL if req.image_base64 else NVIDIA_MODEL

        # Build message content for OpenAI-compatible API
        user_content = _build_nvidia_user_content(req)

        response = await client.chat.completions.create(
            model=model,
            max_tokens=8192,
            messages=[
                {"role": "system", "content": system_prompt},
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
            "model": model,
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

    prompt_parts = []
    if req.count > 0:
        prompt_parts.append(f"Generate {req.count} test cases")
    else:
        prompt_parts.append("Generate test cases based on the scenario (decide the appropriate number)")
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
    """Parse JSON from AI response, stripping markdown fences and extra text."""
    import re
    # Strip markdown code fences
    if "```" in raw:
        match = re.search(r'```(?:json)?\s*\n?(.*?)```', raw, re.DOTALL)
        if match:
            raw = match.group(1)
    raw = raw.strip()
    # Try direct parse first
    try:
        testcases = json.loads(raw)
        if isinstance(testcases, list):
            return testcases
    except json.JSONDecodeError:
        pass
    # Try to find JSON array in the text
    bracket_start = raw.find('[')
    bracket_end = raw.rfind(']')
    if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
        candidate = raw[bracket_start:bracket_end + 1]
        testcases = json.loads(candidate)
        if isinstance(testcases, list):
            return testcases
    raise ValueError("Could not extract valid JSON array from AI response")


@router.post("/generate-from-image")
@limiter.limit("10/minute")
async def generate_from_image(
    request: Request,
    image: UploadFile = File(...),
    description: str = Form(""),
    count: int = Form(5),
    test_type: str = Form("ui"),
):
    """
    Convenience endpoint: upload an image file directly (multipart form).
    Wraps /generate with base64 encoding handled server-side.
    """
    import base64
    img_bytes = await image.read()

    if len(img_bytes) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large. Maximum size is 10 MB.")

    img_b64 = base64.b64encode(img_bytes).decode()

    media_type = image.content_type or "image/png"
    req = AIGenerateRequest(
        description=description or f"UI screen: {image.filename}",
        image_base64=img_b64,
        image_media_type=media_type,
        count=count,
        test_type=test_type,
    )
    return await generate_testcases(req)
