#!/usr/bin/env python3
"""External MCP server for order management tools."""

import logging
from mcp.server.fastmcp import FastMCP

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("Order Management Server")

# Mock order database
ORDERS = {
    "ORD-001": {
        "id": "ORD-001",
        "customer": "John Doe",
        "items": ["Laptop", "Mouse"],
        "total": 1299.99,
        "status": "shipped"
    },
    "ORD-002": {
        "id": "ORD-002",
        "customer": "Jane Smith",
        "items": ["Phone", "Case"],
        "total": 899.99,
        "status": "pending"
    }
}

@mcp.tool()
def get_order(order_id: str) -> str:
    """Get order details by order ID.
    
    Args:
        order_id: The order ID to look up (e.g., 'ORD-001')
    
    Returns:
        Order details in JSON format
    """
    logger.info(f"Looking up order: {order_id}")
    
    if order_id in ORDERS:
        order = ORDERS[order_id]
        result = f"Order {order['id']}: Customer: {order['customer']}, Items: {', '.join(order['items'])}, Total: ${order['total']}, Status: {order['status']}"
        logger.info(f"Found order: {result}")
        return result
    else:
        error_msg = f"Order {order_id} not found"
        logger.warning(error_msg)
        return error_msg

@mcp.tool()
def update_order_status(order_id: str, new_status: str) -> str:
    """Update the status of an order.
    
    Args:
        order_id: The order ID to update
        new_status: New status (pending, processing, shipped, delivered, cancelled)
    
    Returns:
        Update confirmation message
    """
    logger.info(f"Updating order {order_id} status to {new_status}")
    
    valid_statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]
    if new_status not in valid_statuses:
        error_msg = f"Invalid status: {new_status}. Valid statuses: {', '.join(valid_statuses)}"
        logger.error(error_msg)
        return error_msg
    
    if order_id in ORDERS:
        old_status = ORDERS[order_id]["status"]
        ORDERS[order_id]["status"] = new_status
        result = f"Order {order_id} status updated from '{old_status}' to '{new_status}'"
        logger.info(result)
        return result
    else:
        error_msg = f"Order {order_id} not found"
        logger.warning(error_msg)
        return error_msg

@mcp.tool()
def list_orders(status_filter: str = "all") -> str:
    """List all orders, optionally filtered by status.
    
    Args:
        status_filter: Filter by status (all, pending, processing, shipped, delivered, cancelled)
    
    Returns:
        List of orders matching the filter
    """
    logger.info(f"Listing orders with filter: {status_filter}")
    
    filtered_orders = []
    for order_id, order in ORDERS.items():
        if status_filter == "all" or order["status"] == status_filter:
            filtered_orders.append(f"{order_id}: {order['customer']} - ${order['total']} ({order['status']})")
    
    if filtered_orders:
        result = "Orders:\n" + "\n".join(filtered_orders)
    else:
        result = f"No orders found with status: {status_filter}"
    
    logger.info(f"Found {len(filtered_orders)} orders")
    return result

@mcp.tool()
def create_order(customer: str, items_json: str, total: float) -> str:
    """Create a new order.
    
    Args:
        customer: Customer name
        items_json: Items as JSON string (e.g., '["item1", "item2"]')
        total: Total order amount
    
    Returns:
        New order confirmation
    """
    import json
    
    # Generate new order ID
    next_id = f"ORD-{len(ORDERS) + 1:03d}"
    
    try:
        items = json.loads(items_json)
    except json.JSONDecodeError:
        error_msg = "Invalid items JSON format"
        logger.error(error_msg)
        return error_msg
    
    new_order = {
        "id": next_id,
        "customer": customer,
        "items": items,
        "total": total,
        "status": "pending"
    }
    
    ORDERS[next_id] = new_order
    result = f"Created order {next_id} for {customer}: {', '.join(items)} - ${total}"
    logger.info(result)
    return result

if __name__ == "__main__":
    logger.info("Starting Order Management MCP server...")
    mcp.run(transport="stdio")