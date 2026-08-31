"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  fetchBrokerStatus,
  fetchPositions,
  fetchFunds,
  fetchOrders,
  placeOrder,
  cancelOrder,
  type PlaceOrderRequest,
} from "@/lib/api";

export default function BrokerPage() {
  const { data: status } = useSWR("/api/broker/status", fetchBrokerStatus, { keepPreviousData: true });
  const { data: fundsData, mutate: mutateFunds } = useSWR("/api/broker/funds", fetchFunds, { refreshInterval: 60000, keepPreviousData: true });
  const { data: positionsData, mutate: mutatePositions } = useSWR("/api/broker/positions", fetchPositions, { refreshInterval: 60000, keepPreviousData: true });
  const { data: ordersData, mutate: mutateOrders } = useSWR("/api/broker/orders", fetchOrders, { refreshInterval: 60000, keepPreviousData: true });

  const [symbol, setSymbol] = useState("RELIANCE");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [qty, setQty] = useState(1);
  const [orderType, setOrderType] = useState("MARKET");
  const [product, setProduct] = useState("CNC");
  const [limitPrice, setLimitPrice] = useState("");
  const [placing, setPlacing] = useState(false);
  const [orderResult, setOrderResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const connected = status?.connected || false;
  const positions = positionsData?.positions || [];
  const orders = ordersData?.orders || [];

  const handlePlaceOrder = async () => {
    setPlacing(true);
    setError(null);
    setOrderResult(null);
    try {
      const req: PlaceOrderRequest = {
        symbol: symbol.toUpperCase(),
        side,
        quantity: qty,
        order_type: orderType as PlaceOrderRequest["order_type"],
        product: product as PlaceOrderRequest["product"],
      };
      if (orderType === "LIMIT" && limitPrice) {
        req.limit_price = parseFloat(limitPrice);
      }
      const res = await placeOrder(req);
      if (res.status === "success") {
        setOrderResult(`✅ Order placed: ${res.order_id || "OK"}`);
      } else if (res.status === "simulated") {
        setOrderResult(`⚠ Simulated (mock broker): ${res.message}`);
      } else {
        setError(`❌ ${res.message}`);
      }
      mutateOrders();
      mutatePositions();
      mutateFunds();
    } catch (e: any) {
      setError(e.message || "Failed to place order");
    } finally {
      setPlacing(false);
    }
  };

  const handleCancel = async (orderId: string) => {
    try {
      await cancelOrder(orderId);
      mutateOrders();
    } catch (e: any) {
      setError(e.message || "Failed to cancel order");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Broker Integration</h1>
        <p className="text-sm text-slate-500 mt-1">
          Place real orders, view positions, and check funds through your Fyers account.
        </p>
      </div>

      {/* Connection Status */}
      <div className="glass-card p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${connected ? "bg-emerald-400" : "bg-slate-600"}`} />
          <div>
            <div className="text-sm font-semibold text-slate-200">
              {status?.broker?.toUpperCase() || "Mock"} Broker
            </div>
            <div className="text-xs text-slate-500">{status?.message}</div>
          </div>
        </div>
      </div>

      {/* Funds */}
      {fundsData && !fundsData.error && (
        <div className="grid grid-cols-3 gap-3">
          <div className="glass-card p-3">
            <div className="text-xs text-slate-500">Available Balance</div>
            <div className="text-lg font-bold text-emerald-400 tabular-nums">
              ₹{(fundsData.available_balance || 0).toLocaleString("en-IN")}
            </div>
          </div>
          <div className="glass-card p-3">
            <div className="text-xs text-slate-500">Used Margin</div>
            <div className="text-lg font-bold text-amber-400 tabular-nums">
              ₹{(fundsData.used_margin || 0).toLocaleString("en-IN")}
            </div>
          </div>
          <div className="glass-card p-3">
            <div className="text-xs text-slate-500">Total Balance</div>
            <div className="text-lg font-bold text-slate-200 tabular-nums">
              ₹{(fundsData.total_balance || 0).toLocaleString("en-IN")}
            </div>
          </div>
        </div>
      )}

      {/* Place Order */}
      <div className="glass-card p-4 space-y-4">
        <div className="text-sm font-semibold text-slate-300">Place Order</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-slate-500 block mb-1">Symbol</label>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Side</label>
            <div className="flex gap-1">
              {(["buy", "sell"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setSide(s)}
                  className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium ${
                    side === s
                      ? s === "buy" ? "bg-emerald-600 text-white" : "bg-rose-600 text-white"
                      : "bg-slate-800 text-slate-400"
                  }`}
                >
                  {s.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Quantity</label>
            <input
              type="number"
              value={qty}
              onChange={(e) => setQty(parseInt(e.target.value) || 1)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Order Type</label>
            <select
              value={orderType}
              onChange={(e) => setOrderType(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
            >
              <option value="MARKET">Market</option>
              <option value="LIMIT">Limit</option>
              <option value="SL">Stop Loss</option>
              <option value="SL-M">SL Market</option>
            </select>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-500 block mb-1">Product</label>
            <select
              value={product}
              onChange={(e) => setProduct(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700"
            >
              <option value="CNC">CNC (Delivery)</option>
              <option value="MIS">MIS (Intraday)</option>
              <option value="NRML">NRML (Carry)</option>
            </select>
          </div>
          {orderType === "LIMIT" && (
            <div>
              <label className="text-xs text-slate-500 block mb-1">Limit Price</label>
              <input
                type="number"
                step="0.05"
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
              />
            </div>
          )}
        </div>
        {!connected && (
          <div className="text-xs text-amber-400 bg-amber-900/20 p-2 rounded-lg">
            ⚠ Mock broker is active. Orders will be simulated, not placed on the exchange.
            Configure Fyers credentials in backend/.env to enable real trading.
          </div>
        )}
        {orderResult && <div className="text-sm text-emerald-400">{orderResult}</div>}
        {error && <div className="text-sm text-rose-400">{error}</div>}
        <div className="flex justify-end">
          <button
            onClick={handlePlaceOrder}
            disabled={placing}
            className={`px-6 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50 ${
              side === "buy" ? "bg-emerald-600 hover:bg-emerald-500" : "bg-rose-600 hover:bg-rose-500"
            }`}
          >
            {placing ? "Placing..." : `Place ${side.toUpperCase()} Order`}
          </button>
        </div>
      </div>

      {/* Positions */}
      <div>
        <div className="text-sm font-semibold text-slate-300 mb-2">Open Positions ({positions.length})</div>
        {positions.length === 0 ? (
          <div className="glass-card p-4 text-center">
            <p className="text-xs text-slate-500">No open positions.</p>
          </div>
        ) : (
          <div className="glass-card overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="px-3 py-2 text-left font-medium">Symbol</th>
                  <th className="px-3 py-2 text-left font-medium">Side</th>
                  <th className="px-3 py-2 text-right font-medium">Qty</th>
                  <th className="px-3 py-2 text-right font-medium">Avg Price</th>
                  <th className="px-3 py-2 text-right font-medium">LTP</th>
                  <th className="px-3 py-2 text-right font-medium">P&L</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p, i) => (
                  <tr key={i} className="border-b border-slate-800/40">
                    <td className="px-3 py-2.5 text-slate-200">{p.symbol}</td>
                    <td className={`px-3 py-2.5 ${p.side === "long" ? "text-emerald-400" : "text-rose-400"}`}>{p.side}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{p.quantity}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">₹{p.avg_price}</td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">₹{p.current_price}</td>
                    <td className={`px-3 py-2.5 text-right tabular-nums font-semibold ${p.pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      ₹{p.pnl.toLocaleString("en-IN")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Today's Orders */}
      {orders.length > 0 && (
        <div>
          <div className="text-sm font-semibold text-slate-300 mb-2">Today&apos;s Orders ({orders.length})</div>
          <div className="glass-card overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="px-3 py-2 text-left font-medium">Order ID</th>
                  <th className="px-3 py-2 text-left font-medium">Symbol</th>
                  <th className="px-3 py-2 text-left font-medium">Side</th>
                  <th className="px-3 py-2 text-right font-medium">Qty</th>
                  <th className="px-3 py-2 text-left font-medium">Status</th>
                  <th className="px-3 py-2 text-right font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {orders.slice(0, 20).map((o: any, i: number) => (
                  <tr key={i} className="border-b border-slate-800/40">
                    <td className="px-3 py-2.5 text-slate-400 text-[10px]">{o.id || o.orderId}</td>
                    <td className="px-3 py-2.5 text-slate-200">{(o.symbol || "").replace("NSE:", "").replace("-EQ", "")}</td>
                    <td className={`px-3 py-2.5 ${o.side === 1 || o.side === "buy" ? "text-emerald-400" : "text-rose-400"}`}>
                      {o.side === 1 || o.side === "buy" ? "BUY" : "SELL"}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums text-slate-300">{o.qty || o.quantity}</td>
                    <td className="px-3 py-2.5 text-slate-400">{o.status || o.orderStatus || "—"}</td>
                    <td className="px-3 py-2.5 text-right">
                      {(o.status === 1 || (o.statusDescription || "").toLowerCase() === "pending" || (o.statusDescription || "").toLowerCase() === "open") && (
                        <button
                          onClick={() => handleCancel(o.id || o.orderId)}
                          className="text-xs text-rose-400 hover:text-rose-300"
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
