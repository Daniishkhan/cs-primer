"""MILESTONE 5: the HTTP adapter. Allowed imports: json, re, domain.

build_handler(place_order, get_order) -> handle(request) -> (status, body_dict)

It must reproduce legacy.py's routing and its status codes:
    POST /orders       -> 201 {"id","status","total_cents"}
                          400 malformed JSON / not an object / no body
                          422 ValidationError, 409 OutOfStock, 402 PaymentDeclined
    GET  /orders/<id>  -> 200 {"id","customer","status","total_cents","lines":[...]} or 404 "order not found"
    wrong method on a known path -> 405 {"error": "method not allowed"}
    anything else -> 404 {"error": "no such route"}
The use cases are passed in; this file knows nothing about SQL.
"""
import json
import re

import domain


def build_handler(place_order, get_order):
    def handle(request):
        raise NotImplementedError("TODO milestone 5: the HTTP handler")

    return handle
