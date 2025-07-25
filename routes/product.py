from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from database import products_collection
import re

router = APIRouter()

# -------------------------------
# ✏️ Model for product input
# -------------------------------
class ProductIn(BaseModel):
    name: str
    price: float
    image: str = ""
    description: str = ""

# -------------------------------
# 📦 Add a new product
# -------------------------------
@router.post("/products")
async def add_product(product: ProductIn):
    result = await products_collection.insert_one(product.dict())
    return {"message": "Product added", "product_id": str(result.inserted_id)}

# -------------------------------
# 📄 Get all products
# -------------------------------
@router.get("/products")
async def get_all_products():
    products = []
    cursor = products_collection.find({})
    async for product in cursor:
        product["_id"] = str(product["_id"])
        products.append(product)
    return {"products": products}

# -------------------------------
# 🔍 Get a product by ID
# -------------------------------
@router.get("/products/{product_id}")
async def get_product(product_id: str):
    try:
        product = await products_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        product["_id"] = str(product["_id"])
        return product
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product ID")

# -------------------------------
# 🔎 Search products with filters + pagination
# -------------------------------
@router.get("/search")
async def search_products(
    keyword: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    storage: Optional[str] = Query(None),
    ram: Optional[str] = Query(None),
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    order: Optional[str] = Query(None, description="Sort order: 'asc' or 'desc'"),
    sorty_by: Optional[str] = Query(None),
    page: int = Query(1, gt=0),
    limit: int = Query(10, gt=0)
):
    skip = (page - 1) * limit
    query = {}

 # 🔍 Keyword search (e.g., "realme c11")
    if keyword:
        terms = re.split(r"\s+", keyword.strip())
        query["$or"] = []
        for term in terms:
            query["$or"].append({"Brand": {"$regex": term, "$options": "i"}})
            query["$or"].append({"Model": {"$regex": term, "$options": "i"}})
    

# 👉 These override if explicitly provided
    if brand:
        query["Brand"] = {"$regex": brand, "$options": "i"}
    if model:
        query["Model"] = {"$regex": model, "$options": "i"}
    if storage:
        query["Storage"] = storage
    if ram:
        query["Memory"] = ram
    if min_price is not None and max_price is not None:
        query["Selling Price"] = {"$gte": min_price, "$lt": max_price}
    elif min_price is not None:
        query["Selling Price"] = {"$gte": min_price}
    elif max_price is not None:
        query["Selling Price"] = {"$lt": max_price}
    
    sort_field =None
    if sorty_by:
        if sorty_by == "price":
            sort_field = "Selling Price"
        elif sorty_by == "rating":
            sort_field = "Rating"
    
    cursor = products_collection.find(query).skip(skip).limit(limit)
    products = []
    async for product in cursor:
        product["_id"] = str(product["_id"])
        products.append(product)

    total = await products_collection.count_documents(query)

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "products": products
    }

# -------------------------------
# 🔠 Auto-suggest brands
# -------------------------------
@router.get("/brands/autocomplete")
async def suggest_brands(prefix: str = ""):
    pipeline = [
        {"$match": {"Brand": {"$regex": f"^{prefix}", "$options": "i"}}},
        {"$group": {"_id": "$Brand"}},
        {"$limit": 10}
    ]
    cursor = products_collection.aggregate(pipeline)
    return [doc["_id"] async for doc in cursor]
