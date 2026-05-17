Helpful utility scripts for the competition repo.

- `create_submission_template.py`: creates `submissions/working_submission.csv`
  - uses `data/raw/sample_submission.csv` if present
  - otherwise uses `data/raw/test.csv`
  - otherwise falls back to ids `0..8519` based on the competition description
