"""CSV file validation with detailed error messages.

Implements FR-002: Clear error messages for CSV validation failures

Validates:
- File format (CSV structure)
- Encoding issues
- Delimiter problems
- Header validation
- Data consistency

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import csv
from io import BytesIO, StringIO
from typing import Any, ClassVar

import chardet


class CSVValidationError(Exception):
    """Exception raised for CSV validation failures.

    Attributes:
        message: Human-readable error description
        error_code: Machine-readable error code
        details: Additional context for debugging
    """

    def __init__(self, message: str, error_code: str, details: dict[str, Any] | None = None):
        """Initialize CSV validation error.

        Args:
            message: Human-readable error description
            error_code: Machine-readable error code
            details: Additional context dictionary
        """
        super().__init__(message)
        self.message: str = message
        self.error_code: str = error_code
        self.details: dict[str, Any] = details or {}


class CSVValidator:
    """Validates CSV files and provides detailed error messages."""

    # Maximum file size for validation (100MB default)
    MAX_FILE_SIZE: int = 100 * 1024 * 1024

    # Supported encodings (in preference order)
    SUPPORTED_ENCODINGS: ClassVar[list[str]] = ["utf-8", "latin-1", "windows-1252", "utf-16"]

    # Supported delimiters
    SUPPORTED_DELIMITERS: ClassVar[list[str]] = [",", ";", "\t", "|"]

    @staticmethod
    def validate_file_format(csv_file: BytesIO) -> None:
        """Validate basic CSV file format.

        Args:
            csv_file: CSV file as BytesIO

        Raises:
            CSVValidationError: If file format is invalid

        Validation checks:
        - File is not empty
        - File size within limits
        - File is readable
        """
        csv_file.seek(0)
        content: bytes = csv_file.read()
        csv_file.seek(0)

        # Check if file is empty
        if len(content) == 0:
            raise CSVValidationError(
                message="CSV file is empty. Please upload a file with data.",
                error_code="EMPTY_FILE",
                details={"file_size_bytes": 0},
            )

        # Check file size
        file_size: int = len(content)
        if file_size > CSVValidator.MAX_FILE_SIZE:
            max_mb: float = CSVValidator.MAX_FILE_SIZE / (1024 * 1024)
            actual_mb: float = file_size / (1024 * 1024)
            raise CSVValidationError(
                message=f"CSV file is too large ({actual_mb:.1f}MB). Maximum supported size is {max_mb:.0f}MB.",
                error_code="FILE_TOO_LARGE",
                details={
                    "file_size_bytes": file_size,
                    "max_size_bytes": CSVValidator.MAX_FILE_SIZE,
                },
            )

    @staticmethod
    def validate_encoding(csv_file: BytesIO) -> str:
        """Validate and detect CSV file encoding.

        Args:
            csv_file: CSV file as BytesIO

        Returns:
            Detected encoding string

        Raises:
            CSVValidationError: If encoding cannot be detected or is unsupported

        Validation checks:
        - Encoding is detectable
        - Encoding is supported
        - File can be decoded with detected encoding
        """
        csv_file.seek(0)
        sample: bytes = csv_file.read(8192)
        csv_file.seek(0)

        # Detect encoding
        result: dict[str, Any] = chardet.detect(sample)  # type: ignore[assignment]
        detected_encoding: str | None = result.get("encoding")
        confidence: float = result.get("confidence", 0.0)

        if not detected_encoding:
            raise CSVValidationError(
                message="Unable to detect file encoding. Please ensure the file is a valid CSV in UTF-8, Latin-1, or Windows-1252 encoding.",
                error_code="ENCODING_DETECTION_FAILED",
                details={"confidence": confidence},
            )

        # Normalize encoding name
        encoding_lower: str = detected_encoding.lower()
        normalized_encoding: str

        if encoding_lower in {"utf-8", "utf8", "utf-8-sig", "ascii"}:
            normalized_encoding = "utf-8"
        elif encoding_lower in {"iso-8859-1", "latin-1", "latin1", "iso88591"}:
            normalized_encoding = "latin-1"
        elif encoding_lower in {"windows-1252", "windows1252", "cp1252"}:
            normalized_encoding = "windows-1252"
        elif encoding_lower in {"utf-16", "utf16", "utf-16-le", "utf-16-be"}:
            normalized_encoding = "utf-16"
        else:
            # Unsupported encoding
            supported_list: str = ", ".join(CSVValidator.SUPPORTED_ENCODINGS)
            raise CSVValidationError(
                message=f"Unsupported encoding '{detected_encoding}'. Supported encodings: {supported_list}. Please convert your file to UTF-8.",
                error_code="UNSUPPORTED_ENCODING",
                details={"detected_encoding": detected_encoding, "confidence": confidence},
            )

        # Verify encoding by attempting to decode
        try:
            sample.decode(normalized_encoding)
        except (UnicodeDecodeError, LookupError) as e:
            raise CSVValidationError(
                message=f"File cannot be decoded with detected encoding '{normalized_encoding}'. The file may be corrupted or have mixed encodings.",
                error_code="ENCODING_DECODE_FAILED",
                details={"detected_encoding": normalized_encoding, "error": str(e)},
            ) from e

        return normalized_encoding

    @staticmethod
    def validate_delimiter(csv_text: str) -> str:
        """Validate and detect CSV delimiter.

        Args:
            csv_text: CSV content as string

        Returns:
            Detected delimiter character

        Raises:
            CSVValidationError: If delimiter cannot be detected

        Validation checks:
        - Delimiter is detectable
        - Delimiter is one of supported characters
        - File has consistent delimiter usage
        """
        # Try automatic detection
        try:
            sniffer: csv.Sniffer = csv.Sniffer()
            dialect: Any = sniffer.sniff(
                csv_text, delimiters="".join(CSVValidator.SUPPORTED_DELIMITERS)
            )
            detected_delimiter: str = dialect.delimiter

            if detected_delimiter in CSVValidator.SUPPORTED_DELIMITERS:
                return detected_delimiter

        except csv.Error:
            pass

        # Manual detection: count occurrences of each delimiter
        sample_lines: list[str] = csv_text.split("\n")[:10]  # Check first 10 lines
        delimiter_counts: dict[str, list[int]] = {
            delim: [] for delim in CSVValidator.SUPPORTED_DELIMITERS
        }

        for line in sample_lines:
            if line.strip():
                for delim in CSVValidator.SUPPORTED_DELIMITERS:
                    delimiter_counts[delim].append(line.count(delim))

        # Find most consistent delimiter (same count across lines)
        best_delimiter: str | None = None
        min_variance: float = float("inf")

        for delim, counts in delimiter_counts.items():
            if not counts or all(c == 0 for c in counts):
                continue

            # Calculate variance
            avg: float = sum(counts) / len(counts)
            variance: float = sum((c - avg) ** 2 for c in counts) / len(counts)

            if variance < min_variance and avg > 0:
                min_variance = variance
                best_delimiter = delim

        if not best_delimiter:
            supported_list: str = ", ".join(repr(d) for d in CSVValidator.SUPPORTED_DELIMITERS)
            raise CSVValidationError(
                message=f"Unable to detect CSV delimiter. Supported delimiters: {supported_list}. Please ensure your file uses one of these delimiters consistently.",
                error_code="DELIMITER_DETECTION_FAILED",
                details={"sample": csv_text[:500]},
            )

        return best_delimiter

    @staticmethod
    def validate_header(csv_file: StringIO) -> list[str]:
        """Validate CSV header row.

        Args:
            csv_file: CSV file as StringIO

        Returns:
            List of column names from header

        Raises:
            CSVValidationError: If header is invalid

        Validation checks:
        - File has a header row
        - Header contains at least one column
        - Column names are non-empty
        - Column names are unique
        """
        csv_file.seek(0)

        try:
            reader: csv.reader = csv.reader(csv_file)
            header: list[str] = next(reader)
        except StopIteration as e:
            raise CSVValidationError(
                message="CSV file has no header row. Please ensure the first row contains column names.",
                error_code="MISSING_HEADER",
                details={},
            ) from e
        except csv.Error as e:
            raise CSVValidationError(
                message=f"CSV header is malformed: {e}. Please check the first row of your file.",
                error_code="MALFORMED_HEADER",
                details={"error": str(e)},
            ) from e

        csv_file.seek(0)

        # Check for empty header
        if not header:
            raise CSVValidationError(
                message="CSV header is empty. Please ensure the first row contains column names.",
                error_code="EMPTY_HEADER",
                details={},
            )

        # Check for empty column names
        empty_columns: list[int] = [i for i, col in enumerate(header) if not col.strip()]
        if empty_columns:
            column_positions: str = ", ".join(str(i + 1) for i in empty_columns)
            raise CSVValidationError(
                message=f"CSV header contains empty column names at positions: {column_positions}. All columns must have names.",
                error_code="EMPTY_COLUMN_NAMES",
                details={"empty_column_positions": empty_columns},
            )

        # Check for duplicate column names
        seen: set[str] = set()
        duplicates: list[str] = []
        for col in header:
            col_stripped: str = col.strip()
            if col_stripped in seen:
                duplicates.append(col_stripped)
            seen.add(col_stripped)

        if duplicates:
            duplicate_list: str = ", ".join(f"'{dup}'" for dup in duplicates)
            raise CSVValidationError(
                message=f"CSV header contains duplicate column names: {duplicate_list}. Each column must have a unique name.",
                error_code="DUPLICATE_COLUMN_NAMES",
                details={"duplicate_columns": duplicates},
            )

        return [col.strip() for col in header]

    @staticmethod
    def validate_data_consistency(csv_file: StringIO, expected_columns: int) -> None:
        """Validate CSV data consistency.

        Args:
            csv_file: CSV file as StringIO
            expected_columns: Number of columns from header

        Raises:
            CSVValidationError: If data rows have inconsistent column counts

        Validation checks:
        - All rows have the same number of columns as header
        - No completely empty rows (except at end)
        """
        csv_file.seek(0)
        reader: csv.reader = csv.reader(csv_file)

        # Skip header
        try:
            next(reader)
        except StopIteration:
            return  # Empty file after header

        # Check data rows
        row_num: int = 2  # Start from 2 (header is row 1)
        inconsistent_rows: list[tuple[int, int]] = []

        for row in reader:
            # Skip completely empty rows at the end
            if not any(cell.strip() for cell in row):
                continue

            if len(row) != expected_columns:
                inconsistent_rows.append((row_num, len(row)))

                # Stop after finding 5 inconsistent rows
                if len(inconsistent_rows) >= 5:
                    break

            row_num += 1

        csv_file.seek(0)

        if inconsistent_rows:
            error_details: str = ", ".join(
                f"row {row_num} has {col_count} columns" for row_num, col_count in inconsistent_rows
            )
            more: str = " (and more)" if len(inconsistent_rows) == 5 else ""
            raise CSVValidationError(
                message=f"CSV has inconsistent column counts. Expected {expected_columns} columns in each row, but found: {error_details}{more}. Please ensure all rows have the same number of columns.",
                error_code="INCONSISTENT_COLUMN_COUNT",
                details={
                    "expected_columns": expected_columns,
                    "inconsistent_rows": inconsistent_rows,
                },
            )

    @staticmethod
    def validate_csv_file(csv_file: BytesIO) -> dict[str, Any]:
        """Comprehensive CSV validation with detailed error messages.

        Args:
            csv_file: CSV file as BytesIO

        Returns:
            Dictionary with validation results:
            - encoding: Detected encoding
            - delimiter: Detected delimiter
            - columns: List of column names
            - valid: Boolean indicating validation success

        Raises:
            CSVValidationError: If any validation check fails

        Validation sequence:
        1. File format (size, readability)
        2. Encoding detection and validation
        3. Delimiter detection and validation
        4. Header validation
        5. Data consistency validation

        Per FR-002: Clear error messages requirement
        """
        # Step 1: Validate file format
        CSVValidator.validate_file_format(csv_file)

        # Step 2: Validate encoding
        encoding: str = CSVValidator.validate_encoding(csv_file)

        # Step 3: Decode file
        csv_file.seek(0)
        content_bytes: bytes = csv_file.read()
        csv_file.seek(0)

        try:
            content_text: str = content_bytes.decode(encoding)
        except UnicodeDecodeError as e:
            raise CSVValidationError(
                message=f"Failed to decode CSV file with detected encoding '{encoding}'. The file may be corrupted.",
                error_code="DECODE_ERROR",
                details={"encoding": encoding, "error": str(e)},
            ) from e

        # Step 4: Validate delimiter
        delimiter: str = CSVValidator.validate_delimiter(content_text)

        # Step 5: Create StringIO for CSV parsing
        csv_string_file: StringIO = StringIO(content_text)

        # Step 6: Validate header
        columns: list[str] = CSVValidator.validate_header(csv_string_file)

        # Step 7: Validate data consistency
        CSVValidator.validate_data_consistency(csv_string_file, len(columns))

        return {"encoding": encoding, "delimiter": delimiter, "columns": columns, "valid": True}
