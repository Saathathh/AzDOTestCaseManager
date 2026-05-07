from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Step(BaseModel):
    action: str
    expected: str


class TestCase(BaseModel):
    title: str
    preconditions: str = ""
    steps: List[Step]


class AzdoConfig(BaseModel):
    org: str
    project: str
    pat: str
    plan_id: int
    story_id: int
    parent_suite_id: Optional[int] = None
    parent_suite_name: Optional[str] = None
    desired_state: str = "Ready"
    tags: str = ""


class ProfileRequest(BaseModel):
    name: str
    config: AzdoConfig


class UploadRequest(BaseModel):
    config: AzdoConfig
    testcases: List[TestCase]


class AIGenerateRequest(BaseModel):
    description: Optional[str] = None
    image_base64: Optional[str] = None
    image_media_type: Optional[str] = None
    count: int = Field(default=0, ge=0, le=50)
    test_type: str = "ui"
    context: Optional[str] = None


class TestcasesValidationRequest(BaseModel):
    testcases: List[TestCase]


class ProfileResponse(BaseModel):
    name: str
    data: dict

    model_config = ConfigDict(extra="ignore")