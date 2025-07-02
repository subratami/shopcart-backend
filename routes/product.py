from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId
from database import products_collection

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
    page: int = Query(1, gt=0),
    limit: int = Query(10, gt=0)
):
    skip = (page - 1) * limit
    query = {}

# 👉 This handles combined keyword search
    if keyword:
        query["$or"] = [
        {"Brand": {"$regex": keyword, "$options": "i"}},
        {"Model": {"$regex": keyword, "$options": "i"}}
    ]

# 👉 These override if explicitly provided
    if brand:
        query["Brand"] = {"$regex": brand, "$options": "i"}
    if model:
        query["Model"] = {"$regex": model, "$options": "i"}

    

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
