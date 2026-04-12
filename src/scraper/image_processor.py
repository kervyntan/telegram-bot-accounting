"""Phase 2: Anti-reverse-search image processing using OpenCV."""

import logging
import os
import tempfile

import cv2
import httpx
import numpy as np

logger = logging.getLogger(__name__)


async def download_image(url: str) -> np.ndarray | None:
    """Download an image from URL and return as OpenCV array."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            img_array = np.frombuffer(resp.content, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            return img
    except Exception as e:
        logger.error(f"Failed to download image from {url}: {e}")
        return None


def order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 corner points as: top-left, top-right, bottom-right, bottom-left."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left has smallest sum
    rect[2] = pts[np.argmax(s)]  # bottom-right has largest sum
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right has smallest difference
    rect[3] = pts[np.argmax(diff)]  # bottom-left has largest difference
    return rect


def detect_and_crop_card(img: np.ndarray) -> np.ndarray:
    """Detect a rectangular card/slab in the image and apply perspective transform.

    Falls back to center-crop if no rectangle is found.
    """
    h, w = img.shape[:2]

    # Preprocessing
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    # Dilate edges to close gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=2)

    # Find contours
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Sort by area (largest first)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    card_contour = None
    for contour in contours[:10]:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        # Look for a quadrilateral that's a reasonable size (at least 10% of image area)
        if len(approx) == 4 and cv2.contourArea(approx) > (h * w * 0.10):
            card_contour = approx
            break

    if card_contour is not None:
        # Perspective transform to flatten the card
        pts = card_contour.reshape(4, 2).astype("float32")
        rect = order_points(pts)

        tl, tr, br, bl = rect
        width_a = np.linalg.norm(br - bl)
        width_b = np.linalg.norm(tr - tl)
        max_width = int(max(width_a, width_b))

        height_a = np.linalg.norm(tr - br)
        height_b = np.linalg.norm(tl - bl)
        max_height = int(max(height_a, height_b))

        dst = np.array(
            [
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1],
            ],
            dtype="float32",
        )

        matrix = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(img, matrix, (max_width, max_height))
        logger.info(f"Card detected and warped: {max_width}x{max_height}")
        return warped

    # Fallback: center crop (remove 15% from each edge)
    logger.info("No card rectangle found, applying center crop fallback")
    margin_x = int(w * 0.15)
    margin_y = int(h * 0.15)
    cropped = img[margin_y : h - margin_y, margin_x : w - margin_x]
    return cropped


def apply_anti_search_transforms(img: np.ndarray) -> np.ndarray:
    """Apply subtle transforms that defeat image hash matching without degrading quality.

    - Slight rotation (0.5-1.5 degrees)
    - Minor brightness/contrast adjustment
    - Resize to non-standard dimensions
    """
    h, w = img.shape[:2]

    # Slight random rotation
    angle = np.random.uniform(0.3, 1.0) * np.random.choice([-1, 1])
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    img = cv2.warpAffine(img, matrix, (w, h), borderMode=cv2.BORDER_REFLECT)

    # Minor brightness/contrast adjustment
    alpha = np.random.uniform(0.97, 1.03)  # contrast
    beta = np.random.uniform(-3, 3)  # brightness
    img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

    # Resize to slightly non-standard dimensions
    new_w = w + np.random.randint(-5, 6)
    new_h = h + np.random.randint(-5, 6)
    img = cv2.resize(img, (max(new_w, 100), max(new_h, 100)), interpolation=cv2.INTER_LANCZOS4)

    return img


async def process_listing_image(image_url: str, listing_id: str) -> str | None:
    """Download listing image and save as-is (no cropping or transforms).

    Returns the path to the saved image, or None on failure.
    """
    img = await download_image(image_url)
    if img is None:
        return None

    # Save to temp directory without any modifications
    output_dir = os.path.join(tempfile.gettempdir(), "processed_cards")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{listing_id}.jpg")

    cv2.imwrite(output_path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    logger.info(f"Image saved: {output_path}")
    return output_path
