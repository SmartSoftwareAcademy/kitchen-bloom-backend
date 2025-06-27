# Inventory Management API Documentation

This document provides detailed information about the Inventory Management API endpoints, focusing on batch/lot tracking and expiry management.

## Table of Contents
- [Base URL](#base-url)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Batches](#batches)
  - [Batch Stock](#batch-stock)
  - [Inventory Adjustments with Batches](#inventory-adjustments-with-batches)
- [Sample Data](#sample-data)
- [Error Handling](#error-handling)

## Base URL
```
/api/inventory/
```

## Authentication
All endpoints require authentication using JWT tokens. Include the token in the `Authorization` header:
```
Authorization: Bearer <your_token>
```

## Endpoints

### Batches

#### List Batches
```
GET /api/inventory/batches/
```

**Query Parameters:**
- `product`: Filter by product ID
- `is_active`: Filter by active status (true/false)
- `expiry_status`: Filter by expiry status (expired, expiring_soon, active)
- `search`: Search by batch number or product name
- `ordering`: Order by fields (batch_number, expiry_date, created_at, etc.)

**Example Response (200 OK):**
```json
{
  "count": 10,
  "next": "...",
  "previous": null,
  "results": [
    {
      "id": 1,
      "batch_number": "BATCH-MLK001-001",
      "product": 1,
      "product_name": "Milk",
      "manufactured_date": "2025-05-15",
      "expiry_date": "2025-08-15",
      "is_active": true,
      "status": "active",
      "notes": "",
      "created_at": "2025-05-15T10:00:00Z",
      "updated_at": "2025-05-15T10:00:00Z"
    }
  ]
}
```

#### Create Batch
```
POST /api/inventory/batches/
```

**Request Body:**
```json
{
  "batch_number": "BATCH-CHK001-001",
  "product": 6,
  "manufactured_date": "2025-06-01",
  "expiry_date": "2025-09-01",
  "is_active": true,
  "notes": "Summer batch"
}
```

### Batch Stock

#### List Batch Stock
```
GET /api/inventory/batch-stock/
```

**Query Parameters:**
- `batch`: Filter by batch ID
- `branch`: Filter by branch ID
- `batch__product`: Filter by product ID
- `quantity__lt`, `quantity__gt`: Filter by quantity
- `expiry_status`: Filter by expiry status (expired, expiring_soon)
- `low_stock`: Filter for low stock items (true/false)

**Example Response (200 OK):**
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "batch": 1,
      "batch_number": "BATCH-MLK001-001",
      "product_name": "Milk",
      "product_id": 1,
      "branch": 1,
      "branch_name": "Main Branch",
      "quantity": "10.000",
      "reserved_quantity": "2.000",
      "available_quantity": "8.000",
      "expiry_date": "2025-08-15",
      "last_checked": "2025-06-17T10:00:00Z",
      "created_at": "2025-06-17T10:00:00Z"
    }
  ]
}
```

#### Get Expiring Soon Batches
```
GET /api/inventory/batch-stock/expiring-soon/
```

Returns batches that will expire within the next 30 days.

#### Get Low Stock Batches
```
GET /api/inventory/batch-stock/low-stock/
```

Returns batches where the quantity is at or below the reorder level.

#### Get Expired Batches
```
GET /api/inventory/batch-stock/expired/
```

Returns batches that have already expired.

### Inventory Adjustments with Batches

#### Create Adjustment with Batch
```
POST /api/inventory/adjustments/
```

**Request Body:**
```json
{
  "product": 1,
  "branch": 1,
  "quantity_after": 15,
  "reason": "Stock take adjustment",
  "batch_id": 1
}
```

## Sample Data

You can populate the database with sample data using the management command:

```bash
python manage.py seed_inventory
```

This will create:
- Sample categories, suppliers, and units of measure
- Sample products with batch tracking enabled where applicable
- Sample batches and batch stock entries
- A default superuser (admin@example.com / admin123)

## Error Handling

### 400 Bad Request
```json
{
  "batch": ["This field is required for products with batch tracking enabled."]
}
```

### 403 Forbidden
```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found
```json
{
  "detail": "Not found."
}
```
