from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import auth, cart, product

app = FastAPI()

app.include_router(auth.router)
app.include_router(cart.router)
app.include_router(product.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
