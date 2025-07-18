# Poloniex-Golang API Integration

This integration allows the Poloniex Python API to automatically store order data in the Golang API when orders are placed.

## Features

- **Automatic Order Storage**: When an order is placed via Poloniex, it's automatically stored in the Golang API
- **Session Management**: Each trading session has a unique session key for tracking
- **Authentication**: Automatic authentication with the Golang API
- **Error Handling**: Graceful error handling - Golang API failures don't prevent Poloniex orders
- **Order Updates**: Support for updating order status when orders are filled/cancelled

## How It Works

1. **Initialization**: When creating a `PoloniexPrivate` instance, you can optionally provide a `session_key`
2. **Authentication**: The API automatically authenticates with the Golang API when needed
3. **Order Placement**: When `place_order()` is called:
   - Order is sent to Poloniex
   - If successful, order data is stored in Golang API
   - Both Poloniex order ID and Golang order ID are tracked

## Usage

### Basic Setup

```python
from exchange_api.poloniex.poloniex_private import PoloniexPrivate

# Initialize with session key
poloniex = PoloniexPrivate(
    symbol="BTC",
    quote="USDT",
    api_key="your_api_key",
    secret_key="your_secret_key",
    session_key="trading_session_001"  # Optional - auto-generated if not provided
)
```

### Placing Orders

```python
# Place a market buy order
result = poloniex.place_order(
    side_order="buy",
    quantity=0.001,
    order_type="market"
)

if result["code"] == 0:
    print(f"Order placed: {result['data']['orderId']}")
    # Order is automatically stored in Golang API
```

### Manual Authentication (Optional)

```python
# Authenticate manually if needed
if poloniex.authenticate_server_api():
    print("Authenticated with Golang API")
```

## Configuration

### Environment Variables

Make sure your Golang API server is running with the correct configuration:

```bash
# .env file
SERVER_PORT=8083
DATABASE_DSN=your_database_connection
JWT_SECRET=your_jwt_secret
```

### Python Configuration

The integration uses these default settings:

```python
GOLANG_API_BASE_URL = "http://localhost:8083"
```

You can modify these in the `poloniex_private.py` file if needed.

## API Endpoints Used

### Golang API Endpoints

- `POST /api/v1/auth/login` - Authentication
- `POST /api/v1/orders` - Create order
- `PUT /api/v1/orders/{id}/status` - Update order status

### Data Flow

1. **Order Creation**:
   ```
   Poloniex API → Order Response → Golang API Storage
   ```

2. **Order Updates**:
   ```
   Order Status Check → Golang API Update
   ```

## Error Handling

The integration is designed to be non-blocking:

- If Golang API is unavailable, Poloniex orders still work
- Authentication failures are logged but don't prevent trading
- Order storage failures are logged as warnings

## Security

- JWT tokens are used for Golang API authentication
- Credentials are not stored permanently
- Session keys provide isolation between different trading sessions

## Testing

Run the test script to verify the integration:

```bash
cd /Users/vudat/Desktop/Fin20/strategies-src
python test_poloniex_golang_integration.py
```

## Requirements

### Python Dependencies

```bash
pip install requests redis uuid
```

### Golang API

- Server running on port 8083
- Authentication endpoints enabled
- Order management endpoints enabled

## Database Schema

The integration stores orders in the Golang API with this structure:

```sql
CREATE TABLE orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    order_id VARCHAR(255) UNIQUE NOT NULL,
    session_key VARCHAR(255) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) DEFAULT 'market',
    quantity FLOAT NOT NULL,
    price FLOAT DEFAULT 0,
    filled_qty FLOAT DEFAULT 0,
    avg_price FLOAT DEFAULT 0,
    status VARCHAR(50) NOT NULL,
    time_in_force VARCHAR(10) DEFAULT 'GTC',
    exchange_order_id VARCHAR(255),
    commission FLOAT DEFAULT 0,
    pnl FLOAT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    filled_at TIMESTAMP
);
```

## Support

For issues or questions:

1. Check the Golang API logs for authentication issues
2. Verify the server is running on the correct port
3. Ensure database connections are working
4. Check Python console output for error messages

## Example Output

```
📝 Storing order in Golang API...
✅ Successfully authenticated with Golang API
✅ Order stored in Golang API with ID: uuid-here
✅ Order 123456789 stored in both Poloniex and Golang API
```