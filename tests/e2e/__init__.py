"""End-to-end tests with real API calls.

These tests exercise the complete backend flow WITHOUT mocks.
They make real API calls to OpenAI/Anthropic and should be run
sparingly to avoid quota issues.

To run E2E tests, modify the skipif condition in the test file:
    @pytest.mark.skipif(
        False,  # Set to False to enable
        reason="..."
    )

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""
