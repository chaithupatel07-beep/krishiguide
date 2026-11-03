from typing import List, Optional, Dict, Any, Union
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict


# 1. Farm Profile Schemas
class FarmProfileCreateUpdate(BaseModel):
    farm_location: str = Field(..., min_length=2, max_length=255, description="Geographic location / Village / District")
    farm_size: Decimal = Field(..., gt=0, description="Farm size in acres")
    soil_type: str = Field(..., min_length=2, max_length=100, description="Soil classification (e.g., Red sandy loam, Black cotton, Alluvial)")
    crop_details: Optional[Union[List[str], Dict[str, Any]]] = Field(None, description="Current or planned crops")
    irrigation_details: Optional[Union[List[str], Dict[str, Any]]] = Field(None, description="Irrigation facilities (e.g., Drip, Borewell, Canal)")


class FarmProfileResponse(BaseModel):
    id: int
    user_id: int
    farm_location: str
    farm_size: Decimal
    soil_type: str
    crop_details: Optional[Any] = None
    irrigation_details: Optional[Any] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# 2. Cultivation Cost Calculator Schemas
class CostCalculationRequest(BaseModel):
    crop_name: str = Field(..., min_length=2, max_length=100, description="Target crop (e.g., Groundnut, Paddy, Cotton)")
    land_area: Decimal = Field(..., gt=0, description="Cultivated land area in acres")
    seed_cost: Decimal = Field(Decimal("0.00"), ge=0, description="Seed / sapling cost")
    fertilizer_cost: Decimal = Field(Decimal("0.00"), ge=0, description="Fertilizers and bio-nutrients cost")
    labor_cost: Decimal = Field(Decimal("0.00"), ge=0, description="Manual labor / weeding / harvesting wages")
    irrigation_cost: Decimal = Field(Decimal("0.00"), ge=0, description="Electricity / diesel / water charges")
    pesticide_cost: Decimal = Field(Decimal("0.00"), ge=0, description="Plant protection chemicals / biopesticides")
    machinery_fuel_cost: Decimal = Field(Decimal("0.00"), ge=0, description="Tractor hiring, ploughing, and diesel")
    post_harvest_transport_cost: Decimal = Field(Decimal("0.00"), ge=0, description="Threshing, packaging, and transport")
    expected_yield_per_acre: Optional[Decimal] = Field(None, ge=0, description="Expected yield per acre in quintals")
    expected_market_price_per_unit: Optional[Decimal] = Field(None, ge=0, description="Expected market price per quintal (₹)")


class CostBreakdownItem(BaseModel):
    category: str
    amount: Decimal
    percentage: Decimal


class CostCalculationResponse(BaseModel):
    crop_name: str
    land_area_acres: Decimal
    total_expenditure: Decimal
    cost_per_acre: Decimal
    breakdown: List[CostBreakdownItem]
    expected_yield_total: Optional[Decimal] = None
    expected_gross_revenue: Optional[Decimal] = None
    expected_net_profit: Optional[Decimal] = None
    profit_margin_percentage: Optional[Decimal] = None
    currency: str = "INR"


# 3. Farm Expense Tracker Schemas
class FarmExpenseCreate(BaseModel):
    category: str = Field(..., min_length=2, max_length=100, description="Expense category (Seeds, Fertilizer, Pesticides, Labor, etc.)")
    amount: Decimal = Field(..., gt=0, description="Expense amount in currency units")
    crop_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    expense_date: Optional[date] = Field(None, description="Date of expense, defaults to today")
    meta_info: Optional[Dict[str, Any]] = None


class FarmExpenseResponse(BaseModel):
    id: int
    user_id: int
    category: str
    amount: Decimal
    crop_name: Optional[str] = None
    description: Optional[str] = None
    expense_date: date
    meta_info: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedExpensesResponse(BaseModel):
    total_count: int
    total_amount: Decimal
    items: List[FarmExpenseResponse]


# 4. Crop Task Scheduler Schemas
class CropTaskCreate(BaseModel):
    task_title: str = Field(..., min_length=2, max_length=255, description="Activity title (e.g., Gypsum application, Sowing)")
    crop_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    scheduled_date: date = Field(..., description="Target execution date")
    priority: Optional[str] = Field("medium", description="Priority level: low, medium, high, urgent")
    status: Optional[str] = Field("pending", description="Task status: pending, in_progress, completed")
    notification_tag: Optional[str] = Field(None, description="Tag for notification (e.g., Irrigation, Spraying)")


class CropTaskUpdate(BaseModel):
    task_title: Optional[str] = Field(None, min_length=2, max_length=255)
    crop_name: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[date] = None
    is_completed: Optional[bool] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    notification_tag: Optional[str] = None


class CropTaskResponse(BaseModel):
    id: int
    user_id: int
    task_title: str
    crop_name: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: date
    is_completed: bool
    reminder_info: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

