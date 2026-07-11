# Developer Guide

Welcome! This guide helps you understand how to contribute to the `net-mgmt` codebase, execute tests, and implement new features.

---

## 1. Architectural Vision Alignment

Every new feature, library enhancement, or technical choice **must** be aligned with the target audience, goals, and non-goals documented inside the [Technical Architecture Vision](vision.md).

- **Strict Adherence**: `docs/vision.md` is the authoritative definition of the scope of this project. It is intentionally designed to serve the lean, high-availability GitOps needs of SRE and Platform teams, deliberately leaving out complex central-CMDB features.

---

## 2. Development Environment & Setup

The project uses a standard `src` layout.

### Project Dependencies
Managed inside `pyproject.toml`. Main dependencies include:
- `click` (CLI framework)
- `ruamel.yaml` (Sorted, comment-preserving YAML persistence)
- `filelock` (Safe concurrency)
- `rich` (Styled console tables and layout engines)

---

## 2. Core Workflows

### How to Add a New Domain Field
When adding a new topological metadata field (e.g. adding `environment` or similar):

1. **Update Domain Model**:
   - Locate `class Network` inside `src/net_mgmt/core.py`.
   - Add the attribute with standard Python typing and default value (`Optional[str] = None`).
2. **Update Loader layer**:
   - Locate `load_network_from_file` and `save_network_to_file` in `src/net_mgmt/loader.py`.
   - Parse the key inside `load_network_from_file` using `data.get("new_field")`.
   - Persist the key inside `save_network_to_file` under `data["new_field"] = network.new_field`.
3. **Update Centralized Hierarchy Inheritance**:
   - If the new field belongs to the hierarchy, locate `apply_hierarchy_config` in `src/net_mgmt/loader.py` (for legacy `hierarchy.yaml`).
   - Add it to the tree traversal loops so that it can be defined inside `hierarchy.yaml` and inherited by networks.
   - For **Relational Mode**, add it to the **Metadata Resolution Cascade** loop in `load_all_networks` and the **Pruning/Serialization** logic in `save_network_to_file` in `src/net_mgmt/loader.py` so that it is properly loaded, inherited, and dry-saved from relational entities.
4. **Extend CLI & Markdown Reports**:
   - **`list` command**: Update the Table headers and row data inside `src/net_mgmt/cli.py` to display the new column.
   - **`show` command**: Update the `rich` console output inside `src/net_mgmt/cli.py` to print the new field.
   - **Markdown generator**: Update `generate_markdown_report` inside `src/net_mgmt/reports.py` to include the field inside both the overview table and the network-specific markdown details file.
5. **Write Unit Tests**:
   - Ensure the new attribute is covered by dedicated tests inside `tests/` (e.g., verifying parsing, saving, querying, and inheritance).

---

## 3. Code Quality & Formatting

All code must comply with standard Python PEP-8 rules.

### Formatting & Style
Managed automatically by **`ruff`**:
- **Format code**:
  ```bash
  ruff format .
  ```
- **Lint code**:
  ```bash
  ruff check .
  ```
- **Automatically resolve import ordering / minor issues**:
  ```bash
  ruff check . --fix
  ```

Always run both `ruff check .` and `ruff format --check .` before submitting pull requests.

---

## 4. Testing Suite

The test suite uses the standard Python `unittest` framework. All test files reside inside `tests/`.

### Running Tests
To run all tests, you **must** set the `PYTHONPATH` environment variable to include the `src` layout directory:

```bash
PYTHONPATH=src python -m unittest discover tests
```

### Writing a New Test File
If you create a new test file, name it with the `test_` prefix (e.g., `tests/test_new_feature.py`), import `unittest`, and subclass `unittest.TestCase`.

```python
import unittest
from net_mgmt.core import Network

class TestNewFeature(unittest.TestCase):
    def test_feature_logic(self):
        # Your test logic here
        pass

if __name__ == "__main__":
    unittest.main()
```
