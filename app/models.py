# models.py
from pydantic import BaseModel

class Payment(BaseModel):
    payee_first_name: str
    payee_last_name: str
    payee_payment_status: str 
    payee_added_date_utc: str 
    payee_due_date: str
    payee_address_line_1: str
    payee_address_line_2: str | None = None
    payee_city: str
    payee_country: str 
    payee_province_or_state: str | None = None
    payee_postal_code: str
    payee_phone_number: str 
    payee_email: str
    currency: str
    discount_percent: float | None = None
    tax_percent: float | None = None
    due_amount: float
    evidence_file_id: str | None = None