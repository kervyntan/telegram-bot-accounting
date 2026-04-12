"""Card condition grader using YOLOv8 defect detection.

Analyzes card images for defects (corner wear, edge wear, scratches)
and produces a gradability score based on defect count and severity.
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Default model path (relative to project root)
DEFAULT_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "models" / "card_grader" / "weights" / "best.pt"


@dataclass
class DefectInfo:
    """A single detected defect on a card."""

    defect_type: str  # "Corner Wear", "Edge Wear", "Scratch"
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2


@dataclass
class GradeResult:
    """Grading result for a single card image."""

    gradable: bool
    score: float  # 0.0 (worst) to 10.0 (best)
    grade_label: str  # "Gem Mint", "Mint", "Near Mint", etc.
    defects: list[DefectInfo] = field(default_factory=list)
    card_detected: bool = False

    @property
    def summary(self) -> str:
        defect_counts = {}
        for d in self.defects:
            defect_counts[d.defect_type] = defect_counts.get(d.defect_type, 0) + 1
        parts = [f"{self.grade_label} ({self.score:.1f}/10)"]
        if defect_counts:
            defect_str = ", ".join(f"{v}x {k}" for k, v in defect_counts.items())
            parts.append(f"Defects: {defect_str}")
        if self.gradable:
            parts.append("Worth grading")
        else:
            parts.append("Not recommended for grading")
        return " | ".join(parts)


def _score_to_label(score: float) -> str:
    """Convert a numeric score to a PSA-style grade label."""
    if score >= 9.5:
        return "Gem Mint (PSA 10)"
    elif score >= 8.5:
        return "Mint (PSA 9)"
    elif score >= 7.5:
        return "Near Mint-Mint (PSA 8)"
    elif score >= 6.5:
        return "Near Mint (PSA 7)"
    elif score >= 5.5:
        return "Excellent-Mint (PSA 6)"
    elif score >= 4.5:
        return "Excellent (PSA 5)"
    else:
        return "Below Excellent (PSA <5)"


# Penalty weights per defect type — higher means more damaging to grade
DEFECT_PENALTIES = {
    "Corner Wear": 0.6,
    "Edge Wear": 0.4,
    "Scratch": 0.8,
}

# Confidence threshold below which detections are ignored
CONFIDENCE_THRESHOLD = 0.3

# Score threshold for recommending grading (PSA 8+)
GRADABLE_THRESHOLD = 7.5


def grade_card(image_path: str, model_path: str | None = None) -> GradeResult:
    """Grade a card image for condition/gradability.

    Args:
        image_path: Path to the card image file.
        model_path: Path to the trained YOLOv8 weights. Uses default if None.

    Returns:
        GradeResult with score, label, defects, and gradability recommendation.
    """
    from ultralytics import YOLO

    weights = model_path or str(DEFAULT_MODEL_PATH)
    if not os.path.exists(weights):
        logger.error(f"Model weights not found at {weights}")
        return GradeResult(
            gradable=False, score=0.0, grade_label="Unknown", card_detected=False
        )

    model = YOLO(weights)
    results = model(image_path, verbose=False)

    defects: list[DefectInfo] = []
    card_detected = False

    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            cls_name = result.names[cls_id]
            coords = tuple(float(x) for x in box.xyxy[0])

            if cls_name == "Card":
                card_detected = True
                continue

            if conf < CONFIDENCE_THRESHOLD:
                continue

            defects.append(
                DefectInfo(
                    defect_type=cls_name,
                    confidence=conf,
                    bbox=coords,
                )
            )

    # Calculate score: start at 10, deduct per defect weighted by type and confidence
    score = 10.0
    for defect in defects:
        penalty = DEFECT_PENALTIES.get(defect.defect_type, 0.5)
        score -= penalty * defect.confidence
    score = max(0.0, min(10.0, score))

    grade_label = _score_to_label(score)
    gradable = score >= GRADABLE_THRESHOLD

    return GradeResult(
        gradable=gradable,
        score=score,
        grade_label=grade_label,
        defects=defects,
        card_detected=card_detected,
    )


async def grade_card_from_url(image_url: str, model_path: str | None = None) -> GradeResult:
    """Download an image from URL and grade it."""
    import tempfile

    import httpx

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(image_url, timeout=15, follow_redirects=True)
            resp.raise_for_status()

        suffix = ".jpg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(resp.content)
            tmp_path = f.name

        result = grade_card(tmp_path, model_path)
        os.unlink(tmp_path)
        return result
    except Exception as e:
        logger.error(f"Failed to grade image from {image_url}: {e}")
        return GradeResult(
            gradable=False, score=0.0, grade_label="Error", card_detected=False
        )
