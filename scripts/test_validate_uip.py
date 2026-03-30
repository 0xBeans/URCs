import subprocess
import tempfile
import os
import unittest


class TestValidateUIP(unittest.TestCase):
    def _run_validator(self, filename, content):
        """Write content to a temp dir under UIPs/ and run the validator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            uips_dir = os.path.join(tmpdir, "UIPs")
            os.makedirs(uips_dir)
            filepath = os.path.join(uips_dir, filename)
            with open(filepath, "w") as f:
                f.write(content)
            result = subprocess.run(
                ["python3", "scripts/validate_uip.py", filepath],
                capture_output=True,
                text=True,
            )
            return result

    def test_valid_uip(self):
        content = """---
uip: 2
title: Test Proposal
author: Test Author (@test)
status: Draft
created: 2026-01-01
---

## Abstract

Test abstract.

## Specification

Test specification.

## Rationale

Test rationale.

## Security Considerations

None.

## Copyright

Copyright and related rights waived via CC0.
"""
        result = self._run_validator("uip-2.md", content)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_required_field(self):
        content = """---
uip: 2
title: Test Proposal
status: Draft
created: 2026-01-01
---

## Abstract

Test.

## Specification

Test.

## Rationale

Test.

## Security Considerations

None.

## Copyright

CC0.
"""
        result = self._run_validator("uip-2.md", content)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("author", result.stderr)

    def test_invalid_status(self):
        content = """---
uip: 2
title: Test Proposal
author: Test (@test)
status: Approved
created: 2026-01-01
---

## Abstract

Test.

## Specification

Test.

## Rationale

Test.

## Security Considerations

None.

## Copyright

CC0.
"""
        result = self._run_validator("uip-2.md", content)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status", result.stderr.lower())

    def test_missing_required_section(self):
        content = """---
uip: 2
title: Test Proposal
author: Test (@test)
status: Draft
created: 2026-01-01
---

## Abstract

Test.

## Specification

Test.

## Rationale

Test.

## Copyright

CC0.
"""
        result = self._run_validator("uip-2.md", content)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Security Considerations", result.stderr)

    def test_filename_number_mismatch(self):
        content = """---
uip: 3
title: Test Proposal
author: Test (@test)
status: Draft
created: 2026-01-01
---

## Abstract

Test.

## Specification

Test.

## Rationale

Test.

## Security Considerations

None.

## Copyright

CC0.
"""
        result = self._run_validator("uip-2.md", content)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("filename", result.stderr.lower())

    def test_invalid_filename_format(self):
        content = """---
uip: 2
title: Test Proposal
author: Test (@test)
status: Draft
created: 2026-01-01
---

## Abstract

Test.

## Specification

Test.

## Rationale

Test.

## Security Considerations

None.

## Copyright

CC0.
"""
        result = self._run_validator("proposal-2.md", content)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
