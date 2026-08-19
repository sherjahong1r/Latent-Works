"""
WMS API Tool — REAL tenzorsoft API
USE_MOCK=False bo'lganda shu ishlaydi.

Auth: shared/wms_auth.py orqali (bitta, tekshirilgan manba — "identifier"
bilan login qiladi va ishlashi tasdiqlangan). Bu yerda alohida/takroriy
login mantig'i YOZILMAYDI, aks holda ikki joyda ikki xil xato paydo bo'lishi
mumkin (avval shunday bo'lgan edi: bu yerda "username" ishlatilgan edi).
"""
import httpx
from shared.config import USE_MOCK, WMS_API_URL
from shared.wms_auth import auth_headers, get_access_token

# ============================================================
# AUTH — shared/wms_auth.py orqali (yagona manba)
# ============================================================

def _headers() -> dict:
    """Authorization header — tekshirilgan shared/wms_auth.py orqali."""
    return auth_headers()

def _reset_token():
    """Token muddati tugasa (401) — majburan qayta login qildiradi."""
    get_access_token(force_refresh=True)


# ============================================================
# PURCHASE ORDERS
# ============================================================

def _real_get_purchase_orders(size=50, page=0) -> list:
    """
    GET /api/purchase-orders
    Barcha PO lar ro'yxati.
    """
    try:
        resp = httpx.get(
            f"{WMS_API_URL}/api/purchase-orders",
            params={"size": size, "page": page},
            headers=_headers(),
            timeout=15
        )
        if resp.status_code == 401:
            _reset_token()
            resp = httpx.get(
                f"{WMS_API_URL}/api/purchase-orders",
                params={"size": size, "page": page},
                headers=_headers(),
                timeout=15
            )
        data = resp.json()
        return data.get("content", [])
    except Exception as e:
        print(f"PO ro'yxat xatosi: {e}")
        return []


def _real_get_purchase_order_by_doc(doc_no: str) -> dict:
    """
    PO raqami bo'yicha qidirish.
    Masalan: PO-B18CA281

    Real JSON strukturasi (tenzorsoft dan):
    {
      "id": 9,
      "docNo": "PO-B18CA281",
      "docDate": "2026-07-04",
      "expectedDate": "2026-07-09",
      "counterpartyName": "АО Maxam-Chirchiq",
      "warehouseName": "Склад №8",
      "status": "RECEIVED",
      "totalAmount": 2550000.00,
      "lines": [
        {
          "id": 12,
          "lineNo": 1,
          "productId": 27083,
          "productSku": "MXIK-06301001002000000",
          "productName": "Одеяло",
          "qtyOrdered": 100.0,
          "qtyReceived": 100.0,
          "uomName": "кг",
          "price": 25500.0
        }
      ]
    }
    """
    orders = _real_get_purchase_orders(size=100)
    found = next((o for o in orders if o.get("docNo") == doc_no), None)
    if not found:
        return {"error": f"{doc_no} topilmadi"}
    return found


def _real_get_purchase_order_by_id(po_id: int) -> dict:
    """GET /api/purchase-orders/{id}"""
    try:
        resp = httpx.get(
            f"{WMS_API_URL}/api/purchase-orders/{po_id}",
            headers=_headers(),
            timeout=15
        )
        if resp.status_code == 404:
            return {"error": f"ID {po_id} topilmadi"}
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# PO → OCR uchun normallashtirish
# ============================================================

def normalize_po_for_comparison(po_data: dict) -> dict:
    """
    Real PO JSON ni OCR taqqoslash uchun
    standart formatga o'tkazish.
    """
    if "error" in po_data:
        return po_data

    lines = []
    for line in po_data.get("lines", []):
        lines.append({
            "line_no": line.get("lineNo"),
            "material_name": line.get("productName"),
            "material_code": line.get("productSku"),
            "ordered_qty": float(line.get("qtyOrdered", 0)),
            "received_qty": float(line.get("qtyReceived", 0)),
            "uom": line.get("uomName"),
            "price": float(line.get("price", 0))
        })

    return {
        "po_number": po_data.get("docNo"),
        "po_id": po_data.get("id"),
        "supplier": po_data.get("counterpartyName"),
        "partner": po_data.get("partnerName"),
        "warehouse": po_data.get("warehouseName"),
        "warehouse_id": po_data.get("warehouseId"),
        "doc_date": po_data.get("docDate"),
        "expected_date": po_data.get("expectedDate"),
        "status": po_data.get("status"),
        "currency": po_data.get("currencyResponse", {}).get("code"),
        "total_amount": po_data.get("totalAmount"),
        "lines": lines
    }


# ============================================================
# INVENTORY / WAREHOUSE
# ============================================================

def _real_get_warehouses() -> list:
    """GET /api/warehouses — omborlar ro'yxati."""
    try:
        resp = httpx.get(
            f"{WMS_API_URL}/api/warehouses",
            params={"active": True, "size": 100},
            headers=_headers(),
            timeout=15
        )
        data = resp.json()
        return data.get("content", data) if isinstance(data, dict) else data
    except Exception as e:
        print(f"Warehouse xatosi: {e}")
        return []


def _real_get_inventory(location=None, material_code=None) -> list:
    """
    Zaxira qoldig'i.
    TODO: endpoint nomi aniqlanishi kerak
    """
    try:
        params = {"size": 50, "page": 0}
        if location:
            params["location"] = location
        if material_code:
            params["sku"] = material_code
        resp = httpx.get(
            f"{WMS_API_URL}/api/inventory",
            params=params,
            headers=_headers(),
            timeout=15
        )
        if resp.status_code == 404:
            return []
        data = resp.json()
        return data.get("content", []) if isinstance(data, dict) else data
    except Exception as e:
        print(f"Inventory xatosi: {e}")
        return []


# ============================================================
# RECEIPT DRAFT
# ============================================================

def _real_create_receipt_draft(po_id: int, lines: list) -> dict:
    """
    Qabul drafti yaratish.
    TODO: endpoint nomi aniqlanishi kerak — backend dan so'rang.

    Taxminiy: POST /api/receipts yoki /api/goods-receipts
    """
    payload = {
        "purchaseOrderId": po_id,
        "lines": [
            {
                "purchaseOrderLineId": line.get("line_id"),
                "qtyReceived": line.get("qty_received"),
                "lotNumber": line.get("lot"),
                "expiryDate": line.get("expiry")
            }
            for line in lines
        ]
    }
    try:
        resp = httpx.post(
            f"{WMS_API_URL}/api/receipts/draft",
            json=payload,
            headers=_headers(),
            timeout=15
        )
        if resp.status_code in [200, 201]:
            return {"success": True, "data": resp.json()}
        return {
            "success": False,
            "status_code": resp.status_code,
            "detail": resp.text
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================
# PUBLIC funksiyalar — agent ishlatadi
# ============================================================

if USE_MOCK:
    from mock_data.wms_mock import (
        get_inventory_balance as _mock_inventory,
        get_expected_receipt as _mock_receipt,
        get_warehouse_tasks as _mock_tasks,
        get_bin_status as _mock_bin,
        get_exceptions as _mock_exceptions
    )


def fetch_purchase_order(doc_no: str) -> dict:
    """PO raqami bo'yicha qidirish."""
    if USE_MOCK:
        from mock_data.wms_mock import get_expected_receipt
        return get_expected_receipt(doc_no) or {"error": f"{doc_no} topilmadi"}
    raw = _real_get_purchase_order_by_doc(doc_no)
    return normalize_po_for_comparison(raw)


def fetch_inventory(location=None, material_code=None) -> list:
    if USE_MOCK:
        return _mock_inventory(location, material_code)
    return _real_get_inventory(location, material_code)


def fetch_tasks(operator_id=None, status=None) -> list:
    if USE_MOCK:
        return _mock_tasks(operator_id, status)
    # TODO: tasks endpoint aniqlanishi kerak
    return []


def fetch_bin_status(bin_id: str) -> dict:
    if USE_MOCK:
        return _mock_bin(bin_id)
    # TODO: bin endpoint aniqlanishi kerak
    return {}


def fetch_exceptions(limit=10) -> list:
    if USE_MOCK:
        return _mock_exceptions(limit)
    # TODO: exceptions endpoint aniqlanishi kerak
    return []


def create_receipt_draft(po_doc_no: str, lines: list) -> dict:
    """Operator tasdiqlagandan keyin chaqiriladi."""
    if USE_MOCK:
        return {
            "success": True,
            "message": "Mock draft yaratildi",
            "po_number": po_doc_no,
            "lines": lines
        }
    po = _real_get_purchase_order_by_doc(po_doc_no)
    if "error" in po:
        return po
    return _real_create_receipt_draft(po["id"], lines)