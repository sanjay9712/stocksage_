"""Tax-loss harvesting suggestions.

Analyzes holdings for tax-loss harvesting opportunities: identifies losers
that can be sold to offset gains, and suggests replacement stocks to maintain
market exposure (avoiding wash-sale by picking different but correlated
securities).

Wash-sale rule: cannot repurchase the same or "substantially identical"
security within 30 days. So we suggest sector ETFs or similar stocks as
replacements.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.auth import require_token
from app.api.cache import cached
from app.holdings.factory import get_broker
from app.providers.factory import get_provider
from app import indicators as ind

router = APIRouter()

# Sector ETF replacements for common stocks (to avoid wash-sale)
SECTOR_ETF_REPLACEMENTS = {
    "RELIANCE": "NIFTYBEES",
    "TCS": "ITBEES",
    "INFY": "ITBEES",
    "HDFCBANK": "BANKBEES",
    "ICICIBANK": "BANKBEES",
    "SBIN": "BANKBEES",
    "TATAMOTORS": "NIFTYBEES",
    "AAPL": "XLK",
    "MSFT": "XLK",
    "GOOGL": "XLK",
    "AMZN": "XLY",
    "META": "XLK",
    "NVDA": "XLK",
    "TSLA": "XLY",
    "JPM": "XLF",
    "BAC": "XLF",
    "V": "XLF",
    "JNJ": "XLV",
    "PFE": "XLV",
    "XOM": "XLE",
}


@router.get("/tax-harvest")
async def tax_harvest(_t=Depends(require_token)):
    """Analyze holdings for tax-loss harvesting opportunities.

    For each losing position, calculates:
    - Unrealized loss (absolute + %)
    - Tax savings (at 15% STCG or 10% LTCG rate)
    - Suggested replacement (sector ETF to maintain exposure)
    - Wash-sale warning period (30 days)
    """
    async def _fetch():
        broker = get_broker()
        holdings = await broker.get_holdings()
        provider = get_provider()

        losers = [h for h in holdings if h.pnl < 0]
        gainers = [h for h in holdings if h.pnl > 0]

        total_losses = sum(abs(h.pnl) for h in losers)
        total_gains = sum(h.pnl for h in gainers)

        # Net taxable gain (if gains > losses, harvesting saves tax on the difference)
        net_gain = total_gains - total_losses

        opportunities = []
        for h in losers:
            loss_pct = (h.pnl / (h.avg_price * h.quantity)) * 100 if h.avg_price > 0 else 0
            # Short-term if held < 12 months (15% tax), long-term if > 12 months (10% tax)
            # We don't have purchase date, so estimate based on avg price vs current
            # Assume short-term for conservative estimate
            tax_rate = 0.15  # STCG
            tax_savings = abs(h.pnl) * tax_rate

            replacement = SECTOR_ETF_REPLACEMENTS.get(h.symbol.upper(), "NIFTYBEES")

            opportunities.append({
                "symbol": h.symbol,
                "quantity": h.quantity,
                "avg_price": round(h.avg_price, 2),
                "current_price": round(h.current_price, 2),
                "unrealized_loss": round(abs(h.pnl), 2),
                "loss_pct": round(loss_pct, 2),
                "estimated_tax_saving": round(tax_savings, 2),
                "replacement_symbol": replacement,
                "wash_sale_period": "30 days — do not repurchase same security",
                "action": f"Sell {h.symbol} to book loss of ₹{abs(h.pnl):.0f}, replace with {replacement} to maintain sector exposure",
            })

        opportunities.sort(key=lambda d: d["unrealized_loss"], reverse=True)

        # Offset analysis
        offsettable = min(total_losses, total_gains)
        tax_saved_offset = offsettable * 0.15  # STCG rate

        return {
            "total_holdings": len(holdings),
            "losing_positions": len(losers),
            "gaining_positions": len(gainers),
            "total_unrealized_losses": round(total_losses, 2),
            "total_unrealized_gains": round(total_gains, 2),
            "net_taxable_gain": round(net_gain, 2),
            "offsettable_losses": round(offsettable, 2),
            "estimated_tax_saving_from_offset": round(tax_saved_offset, 2),
            "opportunities": opportunities,
            "summary": (
                f"You have {len(losers)} losing positions with ₹{total_losses:.0f} total losses. "
                f"Harvesting these losses can offset ₹{offsettable:.0f} of gains, "
                f"saving approximately ₹{tax_saved_offset:.0f} in taxes."
                if losers else "No losing positions to harvest."
            ),
        }

    return await cached("tax_harvest", 300, _fetch)
