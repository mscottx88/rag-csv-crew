# Example CSV Files

This directory contains sample CSV files for demonstrating the RAG CSV Crew system's capabilities.

## Files

### 1. sales.csv
**20 rows** of sample sales transaction data

**Columns**:
- `order_id`: Unique order identifier (1001-1020)
- `customer_id`: Customer reference (C101-C111)
- `product_name`: Product description
- `category`: Product category (Electronics, Furniture, Office Supplies, Accessories)
- `quantity`: Number of items ordered
- `unit_price`: Price per unit (USD)
- `order_date`: Date of order (2024-01-15 to 2024-02-03)
- `status`: Order status (Delivered, Shipped, Processing)

### 2. customers.csv
**15 rows** of sample customer profile data

**Columns**:
- `customer_id`: Unique customer identifier (C101-C115)
- `name`: Customer full name
- `email`: Customer email address
- `city`: City of residence
- `state`: State/province code
- `country`: Country (all USA)
- `registration_date`: Account registration date
- `membership_tier`: Tier level (Gold, Silver, Bronze)

## Key Features Demonstrated

### 1. Cross-Dataset Relationships
- `customer_id` column present in both datasets enables JOIN detection
- System automatically discovers this relationship via value overlap analysis

### 2. Diverse Data Types
- **Text**: product_name, category, name, email, city
- **Numeric**: quantity, unit_price
- **Date**: order_date, registration_date
- **Categorical**: status, membership_tier, category, state

### 3. Multiple Categories
- **Electronics**: Laptops, monitors, keyboards, mice, webcams, headphones
- **Furniture**: Chairs, desks, filing cabinets, lamps
- **Office Supplies**: Notebooks, whiteboards, paper shredders
- **Accessories**: Laptop bags, cable organizers, desk mats

## Example Queries

### Single Dataset Queries

**sales.csv**:
- "Show me all orders for Electronics products"
- "What are the top 5 products by revenue?"
- "How many orders are still in Processing status?"
- "What's the average order value?"
- "Which products were ordered more than once?"

**customers.csv**:
- "Show me all Gold tier members"
- "How many customers are from California?"
- "Which customers registered in January 2024?"
- "List customers by city"

### Cross-Dataset Queries

These queries leverage the automatic JOIN detection between `sales.csv` and `customers.csv`:

- "Which Gold tier customers ordered Electronics?"
- "Show me orders from customers in California"
- "What's the total revenue by membership tier?"
- "Which cities have the most orders?"
- "List all customers who ordered Furniture products"
- "What's the average order value for Silver tier members?"
- "Show customers from New York who ordered in January"

## Usage Instructions

### 1. Upload Datasets

1. Login to the application at http://localhost:5173
2. Navigate to "Upload Dataset"
3. Upload `sales.csv`
4. Upload `customers.csv`

**Wait**: The system needs ~5-10 seconds to:
- Ingest CSV data into PostgreSQL
- Detect schema and column types
- Generate semantic embeddings for all columns
- Compute column metadata (min/max, distinct values, top values)
- Detect cross-references between datasets

### 2. Query the Data

Once both datasets are uploaded, try the example queries above. The system will:

1. **Hybrid Search**: Search all columns using exact match, full-text search, and semantic similarity
2. **Confidence Scoring**: Calculate confidence based on search results quality
3. **Clarification or SQL**: Either generate SQL (high confidence) or request clarification (low confidence)
4. **Cross-Dataset JOINs**: Automatically detect and use the `customer_id` relationship
5. **HTML Formatting**: Return results as formatted HTML tables

### 3. Advanced Queries

Try ambiguous or complex queries to see the clarification system:

- "Show me information about customers and their purchases" (will suggest specific columns)
- "What's going on with orders?" (will ask for clarification about which aspect)
- "Tell me about the electronics" (will provide column options from sales data)

### 4. Test Cross-Reference Detection

The system should automatically detect that:
- `sales.customer_id` references `customers.customer_id`
- This enables JOIN queries across both datasets

Verify this by asking:
- "Show me customer names and their order amounts"
- "Which customers ordered the most products?"

## Performance Expectations

With these example datasets:

- **Upload Time**: 3-5 seconds per dataset
- **Embedding Generation**: ~200ms per column (10 columns × 200ms = 2s for sales.csv)
- **Hybrid Search**: <500ms (searches both datasets in parallel)
- **Cross-Dataset Query**: <2s total (search + SQL generation + execution + formatting)

## Dataset Statistics

### sales.csv
- **Rows**: 20
- **Columns**: 8
- **Unique customers**: 11 (C101-C111)
- **Date range**: Jan 15 - Feb 3, 2024
- **Categories**: 4 (Electronics, Furniture, Office Supplies, Accessories)
- **Total revenue**: $6,699.81

### customers.csv
- **Rows**: 15
- **Columns**: 8
- **Unique customers**: 15 (C101-C115)
- **Date range**: Jun 15, 2023 - Feb 26, 2024
- **States**: 11 (CA, NY, IL, TX, WA, MA, CO, FL, OR, AZ, PA)
- **Tiers**: 3 (Gold: 5, Silver: 5, Bronze: 5)

## Extending the Examples

To create your own example datasets:

1. **Include a common key**: Add a column (like `customer_id`) to enable cross-dataset queries
2. **Mix data types**: Include text, numeric, date, and categorical columns
3. **Use realistic names**: Column names should be descriptive (e.g., `order_date` not `col1`)
4. **Add variety**: Include multiple categories, date ranges, and value distributions
5. **Keep it manageable**: 10-50 rows is ideal for testing; larger datasets work but take longer to upload

## Troubleshooting

**Issue**: Cross-dataset queries not working

**Solution**: Verify that:
1. Both datasets are uploaded and visible in the dataset list
2. The common key column (`customer_id`) has matching values
3. System detected the cross-reference (check logs for "cross_reference detected" events)

**Issue**: Slow upload times

**Solution**:
- Reduce the number of columns (embeddings generated per column)
- Ensure database connection is fast (localhost recommended for dev)
- Check API rate limits for embedding provider (Google Gemini, OpenAI)

**Issue**: "No columns found" error

**Solution**:
- Ensure CSV has a header row with column names
- Check that CSV is properly formatted (no malformed quotes, correct delimiters)
- Verify file encoding is UTF-8, UTF-16, Latin-1, or Windows-1252
