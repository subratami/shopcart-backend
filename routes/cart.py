from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from bson import ObjectId
from .auth import get_current_user
from database import cart_collection, products_collection, orders_collection
from datetime import datetime

router = APIRouter()

# --- Demo Coupon Codes ---
COUPONS = {
    "SAVE10": 0.10,
    "BIGSALE": 0.25,
    "FREEME": 1.00
}

# --- Request Models ---
class AddToCartRequest(BaseModel):
    product_id: str
    quantity: int = 1

class RemoveFromCartRequest(BaseModel):
    product_id: str

class UpdateCartItem(BaseModel):
    product_id: str
    quantity: int

class ApplyCouponRequest(BaseModel):
    code: str

# -------------------------------
# GET /cart – Fetch and Enrich
# -------------------------------
@router.get("/cart")
async def get_cart(current_user: dict = Depends(get_current_user)):
    user_email = current_user["email"]
    cart = await cart_collection.find_one({"user_email": user_email})
    if not cart or not cart.get("items"):
        return {"items": [], "coupon": None, "discount_total": 0, "final_total": 0}

    enriched_items = []
    total = 0
    for item in cart["items"]:
        product = await products_collection.find_one({"_id": ObjectId(item["product_id"])})
        if product:
            subtotal = item["quantity"] * product["price"]
            enriched_items.append({
                "product_id": str(product["_id"]),
                "name": product["name"],
                "price": product["price"],
                "image": product.get("image", ""),
                "description": product.get("description", ""),
                "quantity": item["quantity"],
                "subtotal": subtotal
            })
            total += subtotal

    coupon = cart.get("applied_coupon")
    discount = COUPONS.get(coupon, 0) if coupon else 0
    discount_amount = total * discount
    final_total = total - discount_amount

    return {
        "items": enriched_items,
        "coupon": coupon,
        "discount_total": round(discount_amount, 2),
        "final_total": round(final_total, 2)
    }

# -----------------------------------
# POST /cart/add – Add or Increment
# -----------------------------------
@router.post("/cart/add")
async def add_to_cart(item: AddToCartRequest, current_user: dict = Depends(get_current_user)):
    user_email = current_user["email"]

    if item.quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")

    cart = await cart_collection.find_one({"user_email": user_email})

    if not cart:
        await cart_collection.insert_one({
            "user_email": user_email,
            "items": [{"product_id": item.product_id, "quantity": item.quantity}]
        })
    else:
        updated = False
        for cart_item in cart["items"]:
            if cart_item["product_id"] == item.product_id:
                cart_item["quantity"] += item.quantity
                updated = True
                break
        if not updated:
            cart["items"].append({"product_id": item.product_id, "quantity": item.quantity})

        await cart_collection.update_one(
            {"user_email": user_email},
            {"$set": {"items": cart["items"]}}
        )

    return {"message": "Item added to cart ✅"}

# -----------------------------------
# PUT /cart/update – Set New Quantity
# -----------------------------------
@router.put("/cart/update")
async def update_cart_item(body: UpdateCartItem, current_user: dict = Depends(get_current_user)):
    user_email = current_user["email"]

    if body.quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be negative")

    cart = await cart_collection.find_one({"user_email": user_email})
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    updated_items = []
    found = False
    for item in cart["items"]:
        if item["product_id"] == body.product_id:
            found = True
            if body.quantity > 0:
                updated_items.append({"product_id": item["product_id"], "quantity": body.quantity})
        else:
            updated_items.append(item)

    if not found:
        raise HTTPException(status_code=404, detail="Product not in cart")

    await cart_collection.update_one(
        {"user_email": user_email},
        {"$set": {"items": updated_items}}
    )

    return {"message": "Cart item updated ✅"}

# -----------------------------------
# DELETE /cart/remove – Remove Item
# -----------------------------------
@router.delete("/cart/remove")
async def remove_from_cart(body: RemoveFromCartRequest, current_user: dict = Depends(get_current_user)):
    user_email = current_user["email"]
    cart = await cart_collection.find_one({"user_email": user_email})
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=404, detail="Cart is empty")

    new_items = [item for item in cart["items"] if item["product_id"] != body.product_id]

    if len(new_items) == len(cart["items"]):
        raise HTTPException(status_code=404, detail="Product not found in cart")

    await cart_collection.update_one(
        {"user_email": user_email},
        {"$set": {"items": new_items}}
    )

    return {"message": "Item removed from cart 🗑️"}

# -----------------------------------
# POST /cart/coupon – Apply Discount
# -----------------------------------
@router.post("/cart/coupon")
async def apply_coupon(body: ApplyCouponRequest, current_user: dict = Depends(get_current_user)):
    user_email = current_user["email"]
    code = body.code.upper()

    if code not in COUPONS:
        raise HTTPException(status_code=400, detail="Invalid or expired coupon")

    await cart_collection.update_one(
        {"user_email": user_email},
        {"$set": {"applied_coupon": code}}
    )

    return {"message": f"Coupon '{code}' applied 🎉", "discount_rate": COUPONS[code]}

# -----------------------------------
# POST /checkout – Finalize & Clear
# -----------------------------------
@router.post("/checkout")
async def checkout(current_user: dict = Depends(get_current_user)):
    user_email = current_user["email"]

    cart = await cart_collection.find_one({"user_email": user_email})
    if not cart or not cart.get("items"):
        raise HTTPException(status_code=400, detail="Your cart is empty")

    enriched_items = []
    total = 0
    for item in cart["items"]:
        product = await products_collection.find_one({"_id": ObjectId(item["product_id"])})
        if product:
            subtotal = item["quantity"] * product["price"]
            enriched_items.append({
                "product_id": str(product["_id"]),
                "name": product["name"],
                "quantity": item["quantity"],
                "price": product["price"],
                "subtotal": subtotal
            })
            total += subtotal

    coupon = cart.get("applied_coupon")
    discount = COUPONS.get(coupon, 0)
    discount_amount = total * discount
    final_total = total - discount_amount

    order = {
        "user_email": user_email,
        "items": enriched_items,
        "total": round(total, 2),
        "discount_code": coupon,
        "final_total": round(final_total, 2),
        "created_at": datetime.utcnow()
    }

    await orders_collection.insert_one(order)
    await cart_collection.delete_one({"user_email": user_email})

    return {"message": "Order placed 🎉", "order_summary": order}

# -----------------------------------
# GET /orders – View Order History
# -----------------------------------
@router.get("/orders")
async def get_orders(current_user: dict = Depends(get_current_user)):
    user_email = current_user["email"]
    cursor = orders_collection.find({"user_email": user_email}).sort("created_at", -1)
    orders = []
    async for order in cursor:
        order["_id"] = str(order["_id"])
        orders.append(order)

    return {"orders": orders}
