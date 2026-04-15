from fastapi import APIRouter

from models.schemas import TestcasesValidationRequest


router = APIRouter()


@router.post("/validate")
async def validate_testcases(req: TestcasesValidationRequest):
    issues = []
    total_steps = 0

    for index, testcase in enumerate(req.testcases, start=1):
        if not testcase.title.strip():
            issues.append({"level": "error", "index": index, "message": "Title is required"})

        if not testcase.steps:
            issues.append({"level": "error", "index": index, "message": "At least one step is required"})
            continue

        total_steps += len(testcase.steps)
        for step_index, step in enumerate(testcase.steps, start=1):
            if not step.action.strip():
                issues.append(
                    {
                        "level": "error",
                        "index": index,
                        "message": f"Step {step_index} is missing an action",
                    }
                )
            if not step.expected.strip():
                issues.append(
                    {
                        "level": "warning",
                        "index": index,
                        "message": f"Step {step_index} is missing an expected result",
                    }
                )

    errors = sum(1 for issue in issues if issue["level"] == "error")
    warnings = sum(1 for issue in issues if issue["level"] == "warning")

    return {
        "valid": errors == 0,
        "issues": issues,
        "stats": {
            "total": len(req.testcases),
            "total_steps": total_steps,
            "errors": errors,
            "warnings": warnings,
        },
    }