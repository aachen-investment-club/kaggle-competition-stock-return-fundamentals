from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
SUBMISSIONS_DIR = ROOT / "submissions"
SUBMISSIONS_DIR.mkdir(exist_ok=True)

SAMPLE_PATH = RAW_DIR / "sample_submission.csv"
TEST_PATH = RAW_DIR / "test.csv"
OUTPUT_PATH = SUBMISSIONS_DIR / "working_submission.csv"


def build_template() -> pd.DataFrame:
    if SAMPLE_PATH.exists():
        submission = pd.read_csv(SAMPLE_PATH)
        if list(submission.columns) != ["id", "return_pct"]:
            raise ValueError("sample_submission.csv must contain columns: id, return_pct")
        submission["return_pct"] = 0.0
        return submission

    if TEST_PATH.exists():
        test = pd.read_csv(TEST_PATH)
        if "id" not in test.columns:
            raise ValueError("test.csv must contain an 'id' column")
        return pd.DataFrame({"id": test["id"], "return_pct": 0.0})

    # Fallback based on the competition description.
    return pd.DataFrame({"id": range(8520), "return_pct": 0.0})


if __name__ == "__main__":
    submission = build_template()
    submission.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved submission template to: {OUTPUT_PATH}")
    print(f"Rows: {len(submission)}")
