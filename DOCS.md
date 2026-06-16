# FastCMS Documentation

FastCMS is a headless CMS built with FastAPI and SQLite. It provides dynamic collection management, authentication, and access control through a web-based admin interface and REST API.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Collection Types](#collection-types)
3. [Creating Collections](#creating-collections)
4. [Authentication System](#authentication-system)
5. [Email Verification & Password Reset](#email-verification--password-reset)
6. [CSV Import/Export](#csv-importexport)
7. [Bulk Operations](#bulk-operations)
8. [Access Control Rules](#access-control-rules)
9. [API Usage](#api-usage)
10. [Webhooks](#webhooks)
11. [Backup & Restore](#backup--restore)
12. [System Settings](#system-settings)
13. [OAuth Authentication](#oauth-authentication)
14. [Field Types](#field-types)

---

## Getting Started

### Installation

FastCMS uses [uv](https://github.com/astral-sh/uv) — install it once:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS / Linux
```

Then either install from PyPI:

```bash
uv tool install pyfastcms
fastcms init my-project && cd my-project
fastcms migrate up
fastcms dev
```

Or run from source:

```bash
git clone https://github.com/aalhommada/fastCMS && cd fastCMS
uv sync --all-extras
source .venv/bin/activate
fastcms migrate up
fastcms dev
```

See the [full installation guide](https://fastcms.org/docs/getting-started)
for Docker, cloud-storage extras, and contributor setup.

### Access the Admin Dashboard

Navigate to `http://localhost:8000/admin` in your browser. On first run, you will be prompted to create an admin account.

---

## Collection Types

FastCMS supports three types of collections:

### 1. Base Collections

Standard collections for storing any type of data.

**Use cases:**
- Products
- Blog posts
- Comments
- Orders
- Any custom data

**Features:**
- Define custom schema with any field types
- Full CRUD operations via API
- Access control rules
- Automatic timestamps (created, updated)

### 2. Auth Collections

Special collections designed for user authentication. Auth collections automatically include authentication fields and endpoints.

**Automatically added fields:**
- `email` (unique, indexed)
- `password` (hashed with bcrypt)
- `verified` (boolean, email verification status)
- `role` (string, user role)
- `token_key` (string, for session invalidation)

**Automatically created endpoints:**
- `POST /api/v1/collections/{collection_name}/auth/register` - Register new users
- `POST /api/v1/collections/{collection_name}/auth/login` - Login users
- `POST /api/v1/collections/{collection_name}/auth/refresh` - Refresh access token

**Use cases:**
- Customer accounts
- Vendor portals
- Team member access
- Any user type requiring authentication

**Example:**
Create a "customers" auth collection to allow customers to register, login, and manage their data.

### 3. View Collections

Virtual collections that compute data from other collections. Views do not store data but execute SQL queries to aggregate or join data from existing collections.

**Features:**
- Define SQL SELECT queries
- Support for JOINs, GROUP BY, ORDER BY
- Configurable caching (TTL in seconds)
- Read-only (no create, update, delete)

**Use cases:**
- Sales reports
- User statistics
- Aggregated data
- Joined data from multiple collections

**Example:**
Create a "sales_summary" view to show total sales per product by aggregating order data.

---

## Creating Collections

### Via Admin Dashboard

1. Navigate to `http://localhost:8000/admin/collections`
2. Click "Create Collection"
3. Fill in the form:
   - **Name:** Collection name (lowercase, letters, numbers, underscores only)
   - **Type:** Choose base, auth, or view
   - **Schema:** Define fields (for base/auth types)
   - **Query Configuration:** Define SQL query (for view types only)
4. Click "Create Collection"

### Via API

```bash
curl -X POST http://localhost:8000/api/v1/collections \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "products",
    "type": "base",
    "schema": [
      {
        "name": "title",
        "type": "text",
        "validation": {"required": true}
      },
      {
        "name": "price",
        "type": "number",
        "validation": {"required": true}
      }
    ]
  }'
```

---

## Authentication System

FastCMS has two authentication systems:

### 1. Built-in Admin Authentication

The `users` table is for admin dashboard access only.

**Roles:**
- `admin` - Full access to admin dashboard and all collections
- `user` - Limited access (typically not used)

**Endpoints:**
- `POST /api/v1/auth/login` - Admin login
- `POST /api/v1/auth/register` - Create admin users (requires admin token)
- `POST /api/v1/auth/refresh` - Refresh admin access token

### 2. Auth Collections (Custom User Systems)

Create auth collections for your own user systems (customers, vendors, etc.).

**Example: Customer Authentication**

1. Create "customers" auth collection
2. Customers can register at: `POST /api/v1/collections/customers/auth/register`
3. Customers can login at: `POST /api/v1/collections/customers/auth/login`

**Registration Example:**

```bash
curl -X POST http://localhost:8000/api/v1/collections/customers/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "securepassword123"
  }'
```

**Login Example:**

```bash
curl -X POST http://localhost:8000/api/v1/collections/customers/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "securepassword123"
  }'
```

**Response:**

```json
{
  "user": {
    "id": "uuid",
    "email": "customer@example.com",
    "verified": false,
    "role": "user"
  },
  "token": {
    "access_token": "eyJhbGc...",
    "refresh_token": "eyJhbGc...",
    "token_type": "bearer",
    "expires_in": 86400
  },
  "message": null,
  "requires_2fa": false
}
```

---

## Email Verification & Password Reset

FastCMS includes a complete email verification and password reset system for both admin users and auth collection users.

### SMTP Configuration

First, configure your SMTP settings in the `.env` file:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@fastcms.dev
SMTP_FROM_NAME=FastCMS
```

**Gmail Setup:**
1. Enable 2-factor authentication on your Google account
2. Generate an App Password: https://myaccount.google.com/apppasswords
3. Use the app password in `SMTP_PASSWORD`

**Other SMTP Providers:**
- **SendGrid**: Use `smtp.sendgrid.net` on port 587
- **Mailgun**: Use `smtp.mailgun.org` on port 587
- **AWS SES**: Use your SES SMTP endpoint

### Email Verification Flow

When a user registers, they receive a verification email with a token.

**1. User Registration (Email Sent Automatically)**

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
    "name": "John Doe"
  }'
```

The user will receive an email with a verification link like:
```
http://localhost:8000/verify?token=abc123...
```

**2. Verify Email**

```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{
    "token": "abc123..."
  }'
```

**Response:**
```json
{
  "message": "Email verified successfully",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "verified": true
  }
}
```

**3. Resend Verification Email**

If the token expires (valid for 24 hours), users can request a new one:

```bash
curl -X POST http://localhost:8000/api/v1/auth/resend-verification \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json"
```

### Password Reset Flow

**1. Request Password Reset**

```bash
curl -X POST http://localhost:8000/api/v1/auth/request-password-reset \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com"
  }'
```

**Response:**
```json
{
  "message": "If the email exists, a password reset link has been sent"
}
```

The user will receive an email with a reset link like:
```
http://localhost:8000/reset-password?token=xyz789...
```

**2. Reset Password**

```bash
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "xyz789...",
    "new_password": "NewSecurePass456!",
    "password_confirm": "NewSecurePass456!"
  }'
```

**Response:**
```json
{
  "message": "Password reset successfully"
}
```

### Auth Collections Email Support

Email verification and password reset also work for auth collections (customers, vendors, etc.):

**Registration (Sends Verification Email):**
```bash
curl -X POST http://localhost:8000/api/v1/collections/customers/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "password": "SecurePass123!"
  }'
```

**Request Password Reset:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/request-password-reset \
  -H "Content-Type: application/json" \
  -d '{
    "email": "customer@example.com",
    "collection": "customers"
  }'
```

### Email Templates

Email templates are HTML-based and include:
- **Verification Email**: Welcome message with verification button
- **Password Reset Email**: Security notice with reset button

Templates are located in `app/services/email_service.py` and can be customized.

### Token Security

- **Verification Tokens**: Valid for 24 hours, single-use
- **Password Reset Tokens**: Valid for 1 hour, single-use
- Tokens are cryptographically secure random strings
- Used tokens are marked and cannot be reused

### Troubleshooting

**Email Not Sending:**
1. Check SMTP credentials in `.env`
2. Verify SMTP host/port are correct
3. Check firewall allows outbound SMTP connections
4. Review server logs for SMTP errors

**Gmail "Less Secure Apps" Error:**
- Don't use "less secure apps" - use App Passwords instead
- Enable 2FA and generate an app-specific password

**Email Goes to Spam:**
- Configure SPF/DKIM records for your domain
- Use a professional email service (SendGrid, Mailgun)
- Avoid localhost/development domains in production

---

## CSV Import/Export

FastCMS allows you to easily import and export data from collections in CSV (Comma-Separated Values) format. This is useful for data migration, backups, bulk editing, and integration with spreadsheet applications like Excel or Google Sheets.

### What is CSV Import/Export?

**CSV Export** downloads all records from a collection into a CSV file that can be opened in Excel, Google Sheets, or any text editor.

**CSV Import** uploads a CSV file to create multiple records in a collection at once. This is much faster than creating records one by one.

### Via Admin Dashboard

The easiest way to use CSV import/export is through the admin dashboard.

#### Exporting Records to CSV

1. Navigate to any collection's records page (e.g., `http://localhost:8000/admin/collections/products/records`)
2. Click the **"Export CSV"** button at the top of the page
3. Your browser will download a CSV file named `{collection_name}_export.csv`
4. Open the file in Excel, Google Sheets, or any text editor

The exported CSV will include:
- System fields: `id`, `created`, `updated`
- All custom fields defined in the collection schema
- Proper formatting for dates, numbers, and boolean values

#### Importing Records from CSV

1. Navigate to the collection's records page
2. Click the **"Import CSV"** button at the top of the page
3. Select your CSV file in the modal dialog
4. Optionally check **"Skip validation"** if you want to import all data as text without type checking
5. Click **"Import"**

The import will show:
- Number of records successfully imported
- Total records in the CSV file
- Any errors that occurred (with row numbers)

**Important Notes:**
- The first row of your CSV must contain field names matching your collection schema
- System fields (`id`, `created`, `updated`) will be ignored if present
- Empty values will be skipped
- Invalid data types will cause errors (unless "Skip validation" is checked)

### Via API

You can also use CSV import/export programmatically through the REST API.

#### Export Records to CSV

```bash
curl -X GET "http://localhost:8000/api/v1/collections/products/records/export/csv" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -o products_export.csv
```

The response will be a CSV file that you can save or process.

**With Filters and Sorting:**

```bash
# Export only active products, sorted by price
curl -X GET "http://localhost:8000/api/v1/collections/products/records/export/csv?filter=active=true&sort=-price" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -o active_products.csv
```

**Query Parameters:**
- `filter` - Filter expression (e.g., `price>=100&&active=true`)
- `sort` - Sort field (prefix with `-` for descending)

**Export Limit:** Maximum 10,000 records per export

#### Import Records from CSV

```bash
curl -X POST "http://localhost:8000/api/v1/collections/products/records/import/csv" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@products.csv"
```

**Response:**
```json
{
  "imported": 95,
  "total": 100,
  "errors": [
    {
      "row": 23,
      "error": "Row 23, field 'price': Cannot convert 'invalid' to number"
    },
    {
      "row": 45,
      "error": "Row 45, field 'email': Invalid email format"
    }
  ]
}
```

**With Skip Validation:**

```bash
# Import all data as text, skip type validation
curl -X POST "http://localhost:8000/api/v1/collections/products/records/import/csv?skip_validation=true" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@products.csv"
```

### CSV Format Examples

#### Simple Example: Products

**CSV File (products.csv):**
```csv
name,price,active
Laptop,999.99,true
Mouse,29.99,true
Keyboard,79.99,false
Monitor,299.99,true
```

**Import Result:** 4 records created

#### Example with Different Field Types

**Collection Schema:**
- `title` (text)
- `quantity` (number)
- `published` (bool)
- `publish_date` (date)
- `tags` (select, multi-select)

**CSV File:**
```csv
title,quantity,published,publish_date,tags
"First Product",100,true,2025-01-15T10:00:00,"[""electronics"", ""sale""]"
"Second Product",50,false,2025-02-01T14:30:00,"[""clothing""]"
```

**Notes:**
- Dates should be in ISO 8601 format
- Boolean values: `true/false`, `1/0`, `yes/no`, `y/n`
- Multi-select and arrays: Use JSON array format `["value1", "value2"]`
- Text with commas: Wrap in double quotes `"text, with comma"`

### Export-Import Workflow (Data Migration)

A common use case is to export data from one collection and import it into another:

**Step 1: Export from source collection**
```bash
curl -X GET "http://localhost:8000/api/v1/collections/old_products/records/export/csv" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -o products_backup.csv
```

**Step 2: Create target collection with matching schema**

Create a new collection with the same field names and types as the source.

**Step 3: Import to target collection**
```bash
curl -X POST "http://localhost:8000/api/v1/collections/new_products/records/import/csv" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@products_backup.csv"
```

**Step 4: Verify import**
```bash
curl -X GET "http://localhost:8000/api/v1/collections/new_products/records" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Handling Large Datasets

For collections with more than 10,000 records:

1. **Export in batches using filters:**
```bash
# Export first 10,000
curl "http://localhost:8000/api/v1/collections/products/records/export/csv?filter=id>0&sort=id"

# Export next batch
curl "http://localhost:8000/api/v1/collections/products/records/export/csv?filter=id>last_id&sort=id"
```

2. **Import in batches:**
   - Split your CSV file into smaller files (e.g., 5,000 records each)
   - Import each file separately
   - Check for errors after each batch

### Troubleshooting

**Import Fails with "Invalid CSV format":**
- Ensure the first row contains field names
- Check that the CSV is properly formatted (use a CSV validator)
- Try opening the file in Excel to verify structure

**Import Partially Succeeds:**
- Check the `errors` array in the response for specific row errors
- Fix the problematic rows in your CSV
- Re-import the corrected CSV (duplicates will be created unless you delete first)

**Boolean Values Not Working:**
- Use accepted formats: `true/false`, `1/0`, `yes/no`, `y/n`
- Values are case-insensitive

**Date Fields Import as Text:**
- Ensure dates are in ISO 8601 format: `2025-01-15T10:00:00`
- Or use simple date format: `2025-01-15`

**Special Characters Cause Issues:**
- Ensure your CSV is UTF-8 encoded
- Wrap text with special characters in double quotes
- Escape double quotes inside text by doubling them: `"He said ""hello"""`

### Access Control

CSV import/export respects collection access control rules:

- **Export**: Requires list permission on the collection
- **Import**: Requires create permission on the collection

If you get a 403 error:
- Check the collection's `list_rule` for export
- Check the collection's `create_rule` for import
- Verify your access token has the necessary permissions

---

## Bulk Operations

FastCMS provides bulk operations to efficiently update or delete multiple records at once. Instead of making individual API calls for each record, you can process up to 100 records in a single request.

### Features

- **Bulk Delete**: Delete multiple records in one operation
- **Bulk Update**: Update the same field(s) across multiple records
- **Partial Success Handling**: Operations continue even if some records fail
- **Detailed Error Reporting**: Get specific error messages for failed operations
- **Access Control**: Respects collection permissions for each record

### Via Admin UI

#### Selecting Records

1. Navigate to any collection's records page
2. Use checkboxes to select records:
   - **Select individual records**: Click the checkbox next to each record
   - **Select all records**: Click the checkbox in the table header
3. Selected count is displayed in the header

#### Bulk Delete

1. Select the records you want to delete
2. Click the **Delete Selected** button
3. Confirm the deletion in the dialog
4. See the operation summary (successful and failed counts)

#### Bulk Update

1. Select the records you want to update
2. Click the **Update Selected** button
3. In the modal:
   - Choose which field to update from the dropdown
   - Enter the new value for that field
   - Click **Update Records**
4. See the operation summary (successful and failed counts)

### Via API

#### Bulk Delete Records

Delete multiple records in a single request.

**Endpoint:** `POST /api/v1/collections/{collection_name}/records/bulk-delete`

**Request Body:**
```json
{
  "record_ids": [
    "record_id_1",
    "record_id_2",
    "record_id_3"
  ]
}
```

**Response:**
```json
{
  "success": 2,
  "failed": 1,
  "errors": [
    {
      "record_id": "record_id_3",
      "error": "Record not found"
    }
  ]
}
```

**Example - cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/collections/posts/records/bulk-delete" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "record_ids": ["abc123", "def456", "ghi789"]
  }'
```

**Example - Python:**
```python
import requests

response = requests.post(
    'http://localhost:8000/api/v1/collections/posts/records/bulk-delete',
    json={
        'record_ids': ['abc123', 'def456', 'ghi789']
    },
    headers={'Authorization': 'Bearer YOUR_TOKEN'}
)

result = response.json()
print(f"Successfully deleted: {result['success']}")
print(f"Failed: {result['failed']}")
if result['errors']:
    print(f"Errors: {result['errors']}")
```

**Example - JavaScript:**
```javascript
const response = await fetch('http://localhost:8000/api/v1/collections/posts/records/bulk-delete', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN'
  },
  body: JSON.stringify({
    record_ids: ['abc123', 'def456', 'ghi789']
  })
});

const result = await response.json();
console.log(`Successfully deleted: ${result.success}`);
console.log(`Failed: ${result.failed}`);
if (result.errors) {
  console.log('Errors:', result.errors);
}
```

#### Bulk Update Records

Update the same field(s) across multiple records.

**Endpoint:** `POST /api/v1/collections/{collection_name}/records/bulk-update`

**Request Body:**
```json
{
  "record_ids": [
    "record_id_1",
    "record_id_2",
    "record_id_3"
  ],
  "data": {
    "status": "published",
    "priority": 1
  }
}
```

**Response:**
```json
{
  "success": 3,
  "failed": 0,
  "errors": null
}
```

**Example - cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/collections/posts/records/bulk-update" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "record_ids": ["abc123", "def456"],
    "data": {
      "status": "published",
      "featured": true
    }
  }'
```

**Example - Python:**
```python
import requests

response = requests.post(
    'http://localhost:8000/api/v1/collections/posts/records/bulk-update',
    json={
        'record_ids': ['abc123', 'def456'],
        'data': {
            'status': 'published',
            'featured': True
        }
    },
    headers={'Authorization': 'Bearer YOUR_TOKEN'}
)

result = response.json()
print(f"Successfully updated: {result['success']}")
print(f"Failed: {result['failed']}")
```

**Example - JavaScript:**
```javascript
const response = await fetch('http://localhost:8000/api/v1/collections/posts/records/bulk-update', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN'
  },
  body: JSON.stringify({
    record_ids: ['abc123', 'def456'],
    data: {
      status: 'published',
      featured: true
    }
  })
});

const result = await response.json();
console.log(`Successfully updated: ${result.success}`);
console.log(`Failed: ${result.failed}`);
```

### Limitations

- **Maximum 100 records per request** - If you need to process more, split into multiple requests
- **At least 1 record required** - You must provide at least one record ID
- **Authentication required** - Bulk operations require a valid access token
- **Sequential processing** - Records are processed one by one, not in parallel

### Error Handling

Bulk operations use **partial success** - if some records fail, the operation continues processing the remaining records.

**Success Response (all succeeded):**
```json
{
  "success": 5,
  "failed": 0,
  "errors": null
}
```

**Partial Success Response:**
```json
{
  "success": 3,
  "failed": 2,
  "errors": [
    {
      "record_id": "abc123",
      "error": "Record not found"
    },
    {
      "record_id": "def456",
      "error": "Insufficient permissions"
    }
  ]
}
```

**Common Error Scenarios:**

**Record Not Found:**
- The record ID doesn't exist in the collection
- The record was already deleted
- **Solution**: Verify the record ID is correct

**Insufficient Permissions:**
- User doesn't have delete/update permission on that record
- Collection access rules deny the operation
- **Solution**: Check collection access rules and user permissions

**Validation Errors:**
- Update data doesn't match field types
- Required fields are missing
- **Solution**: Ensure update data matches collection schema

### Best Practices

**1. Check Results**
Always check the response to see if any operations failed:
```python
result = bulk_delete(record_ids)
if result['failed'] > 0:
    print(f"Warning: {result['failed']} records failed")
    for error in result['errors']:
        print(f"  - {error['record_id']}: {error['error']}")
```

**2. Batch Large Operations**
For more than 100 records, split into batches:
```python
def bulk_delete_all(record_ids, batch_size=100):
    for i in range(0, len(record_ids), batch_size):
        batch = record_ids[i:i + batch_size]
        result = bulk_delete(batch)
        print(f"Batch {i//batch_size + 1}: {result['success']} deleted")
```

**3. Validate Before Bulk Update**
Ensure your update data is valid:
```python
# Get collection schema first
collection = get_collection('posts')

# Validate update data matches schema
update_data = {'status': 'published'}
# Then perform bulk update
bulk_update(record_ids, update_data)
```

**4. Use Transactions for Critical Operations**
For important operations, consider processing records individually with proper error handling instead of bulk operations if you need transactional guarantees.

### Access Control

Bulk operations respect collection access control rules:

- **Bulk Delete**: Requires delete permission on each individual record
- **Bulk Update**: Requires update permission on each individual record

**How It Works:**
- Each record is checked against the collection's access rules
- Records the user doesn't have permission for will fail
- Permitted records will be processed successfully

**Example:**
If a collection has `delete_rule = "@request.auth.id = @record.user_id"`:
- User can only delete their own records
- Bulk delete of 10 records where user owns 7 will succeed for 7, fail for 3

### Performance Considerations

- **API overhead**: One request instead of N requests saves significant overhead
- **Database operations**: Still performs N individual database operations
- **Best for**: 10-100 records at a time
- **Not ideal for**: Thousands of records (consider background jobs instead)

**Estimated Performance:**
- 10 records: ~100-200ms
- 50 records: ~500ms-1s
- 100 records: ~1-2s

---

## Access Control Rules

Every collection has five access control rules that determine who can perform which operations.

### Rule Types

1. **list_rule** - Who can list/search records
2. **view_rule** - Who can view a single record
3. **create_rule** - Who can create new records
4. **update_rule** - Who can update records
5. **delete_rule** - Who can delete records

### Rule Syntax

**Available Variables:**
- `@request.auth.id` - Current logged-in user's ID
- `@request.auth.role` - Current user's role
- `@request.auth.email` - Current user's email
- `@record.field_name` - Value of any field in the record

**Operators:**
- `=` equals
- `!=` not equals
- `&&` AND
- `||` OR

### Common Rule Patterns

#### Public Access
```
list_rule: null
```
Everyone can access (no authentication required).

#### Authenticated Users Only
```
list_rule: "@request.auth.id != ''"
```
Only logged-in users can list records.

#### Admin Only
```
list_rule: "@request.auth.role = 'admin'"
create_rule: "@request.auth.role = 'admin'"
delete_rule: "@request.auth.role = 'admin'"
```
Only admin users can access.

#### Owner Only
```
list_rule: "@request.auth.id = @record.user_id"
update_rule: "@request.auth.id = @record.user_id"
```
Users can only see/edit records they own.

#### Owner OR Admin
```
update_rule: "@request.auth.id = @record.user_id || @request.auth.role = 'admin'"
delete_rule: "@request.auth.id = @record.user_id || @request.auth.role = 'admin'"
```
Record owner OR admin can update/delete.

### Real-World Example: Vendor System

**Scenario:** You want vendors to manage their own products but not see other vendors' products.

**Step 1: Create "vendors" auth collection**
```json
{
  "name": "vendors",
  "type": "auth"
}
```

**Step 2: Create "products" base collection**
```json
{
  "name": "products",
  "type": "base",
  "schema": [
    {
      "name": "vendor_id",
      "type": "text",
      "validation": {"required": true}
    },
    {
      "name": "name",
      "type": "text",
      "validation": {"required": true}
    },
    {
      "name": "price",
      "type": "number",
      "validation": {"required": true}
    }
  ],
  "list_rule": "@request.auth.id = @record.vendor_id",
  "view_rule": "@request.auth.id = @record.vendor_id",
  "create_rule": "@request.auth.id != ''",
  "update_rule": "@request.auth.id = @record.vendor_id",
  "delete_rule": "@request.auth.id = @record.vendor_id || @request.auth.role = 'admin'"
}
```

**Result:**
- Vendors can only see their own products
- Vendors can create new products
- Vendors can only update/delete their own products
- Admins can delete any product

---

## API Usage

All API endpoints are available at `http://localhost:8000/api/v1`

### Collections API

#### List Collections
```bash
GET /api/v1/collections
```

#### Get Collection
```bash
GET /api/v1/collections/{collection_id}
```

#### Create Collection
```bash
POST /api/v1/collections
Authorization: Bearer ADMIN_TOKEN
Content-Type: application/json

{
  "name": "posts",
  "type": "base",
  "schema": [...]
}
```

#### Update Collection
```bash
PUT /api/v1/collections/{collection_id}
Authorization: Bearer ADMIN_TOKEN
```

#### Delete Collection
```bash
DELETE /api/v1/collections/{collection_id}
Authorization: Bearer ADMIN_TOKEN
```

### Records API

#### List Records
```bash
GET /api/v1/collections/{collection_name}/records
```

**Query Parameters:**
- `page` - Page number (default: 1)
- `per_page` - Records per page (default: 30, max: 100)
- `sort` - Sort field (prefix with `-` for descending)
- `filter` - Filter expression
- `search` - Search term for full-text search across text fields

**Example:**
```bash
GET /api/v1/collections/products/records?page=1&per_page=20&sort=-created
```

#### Search Records

Full-text search allows you to search across all text, editor, email, and URL fields in a collection using a single search term.

**Endpoint:**
```bash
GET /api/v1/collections/{collection_name}/records?search={query}
```

**How It Works:**
- Searches across all text-based fields (text, editor, email, url)
- Uses case-insensitive partial matching (LIKE operator)
- Results match if the search term appears anywhere in any searchable field
- Can be combined with filters and sorting

**Basic Search Example:**
```bash
GET /api/v1/collections/posts/records?search=fastcms
```

**Search with Filters:**
```bash
GET /api/v1/collections/posts/records?search=fastcms&filter=status=published
```

**Search with Sorting:**
```bash
GET /api/v1/collections/posts/records?search=fastcms&sort=-created
```

**Searchable Field Types:**
- `text` - Standard text fields
- `editor` - Rich text editor content
- `email` - Email address fields
- `url` - URL fields

**Non-Searchable Field Types:**
- `number`, `bool`, `date`, `select`, `relation`, `file`, `json`

#### Get Record
```bash
GET /api/v1/collections/{collection_name}/records/{record_id}
```

#### Create Record
```bash
POST /api/v1/collections/{collection_name}/records
Authorization: Bearer USER_TOKEN
Content-Type: application/json

{
  "data": {
    "title": "Product Name",
    "price": 99.99
  }
}
```

#### Update Record
```bash
PATCH /api/v1/collections/{collection_name}/records/{record_id}
Authorization: Bearer USER_TOKEN
Content-Type: application/json

{
  "data": {
    "price": 89.99
  }
}
```

#### Delete Record
```bash
DELETE /api/v1/collections/{collection_name}/records/{record_id}
Authorization: Bearer USER_TOKEN
```

### Authentication Headers

Include the access token in the Authorization header for protected endpoints:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Field Types

### Text Field
```json
{
  "name": "title",
  "type": "text",
  "validation": {
    "required": true,
    "min_length": 3,
    "max_length": 100
  }
}
```

### Number Field
```json
{
  "name": "price",
  "type": "number",
  "validation": {
    "required": true,
    "min": 0
  }
}
```

### Boolean Field
```json
{
  "name": "published",
  "type": "bool",
  "validation": {
    "required": false
  }
}
```

### Email Field
```json
{
  "name": "contact_email",
  "type": "email",
  "validation": {
    "required": true
  }
}
```

### URL Field
```json
{
  "name": "website",
  "type": "url",
  "validation": {
    "required": false
  }
}
```

### Date Field
```json
{
  "name": "publish_date",
  "type": "date",
  "validation": {
    "required": false
  }
}
```

### Select Field
```json
{
  "name": "status",
  "type": "select",
  "select": {
    "values": ["draft", "published", "archived"],
    "max_select": 1
  },
  "validation": {
    "required": true
  }
}
```

### Relation Field
```json
{
  "name": "category",
  "type": "relation",
  "relation": {
    "collection_id": "categories_collection_id",
    "type": "many-to-one",
    "cascade_delete": false,
    "display_fields": ["id", "name"]
  },
  "validation": {
    "required": false
  }
}
```

### File Field
```json
{
  "name": "image",
  "type": "file",
  "file": {
    "max_files": 1,
    "max_size": 5242880,
    "mime_types": ["image/jpeg", "image/png", "image/gif"],
    "thumbs": ["100x100", "500x500"]
  },
  "validation": {
    "required": false
  }
}
```

### JSON Field
```json
{
  "name": "metadata",
  "type": "json",
  "validation": {
    "required": false
  }
}
```

### Editor Field (Rich Text)
```json
{
  "name": "content",
  "type": "editor",
  "validation": {
    "required": false
  }
}
```

---

## Interactive API Documentation

FastCMS provides interactive API documentation powered by Swagger UI.

Access it at: `http://localhost:8000/docs`

This interface allows you to:
- Browse all available endpoints
- Test API calls directly from the browser
- View request/response schemas
- Authenticate and test protected endpoints

---

## Database

FastCMS uses SQLite with WAL (Write-Ahead Logging) mode for better concurrency.

**Database Location:** `data/app.db`

**Important Notes:**
- All collections are stored as dynamic tables
- The `collections` table stores metadata and schemas
- The `users` table is for admin authentication only
- Auth collections create their own tables with authentication fields

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Application
ENV=development
DEBUG=true

# Database
DATABASE_URL=sqlite:///./data/app.db

# Security
SECRET_KEY=your-secret-key-here-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

---

## Best Practices

### Security

1. Always use strong SECRET_KEY in production
2. Use HTTPS in production
3. Set appropriate access control rules on collections
4. Validate user input on the client side
5. Use refresh tokens for long-lived sessions

### Performance

1. Add indexes to frequently queried fields
2. Use pagination for large datasets
3. Set appropriate cache TTL for view collections
4. Use view collections for complex queries instead of client-side joins

### Data Modeling

1. Use auth collections for any user type requiring authentication
2. Use base collections for standard data
3. Use view collections for reports and aggregations
4. Use relation fields to link collections
5. Set cascade_delete appropriately on relations

---

## Troubleshooting

### Collection Creation Fails

**Issue:** "An invalid form control with name='' is not focusable"

**Solution:** This occurs when hidden required fields (relation/view fields) are present. Ensure you're creating the correct collection type and all visible required fields are filled.

### Authentication Fails

**Issue:** 401 Unauthorized

**Solution:**
- Ensure access token is included in Authorization header
- Check if token has expired (access tokens expire in 15 minutes by default)
- Use refresh token to get a new access token

### Access Denied to Records

**Issue:** Cannot view/edit records despite being authenticated

**Solution:**
- Check the access control rules on the collection
- Ensure your user meets the rule criteria
- Verify the record data matches the rules (e.g., user_id field)

---

## Support

For issues and questions:
- GitHub: https://github.com/yourusername/fastCMS
- Issues: https://github.com/yourusername/fastCMS/issues

---

## Webhooks

FastCMS includes a powerful webhook system that allows you to subscribe to events and receive HTTP callbacks when records are created, updated, or deleted in your collections.

### What are Webhooks?

Webhooks are HTTP POST requests sent to a URL you specify whenever certain events occur. This allows external systems to react to changes in your FastCMS data in real-time.

**Use Cases:**
- Send notifications when new users register
- Sync data to external systems
- Trigger workflows in other applications
- Update search indexes when content changes
- Send emails or SMS notifications
- Log events to analytics platforms

### Creating a Webhook

**Endpoint:** `POST /api/v1/webhooks`

**Request Body:**
```json
{
  "url": "https://your-server.com/webhook",
  "collection_name": "posts",
  "events": ["create", "update", "delete"],
  "secret": "your-webhook-secret",
  "retry_count": 3
}
```

**Parameters:**
- `url` (required) - The endpoint that will receive webhook POSTs
- `collection_name` (required) - Collection to watch for events
- `events` (required) - Array of events to subscribe to: `["create", "update", "delete"]`
- `secret` (optional) - Secret key for HMAC signature verification
- `retry_count` (optional) - Number of retry attempts on failure (default: 3, max: 5)

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/webhooks" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "url": "https://myapp.com/api/webhook",
    "collection_name": "posts",
    "events": ["create", "update"],
    "secret": "myWebhookSecret123",
    "retry_count": 3
  }'
```

**Response:**
```json
{
  "id": "webhook-uuid",
  "url": "https://myapp.com/api/webhook",
  "collection_name": "posts",
  "events": ["create", "update"],
  "active": true,
  "retry_count": 3,
  "created": "2025-01-15T10:00:00"
}
```

### Webhook Payload

When an event occurs, FastCMS sends a POST request to your webhook URL with this payload:

```json
{
  "event": "create",
  "collection": "posts",
  "record_id": "record-uuid",
  "data": {
    "id": "record-uuid",
    "title": "New Post",
    "content": "Post content...",
    "created": "2025-01-15T10:00:00",
    "updated": "2025-01-15T10:00:00"
  },
  "timestamp": "2025-01-15T10:00:00"
}
```

**Payload Fields:**
- `event` - Event type: `create`, `update`, or `delete`
- `collection` - Collection name where the event occurred
- `record_id` - ID of the affected record
- `data` - Full record data (empty for delete events)
- `timestamp` - When the event occurred (ISO 8601)

### Webhook Security

**HMAC Signature Verification:**

If you provided a `secret` when creating the webhook, FastCMS will sign each request with HMAC-SHA256 and include it in the `X-Webhook-Signature` header.

**Verifying the signature (Python example):**
```python
import hmac
import hashlib

def verify_webhook(request_body, signature, secret):
    expected = hmac.new(
        secret.encode(),
        request_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

# In your webhook handler:
signature = request.headers.get('X-Webhook-Signature')
if not verify_webhook(request.body, signature, 'myWebhookSecret123'):
    return 401  # Unauthorized
```

**Verifying the signature (Node.js example):**
```javascript
const crypto = require('crypto');

function verifyWebhook(body, signature, secret) {
  const expected = crypto
    .createHmac('sha256', secret)
    .update(body)
    .digest('hex');
  return crypto.timingSafeEqual(
    Buffer.from(expected),
    Buffer.from(signature)
  );
}

// In your webhook handler:
const signature = req.headers['x-webhook-signature'];
if (!verifyWebhook(req.body, signature, 'myWebhookSecret123')) {
  return res.status(401).send('Unauthorized');
}
```

### Managing Webhooks

#### List All Webhooks
```bash
GET /api/v1/webhooks
```

**Filter by collection:**
```bash
GET /api/v1/webhooks?collection_name=posts
```

**Example:**
```bash
curl "http://localhost:8000/api/v1/webhooks?collection_name=posts" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response:**
```json
{
  "items": [
    {
      "id": "webhook-1",
      "url": "https://myapp.com/webhook",
      "collection_name": "posts",
      "events": ["create", "update"],
      "active": true,
      "retry_count": 3,
      "created": "2025-01-15T10:00:00"
    }
  ],
  "total": 1
}
```

#### Get Single Webhook
```bash
GET /api/v1/webhooks/{webhook_id}
```

#### Update Webhook
```bash
PATCH /api/v1/webhooks/{webhook_id}
```

**Request Body (all fields optional):**
```json
{
  "url": "https://new-url.com/webhook",
  "events": ["create"],
  "active": false,
  "secret": "newSecret",
  "retry_count": 5
}
```

**Example - Disable a webhook:**
```bash
curl -X PATCH "http://localhost:8000/api/v1/webhooks/webhook-uuid" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"active": false}'
```

#### Delete Webhook
```bash
DELETE /api/v1/webhooks/{webhook_id}
```

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/webhooks/webhook-uuid" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Webhook Retry Logic

When your webhook endpoint fails or returns a non-2xx status code, FastCMS will automatically retry:

**Retry Schedule:**
- 1st retry: After 1 minute
- 2nd retry: After 5 minutes
- 3rd retry: After 15 minutes
- 4th retry: After 30 minutes
- 5th retry: After 1 hour

**After all retries fail:**
- Webhook is automatically disabled (`active: false`)
- You must re-enable it manually after fixing the issue

### Best Practices

1. **Respond Quickly**: Return 200 OK immediately, process the webhook asynchronously
2. **Verify Signatures**: Always verify HMAC signatures in production
3. **Be Idempotent**: Handle duplicate webhook deliveries gracefully
4. **Use HTTPS**: Only use HTTPS URLs for security
5. **Monitor Failures**: Check webhook status regularly, re-enable if disabled

### Troubleshooting

**Webhook not firing:**
- Check that the webhook is `active: true`
- Verify the collection name is correct
- Ensure events array includes the event type
- Check that your URL is accessible from the internet

**Webhook disabled automatically:**
- All retry attempts failed
- Check your endpoint logs for errors
- Fix the issue and re-enable: `PATCH /webhooks/{id}` with `{"active": true}`

**Signature verification fails:**
- Ensure you're using the same secret
- Verify you're hashing the raw request body
- Check that your HMAC implementation is correct

---

## Real-time Features

FastCMS provides real-time updates over a **WebSocket** connection. Subscribe to
one or more collections and receive an event whenever a record is created,
updated, or deleted. (There is no SSE / `EventSource` endpoint — real-time is
WebSocket-only.)

### Endpoint

```
ws://localhost:8000/api/v1/ws/realtime
ws://localhost:8000/api/v1/ws/realtime?token=YOUR_JWT_TOKEN
```

Authenticate by passing a JWT in the `token` query parameter on connect, or by
sending an `auth` message after the connection opens.

### Client → server messages (JSON)

| Action | Example |
|--------|---------|
| Subscribe to a collection | `{"action": "subscribe", "collection": "posts"}` |
| Subscribe with a filter | `{"action": "subscribe", "collection": "posts", "filter": {"published": true}}` |
| Subscribe to all collections | `{"action": "subscribe", "collection": "*"}` |
| Unsubscribe | `{"action": "unsubscribe", "collection": "posts"}` |
| Authenticate | `{"action": "auth", "token": "YOUR_JWT"}` |
| Heartbeat reply | `{"action": "pong"}` |

### Server → client messages (JSON)

| Type | Description |
|------|-------------|
| `connected` | Connection established |
| `authenticated` | Authentication succeeded |
| `subscribed` | Subscription confirmed |
| `unsubscribed` | Unsubscription confirmed |
| `event` | A record was created / updated / deleted in a subscribed collection |
| `ping` | Server heartbeat — reply with `{"action": "pong"}` |
| `error` | Error message |
| `presence` | A user joined or left |

### Browser example

```javascript
const token = localStorage.getItem("access_token");
const ws = new WebSocket(
  `ws://localhost:8000/api/v1/ws/realtime?token=${token}`
);

ws.onopen = () => {
  // Subscribe once connected
  ws.send(JSON.stringify({ action: "subscribe", collection: "posts" }));
};

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  switch (msg.type) {
    case "event":
      console.log("Realtime event:", msg.data);
      break;
    case "ping":
      ws.send(JSON.stringify({ action: "pong" })); // keep the connection alive
      break;
  }
};

ws.onclose = () => {
  // Reconnect with exponential backoff as needed
};
```

### Notes

- Each WebSocket connection is lightweight but persistent; reconnect with
  backoff if it drops.
- For multi-server deployments, enable Redis (`REDIS_ENABLED=true`) so events
  fan out across all instances via pub/sub.
- Some proxies buffer or close idle connections — configure them to allow
  WebSocket upgrades and long-lived connections.

## Advanced Relations

FastCMS supports advanced relationship types beyond basic one-to-many references. The relation schema includes support for many-to-many, polymorphic, one-to-one, and nested relations with configurable cascade actions.

### Overview

**Current Status:**
- ✅ Schema supports all advanced relation types
- ✅ API accepts and validates advanced relation configurations
- ⏳ Runtime behavior (junction tables, recursive loading, cascades) is not yet implemented
- ⏳ Frontend UI for configuring advanced relations is pending

**Available Relation Types:**
- `one-to-many` - One record can have many related records (default)
- `many-to-one` - Many records reference one parent record
- `many-to-many` - Records can have multiple related records in both directions
- `one-to-one` - One record relates to exactly one other record
- `polymorphic` - Relate to records from multiple different collections

**Cascade Actions:**
- `restrict` - Prevent deletion if related records exist (default)
- `cascade` - Delete related records automatically
- `set_null` - Set foreign key to NULL when parent is deleted
- `no_action` - Do nothing (standard SQL behavior)

### Relation Schema

When defining a relation field, use the `RelationOptions` configuration:

```json
{
  "name": "author",
  "type": "relation",
  "relation": {
    "collection_id": "users",
    "type": "many-to-one",
    "cascade_delete": "restrict",
    "display_fields": ["name", "email"],
    "max_depth": 2
  }
}
```

**RelationOptions Fields:**

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `collection_id` | string | Target collection ID (for single collection) | Required |
| `collection_ids` | array | Target collection IDs (for polymorphic) | null |
| `type` | string | Relationship type | `one-to-many` |
| `cascade_delete` | string | Action on parent deletion | `restrict` |
| `display_fields` | array | Fields to show in relation | `["id"]` |
| `max_depth` | integer | Nested loading depth (0-5) | 1 |
| `junction_table` | string | Junction table for many-to-many | null |
| `junction_field` | string | Field in junction referencing this collection | null |
| `target_field` | string | Field in junction referencing target | null |
| `polymorphic_type_field` | string | Field storing collection type | null |

### One-to-Many Relations

Default relation type. One parent record can have multiple child records.

**Example:** Posts collection with multiple comments

```bash
# Create comments collection with relation to posts
curl -X POST "http://localhost:8000/api/v1/collections" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "comments",
    "type": "base",
    "schema": {
      "fields": [
        {
          "name": "content",
          "type": "text"
        },
        {
          "name": "post",
          "type": "relation",
          "relation": {
            "collection_id": "posts",
            "type": "one-to-many",
            "cascade_delete": "cascade",
            "display_fields": ["title"]
          }
        }
      ]
    }
  }'
```

### Many-to-One Relations

Multiple records reference a single parent record. Opposite perspective of one-to-many.

**Example:** Multiple posts by one author

```json
{
  "name": "author",
  "type": "relation",
  "relation": {
    "collection_id": "users",
    "type": "many-to-one",
    "cascade_delete": "set_null",
    "display_fields": ["name", "email"]
  }
}
```

### Many-to-Many Relations

Records can relate to multiple records in both directions. Requires a junction table.

**Example:** Posts with multiple tags, tags with multiple posts

```bash
curl -X POST "http://localhost:8000/api/v1/collections" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "posts",
    "type": "base",
    "schema": {
      "fields": [
        {
          "name": "title",
          "type": "text"
        },
        {
          "name": "tags",
          "type": "relation",
          "relation": {
            "collection_id": "tags",
            "type": "many-to-many",
            "junction_table": "posts_tags",
            "junction_field": "post_id",
            "target_field": "tag_id",
            "display_fields": ["name"]
          }
        }
      ]
    }
  }'
```

**Note:** Runtime support for automatic junction table creation is pending.

### One-to-One Relations

Each record relates to exactly one record in the target collection.

**Example:** User profile

```json
{
  "name": "profile",
  "type": "relation",
  "relation": {
    "collection_id": "user_profiles",
    "type": "one-to-one",
    "cascade_delete": "cascade",
    "display_fields": ["bio", "avatar"]
  }
}
```

### Polymorphic Relations

Relate to records from multiple different collections. Useful for comments, attachments, etc.

**Example:** Comments that can belong to posts OR events

```bash
curl -X POST "http://localhost:8000/api/v1/collections" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "comments",
    "type": "base",
    "schema": {
      "fields": [
        {
          "name": "content",
          "type": "text"
        },
        {
          "name": "commentable",
          "type": "relation",
          "relation": {
            "collection_ids": ["posts", "events"],
            "type": "polymorphic",
            "polymorphic_type_field": "commentable_type",
            "display_fields": ["title"]
          }
        }
      ]
    }
  }'
```

**Storage Pattern:**
- `commentable` field stores the record ID
- `commentable_type` field stores the collection name ("posts" or "events")

**Note:** Runtime support for polymorphic queries is pending.

### Nested Relations (Expansion Depth)

Control how deeply related records are loaded when expanding relations.

**Example:** Load author with their company and company's location

```json
{
  "name": "author",
  "type": "relation",
  "relation": {
    "collection_id": "users",
    "type": "many-to-one",
    "max_depth": 3,
    "display_fields": ["name", "company"]
  }
}
```

**max_depth Values:**
- `0` - No expansion (only ID)
- `1` - Load immediate relation (default)
- `2` - Load relation and its relations
- `3-5` - Deeper nesting (use cautiously for performance)

**Note:** Runtime support for recursive loading beyond depth 1 is pending.

### Cascade Actions

Control what happens to related records when a parent is deleted.

#### CASCADE - Delete Related Records

```json
{
  "name": "author",
  "type": "relation",
  "relation": {
    "collection_id": "users",
    "cascade_delete": "cascade"
  }
}
```

**Behavior:** When a user is deleted, all their posts are automatically deleted.

#### SET_NULL - Clear Foreign Key

```json
{
  "name": "author",
  "type": "relation",
  "relation": {
    "collection_id": "users",
    "cascade_delete": "set_null"
  }
}
```

**Behavior:** When a user is deleted, posts' `author` field is set to NULL.

#### RESTRICT - Prevent Deletion

```json
{
  "name": "author",
  "type": "relation",
  "relation": {
    "collection_id": "users",
    "cascade_delete": "restrict"
  }
}
```

**Behavior:** Cannot delete user if they have posts. Returns error.

#### NO_ACTION - Do Nothing

```json
{
  "name": "author",
  "type": "relation",
  "relation": {
    "collection_id": "users",
    "cascade_delete": "no_action"
  }
}
```

**Behavior:** Standard SQL behavior, may leave orphaned records.

**Note:** Runtime cascade enforcement is pending.

### Current Limitations

**What Works:**
- ✅ Schema validation for all relation types
- ✅ API accepts advanced relation configurations
- ✅ Basic one-to-many expansion (existing functionality)

**What's Pending:**
- ⏳ Automatic junction table creation for many-to-many
- ⏳ Polymorphic relation querying
- ⏳ Recursive loading beyond depth 1
- ⏳ Cascade action enforcement
- ⏳ Frontend UI for relation configuration

### Best Practices

**1. Choose the Right Relation Type**

Use `many-to-one` for most cases:
```json
// Posts -> Author (many posts, one author each)
{"type": "many-to-one", "collection_id": "users"}
```

Use `many-to-many` for bidirectional multi-relations:
```json
// Posts <-> Tags
{"type": "many-to-many", "junction_table": "posts_tags"}
```

**2. Set Appropriate Cascade Actions**

For dependent data:
```json
// Comments should be deleted with their post
{"cascade_delete": "cascade"}
```

For independent data:
```json
// Posts shouldn't be deleted when author is deleted
{"cascade_delete": "set_null"}
```

For strict referential integrity:
```json
// Can't delete if dependencies exist
{"cascade_delete": "restrict"}
```

**3. Limit Expansion Depth**

```json
// Good: Limited depth for performance
{"max_depth": 2}

// Risky: Deep nesting can cause slow queries
{"max_depth": 5}
```

**4. Choose Display Fields Wisely**

```json
// Good: Useful identifying fields
{"display_fields": ["name", "email"]}

// Bad: Too many fields
{"display_fields": ["id", "name", "email", "bio", "created", "updated"]}
```

### Future Implementation Plan

When runtime support is added, the following will be implemented:

**Phase 1: Junction Tables**
- Automatic creation/management of junction tables
- Many-to-many record insertion/deletion
- Bi-directional relation queries

**Phase 2: Polymorphic Relations**
- Multi-collection query resolution
- Type-safe polymorphic fetching
- Eager loading for polymorphic relations

**Phase 3: Nested Loading**
- Recursive relation expansion
- Cycle detection and prevention
- Optimized N+1 query handling

**Phase 4: Cascade Actions**
- Database-level foreign key constraints
- Cascade delete implementation
- Transaction-safe cascade operations

### Migration Guide

When runtime support is added, existing schemas will continue to work. No migration required for:
- Existing one-to-many relations
- Basic relation expansion (depth 1)

You'll be able to upgrade relations by updating the schema:

```bash
# Upgrade existing relation to many-to-many
curl -X PATCH "http://localhost:8000/api/v1/collections/posts" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "schema": {
      "fields": [
        {
          "name": "tags",
          "type": "relation",
          "relation": {
            "type": "many-to-many",
            "junction_table": "posts_tags"
          }
        }
      ]
    }
  }'
```

---

## Backup & Restore

FastCMS provides database backup and restore functionality to protect your data and enable disaster recovery.

### What Gets Backed Up?

A backup includes:
- All collections and their schemas
- All records across all collections
- User accounts (admin users)
- System settings
- Webhooks and other configurations

**Not included in backups:**
- Uploaded files (store separately, e.g., S3)
- Application logs
- Temporary data

### Creating a Backup

**Endpoint:** `POST /api/v1/backups`

**Requires:** Admin authentication

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/backups" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Response:**
```json
{
  "id": "backup-uuid",
  "filename": "backup_2025-01-15_100000.db",
  "size_bytes": 1048576,
  "status": "completed",
  "created": "2025-01-15T10:00:00"
}
```

**Backup Process:**
1. Creates a snapshot of the entire SQLite database
2. Stores the backup file in the `data/backups/` directory
3. Returns backup metadata including file size and creation time

### Listing Backups

**Endpoint:** `GET /api/v1/backups`

**Query Parameters:**
- `limit` - Number of backups to return (default: 50, max: 100)
- `offset` - Skip this many backups (for pagination)

**Example:**
```bash
curl "http://localhost:8000/api/v1/backups?limit=10&offset=0" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Response:**
```json
{
  "items": [
    {
      "id": "backup-1",
      "filename": "backup_2025-01-15_100000.db",
      "size_bytes": 1048576,
      "status": "completed",
      "location": "data/backups/backup_2025-01-15_100000.db",
      "created": "2025-01-15T10:00:00"
    },
    {
      "id": "backup-2",
      "filename": "backup_2025-01-14_100000.db",
      "size_bytes": 1024000,
      "status": "completed",
      "location": "data/backups/backup_2025-01-14_100000.db",
      "created": "2025-01-14T10:00:00"
    }
  ],
  "limit": 10,
  "offset": 0
}
```

### Restoring from a Backup

**WARNING:** Restoring will **overwrite all current data**. This operation cannot be undone.

**Endpoint:** `POST /api/v1/backups/{backup_id}/restore`

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/backups/backup-uuid/restore" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Response:**
```json
{
  "success": true,
  "message": "Backup restored successfully"
}
```

**Restore Process:**
1. Validates the backup file exists
2. Stops all database operations
3. Replaces the current database with the backup
4. Restarts the database connection
5. Verifies data integrity

**After restore:**
- All data returns to the state at backup time
- Any changes made after the backup are lost
- The application may need to be restarted for full effect

### Deleting a Backup

**Endpoint:** `DELETE /api/v1/backups/{backup_id}`

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/backups/backup-uuid" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Response:**
```json
{
  "deleted": true
}
```

### Backup Storage

**Default Location:** `data/backups/`

**Filename Format:** `backup_YYYY-MM-DD_HHMMSS.db`

**Storage Recommendations:**
1. **Keep multiple backups**: Don't delete old backups immediately
2. **Off-site storage**: Copy backups to cloud storage (S3, Google Cloud Storage)
3. **Test restores**: Periodically test restoration to verify backup integrity
4. **Automate backups**: Schedule regular backups (daily/weekly)

### Automated Backups

While manual backups are available via API, you can automate them using cron or a task scheduler:

**Linux/Mac (cron):**
```bash
# Add to crontab: Daily backup at 2 AM
0 2 * * * curl -X POST http://localhost:8000/api/v1/backups \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Python script for automated backups:**
```python
import requests
import schedule
import time

def create_backup():
    response = requests.post(
        'http://localhost:8000/api/v1/backups',
        headers={'Authorization': 'Bearer YOUR_ADMIN_TOKEN'}
    )
    if response.status_code == 200:
        print(f"Backup created: {response.json()['filename']}")
    else:
        print(f"Backup failed: {response.text}")

# Run daily at 2 AM
schedule.every().day.at("02:00").do(create_backup)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Disaster Recovery

**Scenario: Complete data loss**

1. Stop the FastCMS application
2. Locate your most recent backup file
3. Replace `data/app.db` with the backup file:
   ```bash
   cp data/backups/backup_2025-01-15_100000.db data/app.db
   ```
4. Restart FastCMS
5. Verify all data is restored

**Scenario: Accidental deletion**

1. Create a backup of current state (just in case)
2. Identify the backup before the deletion occurred
3. Use the restore API endpoint
4. Verify the deleted data is back

### Best Practices

1. **Regular Schedule**: Backup daily or before major changes
2. **Retention Policy**: Keep at least 7 daily, 4 weekly, 12 monthly backups
3. **Test Restores**: Monthly test restore to verify backups work
4. **Off-site Storage**: Don't rely only on local backups
5. **Monitor Space**: Ensure adequate disk space for backups

### Backup Size Management

Backups can grow large over time. To manage size:

1. **Delete old backups** programmatically:
   ```bash
   # List backups older than 30 days and delete them
   curl "http://localhost:8000/api/v1/backups" \
     -H "Authorization: Bearer ADMIN_TOKEN" | \
     jq -r '.items[] | select(.created < "2024-12-15") | .id' | \
     xargs -I {} curl -X DELETE \
       "http://localhost:8000/api/v1/backups/{}" \
       -H "Authorization: Bearer ADMIN_TOKEN"
   ```

2. **Compress backups**:
   ```bash
   gzip data/backups/backup_2025-01-15_100000.db
   ```

3. **Move to cold storage**: Archive old backups to S3 Glacier or equivalent

---

## System Settings

FastCMS includes a settings system for storing application configuration values in the database.

### What are System Settings?

Settings are key-value pairs stored in the database that control application behavior. Unlike environment variables, settings can be changed at runtime without restarting the application.

**Use Cases:**
- Feature flags
- Application-wide configuration
- User preferences
- API keys for third-party services
- Rate limits
- Default values

### Setting Categories

Settings are organized into categories:
- `app` - General application settings
- `email` - Email/SMTP configuration
- `security` - Security and authentication settings
- `storage` - File storage configuration
- `custom` - Your custom settings

### Get All Settings

**Endpoint:** `GET /api/v1/settings`

**Requires:** Admin authentication

**Example:**
```bash
curl "http://localhost:8000/api/v1/settings" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Response:**
```json
[
  {
    "id": "setting-1",
    "key": "app_name",
    "value": "My FastCMS",
    "category": "app",
    "description": "Application name"
  },
  {
    "id": "setting-2",
    "key": "max_upload_size",
    "value": 10485760,
    "category": "storage",
    "description": "Maximum file upload size in bytes"
  }
]
```

### Get Settings by Category

**Endpoint:** `GET /api/v1/settings/{category}`

**Example:**
```bash
curl "http://localhost:8000/api/v1/settings/email" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Response:**
```json
[
  {
    "id": "setting-3",
    "key": "smtp_host",
    "value": "smtp.gmail.com",
    "category": "email",
    "description": "SMTP server host"
  },
  {
    "id": "setting-4",
    "key": "smtp_port",
    "value": 587,
    "category": "email",
    "description": "SMTP server port"
  }
]
```

### Update a Setting

**Endpoint:** `POST /api/v1/settings`

**Request Body:**
```json
{
  "key": "app_name",
  "value": "My FastCMS",
  "category": "app",
  "description": "Application name displayed in admin"
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/settings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -d '{
    "key": "maintenance_mode",
    "value": false,
    "category": "app",
    "description": "Enable maintenance mode"
  }'
```

**Response:**
```json
{
  "id": "setting-uuid",
  "key": "maintenance_mode",
  "value": false,
  "category": "app"
}
```

### Delete a Setting

**Endpoint:** `DELETE /api/v1/settings/{key}`

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/settings/old_setting" \
  -H "Authorization: Bearer ADMIN_TOKEN"
```

**Response:**
```json
{
  "deleted": true
}
```

### Common Settings Examples

**Application Settings:**
```json
{
  "key": "app_name",
  "value": "My FastCMS",
  "category": "app"
}
```

**Feature Flags:**
```json
{
  "key": "enable_ai_features",
  "value": true,
  "category": "app"
}
```

**Rate Limiting:**
```json
{
  "key": "api_rate_limit",
  "value": 100,
  "category": "security",
  "description": "Max API requests per minute"
}
```

**File Upload Limits:**
```json
{
  "key": "max_file_size",
  "value": 10485760,
  "category": "storage",
  "description": "Maximum file size in bytes (10MB)"
}
```

### Using Settings in Code

Settings are primarily managed via the API, but you can also access them programmatically in your application code.

**Python example:**
```python
from app.services.settings_service import SettingsService

# Get a setting
settings = SettingsService(db)
app_name = await settings.get("app_name", default="FastCMS")

# Set a setting
await settings.set(
    key="maintenance_mode",
    value=True,
    category="app",
    description="Site maintenance mode"
)
```

### Best Practices

1. **Use Categories**: Organize related settings together
2. **Add Descriptions**: Always include helpful descriptions
3. **Set Defaults**: Have sensible defaults in your code
4. **Validate Values**: Check setting values before using them
5. **Document Settings**: Keep a list of all available settings

---

## OAuth Authentication

FastCMS supports OAuth authentication for popular providers, allowing users to sign in with their existing accounts from Google, GitHub, or Microsoft.

### Supported Providers

- **Google** - Google account authentication
- **GitHub** - GitHub account authentication
- **Microsoft** - Microsoft account authentication

### Configuration

OAuth providers are configured via environment variables in your `.env` file:

**Google OAuth:**
```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/oauth/google/callback
```

**GitHub OAuth:**
```env
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_REDIRECT_URI=http://localhost:8000/api/v1/oauth/github/callback
```

**Microsoft OAuth:**
```env
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret
MICROSOFT_REDIRECT_URI=http://localhost:8000/api/v1/oauth/microsoft/callback
```

### Setting Up OAuth Providers

#### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Navigate to "APIs & Services" > "Credentials"
4. Click "Create Credentials" > "OAuth 2.0 Client ID"
5. Select "Web application"
6. Add authorized redirect URI: `http://localhost:8000/api/v1/oauth/google/callback`
7. Copy the Client ID and Client Secret to your `.env` file

#### GitHub OAuth

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "New OAuth App"
3. Fill in:
   - Application name: Your app name
   - Homepage URL: `http://localhost:8000`
   - Authorization callback URL: `http://localhost:8000/api/v1/oauth/github/callback`
4. Copy the Client ID and Client Secret to your `.env` file

#### Microsoft OAuth

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to "Azure Active Directory" > "App registrations"
3. Click "New registration"
4. Fill in:
   - Name: Your app name
   - Redirect URI: `http://localhost:8000/api/v1/oauth/microsoft/callback`
5. Copy the Application (client) ID
6. Create a new client secret under "Certificates & secrets"
7. Copy both values to your `.env` file

### OAuth Flow

**1. Initiate OAuth Login**

Redirect users to the OAuth authorization URL:

```bash
GET /api/v1/oauth/{provider}/login
```

**Example:**
```
http://localhost:8000/api/v1/oauth/google/login
http://localhost:8000/api/v1/oauth/github/login
http://localhost:8000/api/v1/oauth/microsoft/login
```

**2. User Authorization**

The user is redirected to the provider's login page where they authorize your application.

**3. Callback**

After authorization, the provider redirects back to:
```
/api/v1/oauth/{provider}/callback?code=AUTHORIZATION_CODE
```

FastCMS automatically:
- Exchanges the code for an access token
- Fetches the user's profile information
- Creates or updates the user account
- Returns JWT tokens for your application

**4. Response**

```json
{
  "user": {
    "id": "user-uuid",
    "email": "user@gmail.com",
    "name": "John Doe",
    "verified": true,
    "oauth_provider": "google"
  },
  "token": {
    "access_token": "eyJhbGc...",
    "refresh_token": "eyJhbGc...",
    "token_type": "bearer",
    "expires_in": 86400
  },
  "message": null,
  "requires_2fa": false
}
```

### Using OAuth in Your Frontend

**HTML Example:**
```html
<a href="http://localhost:8000/api/v1/oauth/google/login">
  <button>Sign in with Google</button>
</a>

<a href="http://localhost:8000/api/v1/oauth/github/login">
  <button>Sign in with GitHub</button>
</a>
```

**JavaScript Example:**
```javascript
// Redirect to OAuth login
function loginWithGoogle() {
  window.location.href = 'http://localhost:8000/api/v1/oauth/google/login';
}

// Handle callback (if handling manually)
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
if (code) {
  // Exchange code for tokens
  fetch(`http://localhost:8000/api/v1/oauth/google/callback?code=${code}`)
    .then(res => res.json())
    .then(data => {
      // Store tokens
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      // Redirect to dashboard
      window.location.href = '/dashboard';
    });
}
```

### OAuth with Auth Collections

OAuth works with both the main user system and auth collections (e.g., customers, vendors).

**Collection-specific OAuth:**
```bash
GET /api/v1/oauth/{provider}/login?collection=customers
```

This allows customers to sign in with OAuth while keeping them separate from admin users.

### Account Linking

If a user signs in with OAuth and an account with that email already exists:
- **Email verified**: Accounts are automatically linked
- **Email not verified**: User must verify email first or use password login

### Security Considerations

1. **HTTPS in Production**: Always use HTTPS URLs for OAuth redirects in production
2. **State Parameter**: FastCMS automatically includes CSRF protection via state parameter
3. **Redirect URI Validation**: Ensure redirect URIs match exactly in provider settings
4. **Scope Limitations**: OAuth only requests minimal required scopes (email, profile)

### Troubleshooting

**Redirect URI Mismatch:**
- Ensure the redirect URI in your `.env` file exactly matches what's configured in the OAuth provider
- Include the full URL: `http://localhost:8000/api/v1/oauth/google/callback`

**Access Denied Error:**
- User denied permission at the OAuth provider
- User needs to retry the OAuth flow

**Invalid Client Error:**
- Client ID or Client Secret is incorrect
- Verify credentials in `.env` file match provider settings

**Email Already Exists:**
- An account with this email already exists
- User can sign in with password or request password reset
- Or verify the existing account's email to enable linking

### Best Practices

1. **Production URLs**: Update redirect URIs to your production domain before deploying
2. **Error Handling**: Implement proper error handling for OAuth failures
3. **Email Verification**: Encourage users to verify email even with OAuth
4. **Multiple Providers**: Allow users to link multiple OAuth providers to one account
5. **Fallback**: Always provide traditional email/password login as backup

---

## License

MIT License - see LICENSE file for details
