"""Known-answer check for the OCR pipeline.

OCR quality is assumed by everything downstream, so prove it before trusting a
single coordinate: hand it a screenshot whose content you already read by eye
and fail loudly if any expected string is missing.

  python validate_ocr.py shot.png "Pre-viewing" "Activity 1" 答题
"""
import sys
import time

from rapidocr_onnxruntime import RapidOCR


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)

    image, expected = sys.argv[1], sys.argv[2:]
    ocr = RapidOCR()

    t0 = time.time()
    result, _ = ocr(image)
    cold = time.time() - t0

    t0 = time.time()
    result, _ = ocr(image)
    warm = time.time() - t0

    print(f"first call (incl. model load): {cold:.2f}s   warm call: {warm:.2f}s")
    print(f"blocks: {len(result) if result else 0}\n")

    found = {}
    for box, text, score in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        cx, cy = sum(xs) / 4, sum(ys) / 4
        print(f"({cx:6.0f},{cy:6.0f}) conf={float(score):.2f}  {text}")
        found[text] = (cx, cy)

    print()
    missing = []
    for want in expected:
        hit = any(want.lower() in t.lower() for t in found)
        print(f"{'OK  ' if hit else 'MISS'}  {want}")
        if not hit:
            missing.append(want)

    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
