"""亚马逊 Best Sellers 榜单采集器（① RPA 采集层）

采集内容: 排名 / ASIN / 标题 / 价格 / 评分 / 评论数
落库:     dim_product(商品维度, upsert) + fact_snapshot(每次采集追加快照)
存档:     原始 HTML 保存到 data/raw/，选择器失效时便于排查

反爬策略:
- 真实浏览器指纹 + 请求间随机延迟（合规：控制频率、只采公开页面）
- 检测到验证码/拦截页 -> 指数退避重试，连续失败自动放弃不拖垮调度
- 只采集公开榜单页，不碰登录墙

用法:
    python -m collectors.amazon_bestseller            # 采集 settings.yaml 里的全部类目
    python -m collectors.amazon_bestseller --headful  # 显示浏览器窗口（调试选择器用）
"""
import argparse
import random
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from database.db import get_session, load_config
from database.models import DimProduct, FactSnapshot
from utils.logger import get_logger

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

logger = get_logger("collector")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 亚马逊改版频繁，每个字段配多个候选选择器，逐个尝试
CARD_SELECTORS = ["#gridItemRoot", "li.zg-item-immersion"]
RANK_SELECTORS = ["div.zg-bdg-text", "span.zg-bdg-text"]
TITLE_SELECTORS = [".p13n-sc-truncate-desktop-type2", ".p13n-sc-truncated"]
PRICE_SELECTORS = ["span.p13n-sc-price", "span._cDEzb_p13n-sc-price_3mJ9Z"]
RATING_SELECTORS = ["i.a-icon-star .a-icon-alt", "span.a-icon-alt"]
REVIEW_SELECTORS = ["a.a-size-small.a-link-normal", "span.a-size-small"]

BLOCKED_TITLES = ("robot check", "sorry! something went wrong")


# ---------- 解析工具 ----------

def _first_text(scope, selectors):
    """在 scope（page 或卡片 locator）上依次尝试选择器，返回第一个非空文本"""
    for sel in selectors:
        loc = scope.locator(sel)
        try:
            if loc.count() > 0:
                text = loc.first.inner_text().strip()
                if text:
                    return text
        except Exception:
            continue
    return None


def _parse_price(text):
    if not text:
        return None
    m = re.search(r"[\d,]+\.?\d*", text)
    return float(m.group().replace(",", "")) if m else None


def _parse_rating(text):
    if not text:
        return None
    m = re.search(r"([\d.]+)\s*out", text)
    return float(m.group(1)) if m else None


def _parse_int(text):
    if not text:
        return None
    m = re.search(r"[\d,]+", text)
    return int(m.group().replace(",", "")) if m else None


def _parse_rank(text):
    if not text:
        return None
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


def is_blocked(page):
    """检测验证码/拦截页"""
    title = (page.title() or "").lower()
    if any(t in title for t in BLOCKED_TITLES):
        return True
    return page.locator("form[action*='validateCaptcha']").count() > 0


# ---------- 采集流程 ----------

def parse_cards(page):
    """从榜单页解析商品卡片列表"""
    cards, seen = [], set()
    for sel in CARD_SELECTORS:
        loc = page.locator(sel)
        if loc.count() == 0:
            continue
        for i in range(loc.count()):
            card = loc.nth(i)
            link = card.locator("a[href*='/dp/']")
            href = link.first.get_attribute("href") if link.count() else ""
            m = re.search(r"/dp/([A-Z0-9]{10})", href or "")
            if not m or m.group(1) in seen:
                continue
            asin = m.group(1)
            seen.add(asin)
            title = _first_text(card, TITLE_SELECTORS)
            if not title:  # 兜底：图片 alt 通常是商品标题
                img = card.locator("img")
                title = img.first.get_attribute("alt") if img.count() else None
            cards.append({
                "asin": asin,
                "url": "https://www.amazon.com/dp/" + asin,
                "rank": _parse_rank(_first_text(card, RANK_SELECTORS)),
                "title": title,
                "price": _parse_price(_first_text(card, PRICE_SELECTORS)),
                "rating": _parse_rating(_first_text(card, RATING_SELECTORS)),
                "reviews": _parse_int(_first_text(card, REVIEW_SELECTORS)),
            })
        if cards:
            break
    return cards


def _fetch_with_retry(page, url, delay, attempts=3):
    """带退避重试的页面抓取；成功存档原始 HTML 并返回 True"""
    for attempt in range(1, attempts + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            time.sleep(random.uniform(*delay))
        except Exception as e:
            logger.warning("请求异常(第%s次): %s", attempt, e)
            time.sleep(30 * attempt)
            continue
        if is_blocked(page):
            logger.warning("检测到拦截页(第%s次)，退避 %ss 后重试...", attempt, 30 * attempt)
            time.sleep(30 * attempt)
            continue
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = RAW_DIR / f"{stamp}_{re.sub(r'[^\w-]', '_', url[-40:])}.html"
        fname.write_text(page.content(), encoding="utf-8")
        return True
    return False


def collect_category(browser, cfg, cat_cfg):
    """采集单个类目（支持翻页），返回商品卡片列表"""
    name, base_url = cat_cfg["name"], cat_cfg["url"]
    delay = cfg["delay_seconds"]
    context = browser.new_context(
        user_agent=UA, viewport={"width": 1366, "height": 900}, locale="en-US"
    )
    page = context.new_page()
    all_cards = []
    for page_no in range(1, cfg["max_pages"] + 1):
        url = f"{base_url}?pg={page_no}" if page_no > 1 else base_url
        if not _fetch_with_retry(page, url, delay):
            logger.error("%s 连续 %s 次失败，终止该类目", name, 3)
            break
        cards = parse_cards(page)
        if not cards:
            logger.warning(
                "%s 第 %s 页未解析出商品（可能改版或拦截，原始 HTML 已存档到 data/raw）",
                name, page_no,
            )
            break
        logger.info("%s 第 %s 页解析 %s 个商品", name, page_no, len(cards))
        all_cards.extend(cards)
        if page_no < cfg["max_pages"]:
            time.sleep(random.uniform(*delay))
    context.close()
    return all_cards


def save_to_db(cards, category):
    """商品维度 upsert + 快照追加"""
    session = get_session()
    now = datetime.now()
    new_products = 0
    try:
        for c in cards:
            product = session.get(DimProduct, c["asin"])
            if product is None:
                product = DimProduct(
                    asin=c["asin"], title=c["title"] or "未知",
                    category=category, url=c["url"],
                )
                session.add(product)
                new_products += 1
            elif c["title"]:
                product.title = c["title"]
            session.add(FactSnapshot(
                asin=c["asin"], captured_at=now, position=c["rank"],
                price=c["price"], rating=c["rating"], review_count=c["reviews"],
            ))
        session.commit()
    finally:
        session.close()
    logger.info("落库完成: %s 条快照，新增商品 %s 个", len(cards), new_products)


def run_all(headless=True):
    """采集配置中的全部类目并落库"""
    cfg = load_config()["collect"]
    total = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        for cat in cfg["categories"]:
            cards = collect_category(browser, cfg, cat)
            save_to_db(cards, cat["name"])
            total += len(cards)
        browser.close()
    logger.info("本轮采集完成: 共 %s 条快照", total)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="采集亚马逊 Best Sellers 榜单")
    parser.add_argument("--headful", action="store_true", help="显示浏览器窗口，便于调试")
    args = parser.parse_args()
    run_all(headless=args.headful)
