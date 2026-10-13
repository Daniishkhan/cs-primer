"""The catalog's public face. Other modules import this file and nothing else from here."""
from .service import (OutOfStock, ProductInUse, UnknownProduct, add_product, add_removal_guard,
                      exists, line_price, put_back, remove_product, reset, stock_of, take_stock,
                      weight_of)

__all__ = ["OutOfStock", "ProductInUse", "UnknownProduct", "add_product", "add_removal_guard",
           "exists", "line_price", "put_back", "remove_product", "reset", "stock_of", "take_stock",
           "weight_of"]
