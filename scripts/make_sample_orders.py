"""生成模拟店铺订单 CSV —— 模拟 RPA 从卖家后台导出的订单报表格式

用法: python -m scripts.make_sample_orders

数据生成逻辑（面试可讲的数据设计）:
- 1000 个 SKU，5 个品类，每个品类有自己的价格带
- 180 天，日均约 40 单
- 销量长尾: 按排名取 1/rank 权重，头部 SKU 占大头（符合真实电商分布）
- 季节性: 11-12 月旺季 x1.8，夏季 x1.2；周末 x1.15
- 数量分布: 1 件 75% / 2 件 20% / 3 件 5%
- 订单状态: Shipped 90% / Pending 5% / Cancelled 5%（贴近健康店铺）
"""
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw"
OUT_PATH = OUT_DIR / "sample_orders.csv"

# (品类, 标题模板, 价格区间 USD)
CATEGORIES = [
    ("Kitchen", ["Stainless Steel Water Bottle", "Silicone Utensil Set", "Coffee Grinder",
                 "Airtight Storage Containers", "Non-stick Frying Pan", "Milk Frother Handheld",
                 "Knife Sharpener", "Spice Rack Organizer", "Cutting Board Set", "Food Storage Bags",
                 "Electric Kettle", "Ice Cube Trays", "Measuring Cups Set", "Dish Drying Rack",
                 "Salad Spinner", "Reusable Coffee Filter", "Tea Infuser Set", "Oil Sprayer for Cooking",
                 "Can Opener", "Herb Scissors"], (8, 45)),
    ("Home", ["Memory Foam Pillow", "LED Desk Lamp", "Blackout Curtains",
              "Robot Vacuum Accessories", "Wall Art Prints", "Shower Caddy",
              "Storage Bins", "Essential Oil Diffuser", "Door Draft Stopper", "Closet Organizer",
              "Bed Sheet Set", "Weighted Blanket", "Curtain Rods", "Over-the-Door Hooks",
              "Scented Candles Set", "Photo Frames Set", "Laundry Hamper", "Vacuum Storage Bags",
              "Wall Clock", "Throw Pillow Covers"], (10, 60)),
    ("Sports", ["Yoga Mat", "Resistance Bands Set", "Adjustable Dumbbells",
                "Running Belt", "Foam Roller", "Jump Rope", "Waterproof Phone Pouch",
                "Gym Gloves", "Knee Compression Sleeve", "Camping Lantern",
                "Hiking Backpack", "Bike Lock", "Swim Goggles", "Tennis Grips",
                "Insulated Sports Bottle", "Exercise Sliders", "Push-up Bars", "Wrist Weights",
                "Fitness Tracker Band", "Yoga Blocks"], (10, 80)),
    ("Beauty", ["Vitamin C Serum", "Electric Toothbrush", "Hair Dryer Brush",
                "Makeup Brush Set", "Jade Roller", "Face Mask Pack", "Eyelash Curler",
                "Nail Polish Set", "Beard Trimmer", "Makeup Sponge Set",
                "Hair Straightener", "Facial Cleansing Brush", "Eyebrow Razor Set", "Shampoo Bar",
                "Lip Balm Set", "Cuticle Oil", "Hair Growth Serum", "Pimple Patches",
                "Body Scrub", "Under Eye Mask"], (6, 50)),
    ("Electronics", ["Wireless Earbuds", "Phone Stand", "USB-C Hub",
                     "Bluetooth Speaker", "Charging Cable 3-Pack", "Car Phone Mount",
                     "Screen Protector", "Smart Watch Band", "Webcam Cover", "HDMI Cable",
                     "Power Bank", "LED Strip Lights", "Wireless Charger", "Keyboard Cover",
                     "USB Flash Drive", "Bluetooth Tracker", "Gaming Mouse Pad", "Headphone Stand",
                     "Smart Plug", "Cable Organizer"], (9, 70)),
]
VARIANTS = ["", " - Black", " - White", " - Pro", " - Mini",
            " - Large", " - Small", " - Set of 2", " - Premium", " - Travel"]


def build_sku_pool() -> list[dict]:
    skus = []
    for cat, titles, (low, high) in CATEGORIES:
        for base in titles:
            for variant in VARIANTS:
                skus.append({
                    "asin": "B0" + "".join(
                        random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8)),
                    "title": base + variant,
                    "category": cat,
                    "base_price": round(random.uniform(low, high), 2),
                })
    # 打散后按排名生成长尾权重（第 1 名权重 1/1，第 1000 名 1/1000）
    # 注意: 不能按价格排序——那会让销量与价格耦合（越贵卖越多），违背真实电商分布
    random.shuffle(skus)
    return skus


def seasonal_factor(day_date: datetime) -> float:
    """Q4 旺季 + 夏季小高峰 + 周末效应"""
    factor = 1.0
    if day_date.month in (11, 12):
        factor *= 1.8
    elif day_date.month in (6, 7, 8):
        factor *= 1.2
    if day_date.weekday() >= 5:
        factor *= 1.15
    return factor


def main():
    random.seed(42)
    skus = build_sku_pool()
    weights = [1 / (i + 1) for i in range(len(skus))]

    rows = []
    start = datetime.now() - timedelta(days=180)
    order_seq = 1
    for day in range(180):
        day_date = start + timedelta(days=day)
        n_orders = max(1, round(40 * seasonal_factor(day_date) * random.uniform(0.85, 1.15)))
        for _ in range(n_orders):
            sku = random.choices(skus, weights=weights, k=1)[0]
            quantity = random.choices([1, 2, 3], weights=[75, 20, 5], k=1)[0]
            rows.append({
                "order_id": f"114-{random.randint(1000000, 9999999)}-{order_seq:07d}",
                "order_date": (day_date + timedelta(
                    hours=random.randint(0, 23), minutes=random.randint(0, 59))
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "asin": sku["asin"],
                "title": sku["title"],
                "category": sku["category"],
                "quantity": quantity,
                "unit_price": round(sku["base_price"] * random.uniform(0.9, 1.1), 2),
                "currency": "USD",
                "channel": "amazon",
                "status": random.choices(
                    ["Shipped", "Pending", "Cancelled"], weights=[90, 5, 5], k=1)[0],
            })
            order_seq += 1

    df = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    gmv = (df["unit_price"] * df["quantity"]).sum()
    print(f"模拟订单已生成: {OUT_PATH}")
    print(f"总行数 {len(df)} | SKU 数 {len(skus)} | 总 GMV ${gmv:,.2f}")
    print(f"日期范围 {df['order_date'].min()} ~ {df['order_date'].max()}")


if __name__ == "__main__":
    main()
