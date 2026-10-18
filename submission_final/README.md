# HackerRank Orchestrate Submission - Message Notification Router

This folder contains the complete, verified submission package for the Message Notification Router platform.

## Contents

- `code_final.zip`: Executable Python source code (`code/`), automated test suite (`tests/`), domain knowledge rules (`knowledge/`), and setup instructions (`README.md`).
- `output.csv`: Complete predictions (110 rows) for `dataset/messages.csv`.
- `log.txt`: Independent evaluation log verifying schema compliance, confidence bounds, and regression suite execution.
- `README.md`: Submission overview and verification instructions.

## Verification & Execution

To run the pipeline against `dataset/` and reproduce `output.csv`:

```bash
python -m code.main
```

To execute the offline unit and regression test suite:

```bash
python -c "import unittest; suite = unittest.TestLoader().discover('tests'); runner = unittest.TextTestRunner(verbosity=2); runner.run(suite)"
```
