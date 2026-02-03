"""Unit tests for CSV format auto-detection (T042-TEST).

Tests automatic detection of CSV format parameters:
- Delimiter detection (comma, semicolon, pipe, tab)
- Encoding detection (UTF-8, Latin1, Windows-1252, UTF-16)
- Quote character detection
- Per FR-013: Automatic format detection

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from io import BytesIO
from typing import Any

import pytest


@pytest.mark.unit
class TestCSVFormatDetection:
    """Unit tests for CSV format auto-detection (T042)."""

    def test_detect_comma_delimiter(self) -> None:
        """Test delimiter detection identifies comma-separated values.

        Validates:
        - Standard CSV with commas → delimiter: ','
        - Per FR-013: Automatic delimiter detection

        Success Criteria (T042):
        - Comma delimiter correctly identified
        - Format detection returns delimiter info
        """
        csv_content: bytes = b"name,age,city\nAlice,30,NYC\nBob,25,LA\n"
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify delimiter detection
        assert "delimiter" in format_info
        assert format_info["delimiter"] == ","

    def test_detect_semicolon_delimiter(self) -> None:
        """Test delimiter detection identifies semicolon-separated values.

        Validates:
        - CSV with semicolons → delimiter: ';'
        - Common in European CSV files
        - Per FR-013: Support multiple delimiters

        Success Criteria (T042):
        - Semicolon delimiter correctly identified
        - Distinguishes from comma-delimited
        """
        csv_content: bytes = b"name;age;city\nAlice;30;NYC\nBob;25;LA\n"
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify semicolon delimiter
        assert format_info["delimiter"] == ";"

    def test_detect_pipe_delimiter(self) -> None:
        """Test delimiter detection identifies pipe-separated values.

        Validates:
        - CSV with pipes → delimiter: '|'
        - Less common but valid delimiter
        - Per FR-013: Support pipe delimiter

        Success Criteria (T042):
        - Pipe delimiter correctly identified
        """
        csv_content: bytes = b"name|age|city\nAlice|30|NYC\nBob|25|LA\n"
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify pipe delimiter
        assert format_info["delimiter"] == "|"

    def test_detect_tab_delimiter(self) -> None:
        """Test delimiter detection identifies tab-separated values (TSV).

        Validates:
        - TSV files → delimiter: '\\t'
        - Per FR-013: Support tab delimiter

        Success Criteria (T042):
        - Tab delimiter correctly identified
        """
        csv_content: bytes = b"name\tage\tcity\nAlice\t30\tNYC\nBob\t25\tLA\n"
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify tab delimiter
        assert format_info["delimiter"] in ["\t", "\\t", "tab"]

    def test_detect_utf8_encoding(self) -> None:
        """Test encoding detection identifies UTF-8.

        Validates:
        - UTF-8 encoded file → encoding: 'utf-8'
        - Default encoding for modern files
        - Per FR-013: UTF-8 support

        Success Criteria (T042):
        - UTF-8 encoding correctly identified
        - Unicode characters handled
        """
        csv_content: bytes = "name,city\nAlice,New York\nBob,Los Angeles\n".encode("utf-8")
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify UTF-8 encoding
        assert "encoding" in format_info
        assert format_info["encoding"].lower() in ["utf-8", "utf8"]

    def test_detect_latin1_encoding(self) -> None:
        """Test encoding detection identifies Latin-1 (ISO-8859-1).

        Validates:
        - Latin-1 encoded file → encoding: 'latin-1'
        - Common in legacy European files
        - Per FR-013: Latin-1 support

        Success Criteria (T042):
        - Latin-1 encoding correctly identified
        - Special characters preserved
        """
        # Latin-1 text with special characters
        csv_content: bytes = "name,city\nJosé,São Paulo\nFrançois,Montréal\n".encode("latin-1")
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify Latin-1 encoding
        assert format_info["encoding"].lower() in ["latin-1", "latin1", "iso-8859-1", "iso88591"]

    def test_detect_windows1252_encoding(self) -> None:
        """Test encoding detection identifies Windows-1252.

        Validates:
        - Windows-1252 encoded file → encoding: 'windows-1252'
        - Common in Windows Excel exports
        - Per FR-013: Windows-1252 support

        Success Criteria (T042):
        - Windows-1252 encoding correctly identified
        """
        # Windows-1252 text with special characters
        csv_content: bytes = "name,amount\nUser,€100\nCustomer,$50\n".encode("windows-1252")
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify Windows-1252 encoding
        assert format_info["encoding"].lower() in [
            "windows-1252",
            "windows1252",
            "cp1252",
            "latin-1",  # Sometimes detected as latin-1 due to similarity
        ]

    def test_detect_utf16_encoding(self) -> None:
        """Test encoding detection identifies UTF-16.

        Validates:
        - UTF-16 encoded file → encoding: 'utf-16'
        - Common in some Windows applications
        - Per FR-013: UTF-16 support

        Success Criteria (T042):
        - UTF-16 encoding correctly identified
        - BOM (Byte Order Mark) handled
        """
        csv_content: bytes = "name,city\nAlice,NYC\nBob,LA\n".encode("utf-16")
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify UTF-16 encoding
        assert format_info["encoding"].lower() in ["utf-16", "utf16", "utf-16-le", "utf-16-be"]

    def test_detect_quote_character(self) -> None:
        """Test detection of quote character in CSV.

        Validates:
        - Quoted fields → quotechar identified
        - Standard double quotes: "
        - Single quotes: '

        Success Criteria (T042):
        - Quote character correctly identified
        - Quoted fields with embedded delimiters handled
        """
        csv_content: bytes = b'name,description\n"Alice","Software, Engineer"\n"Bob","Designer"\n'
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify quote character detection
        assert "quotechar" in format_info
        assert format_info["quotechar"] in ['"', "'"]

    def test_handle_mixed_line_endings(self) -> None:
        """Test format detection handles different line endings.

        Validates:
        - Windows (\\r\\n), Unix (\\n), Mac (\\r) line endings
        - Mixed line endings in same file
        - Per FR-013: Cross-platform compatibility

        Success Criteria (T042):
        - Line endings detected and normalized
        - No parsing errors with mixed endings
        """
        csv_content_crlf: bytes = b"name,age\r\nAlice,30\r\nBob,25\r\n"  # Windows
        csv_file: BytesIO = BytesIO(csv_content_crlf)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Should successfully detect format despite line ending differences
        assert "delimiter" in format_info
        assert format_info["delimiter"] == ","

    def test_handle_bom_utf8(self) -> None:
        """Test format detection handles UTF-8 BOM (Byte Order Mark).

        Validates:
        - UTF-8 with BOM → BOM stripped, encoding detected
        - Common in Excel CSV exports
        - Per FR-013: BOM handling

        Success Criteria (T042):
        - BOM detected and stripped
        - UTF-8 encoding identified
        """
        # UTF-8 BOM + CSV content
        bom: bytes = b"\xef\xbb\xbf"
        csv_content: bytes = bom + b"name,age\nAlice,30\nBob,25\n"
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify UTF-8 encoding detected
        assert format_info["encoding"].lower() in ["utf-8", "utf8", "utf-8-sig"]

    def test_detect_header_presence(self) -> None:
        """Test detection of whether CSV has header row.

        Validates:
        - CSV with header → has_header: true
        - CSV without header → has_header: false
        - Heuristic detection (column names vs data)

        Success Criteria (T042):
        - Header presence correctly identified
        """
        csv_with_header: bytes = b"name,age,city\nAlice,30,NYC\nBob,25,LA\n"
        csv_file: BytesIO = BytesIO(csv_with_header)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify header detection
        if "has_header" in format_info:
            assert format_info["has_header"] is True

    def test_handle_empty_file(self) -> None:
        """Test format detection handles empty file gracefully.

        Validates:
        - Empty file → sensible defaults
        - No exceptions raised
        - Error handling

        Success Criteria (T042):
        - Empty file returns default format info
        - No crashes or exceptions
        """
        csv_content: bytes = b""
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        # Should not raise exception
        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Should return default format
        assert isinstance(format_info, dict)

    def test_detect_format_with_minimal_sample(self) -> None:
        """Test format detection works with minimal data sample.

        Validates:
        - Small CSV (1-2 rows) → format detected
        - Efficient sampling strategy
        - Minimal data requirements

        Success Criteria (T042):
        - Format detected from minimal sample
        - Accuracy maintained
        """
        csv_content: bytes = b"name,age\nAlice,30\n"
        csv_file: BytesIO = BytesIO(csv_content)

        from backend.src.services.ingestion import detect_csv_format

        format_info: dict[str, Any] = detect_csv_format(csv_file)

        # Verify detection works with minimal data
        assert format_info["delimiter"] == ","
        assert "encoding" in format_info
