"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  fetchChannels,
  createChannel,
  deleteChannel,
  testNotification,
  type NotificationChannel,
} from "@/lib/api";

export default function NotificationsPage() {
  const { data, mutate } = useSWR("/api/notifications/channels", fetchChannels);
  const [channelType, setChannelType] = useState<"telegram" | "discord">("telegram");
  const [telegramToken, setTelegramToken] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [discordWebhook, setDiscordWebhook] = useState("");
  const [creating, setCreating] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);

  const channels = data?.channels || [];

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      if (channelType === "telegram") {
        if (!telegramToken || !telegramChatId) {
          setError("Telegram requires Bot Token and Chat ID");
          return;
        }
        await createChannel({
          channel_type: "telegram",
          config: { bot_token: telegramToken, chat_id: telegramChatId },
        });
        setTelegramToken("");
        setTelegramChatId("");
      } else {
        if (!discordWebhook) {
          setError("Discord requires Webhook URL");
          return;
        }
        await createChannel({
          channel_type: "discord",
          config: { webhook_url: discordWebhook },
        });
        setDiscordWebhook("");
      }
      mutate();
    } catch (e: any) {
      setError(e.message || "Failed to create channel");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteChannel(id);
      mutate();
    } catch (e: any) {
      setError(e.message || "Failed to delete channel");
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setError(null);
    setTestResult(null);
    try {
      const res = await testNotification();
      if (res.sent > 0) {
        setTestResult(`✅ Sent to ${res.sent}/${res.total} channel(s)`);
      } else {
        setTestResult("⚠ No channels received the test. Check your configuration.");
      }
    } catch (e: any) {
      setError(e.message || "Failed to send test notification");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Notifications</h1>
          <p className="text-sm text-slate-500 mt-1">
            Configure Telegram or Discord to receive trading alerts and daily digests.
          </p>
        </div>
        <button
          onClick={handleTest}
          disabled={testing || channels.length === 0}
          className="px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
        >
          {testing ? "Sending..." : "Send Test"}
        </button>
      </div>

      {testResult && (
        <div className="glass-card p-3 text-center">
          <p className="text-sm text-slate-300">{testResult}</p>
        </div>
      )}

      {error && <div className="glass-card p-4 text-center"><p className="text-rose-300 text-sm">{error}</p></div>}

      {/* Create Channel */}
      <div className="glass-card p-4 space-y-4">
        <div className="text-sm font-semibold text-slate-300">Add Notification Channel</div>
        <div className="flex gap-2">
          {(["telegram", "discord"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setChannelType(t)}
              className={`px-4 py-1.5 rounded-lg text-xs font-medium ${
                channelType === t ? "bg-emerald-600 text-white" : "bg-slate-800 text-slate-400"
              }`}
            >
              {t === "telegram" ? "Telegram" : "Discord"}
            </button>
          ))}
        </div>

        {channelType === "telegram" ? (
          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-500 block mb-1">Bot Token</label>
              <input
                type="password"
                value={telegramToken}
                onChange={(e) => setTelegramToken(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
                placeholder="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
              />
              <p className="text-[10px] text-slate-600 mt-1">
                Create a bot via <span className="text-sky-400">@BotFather</span> on Telegram to get a token.
              </p>
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Chat ID</label>
              <input
                type="text"
                value={telegramChatId}
                onChange={(e) => setTelegramChatId(e.target.value)}
                className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
                placeholder="123456789"
              />
              <p className="text-[10px] text-slate-600 mt-1">
                Message <span className="text-sky-400">@userinfobot</span> to get your Chat ID.
              </p>
            </div>
          </div>
        ) : (
          <div>
            <label className="text-xs text-slate-500 block mb-1">Webhook URL</label>
            <input
              type="text"
              value={discordWebhook}
              onChange={(e) => setDiscordWebhook(e.target.value)}
              className="w-full px-3 py-2 bg-slate-800 text-slate-100 rounded-lg text-sm border border-slate-700 focus:border-emerald-500 focus:outline-none"
              placeholder="https://discord.com/api/webhooks/..."
            />
            <p className="text-[10px] text-slate-600 mt-1">
              Go to Discord Server Settings → Integrations → Webhooks → New Webhook.
            </p>
          </div>
        )}

        <div className="flex justify-end">
          <button
            onClick={handleCreate}
            disabled={creating}
            className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium"
          >
            {creating ? "Adding..." : "Add Channel"}
          </button>
        </div>
      </div>

      {/* Existing Channels */}
      <div>
        <div className="text-sm font-semibold text-slate-300 mb-2">Configured Channels ({channels.length})</div>
        {channels.length === 0 ? (
          <div className="glass-card p-8 text-center">
            <p className="text-sm text-slate-500">No notification channels configured yet.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {channels.map((ch) => (
              <div key={ch.id} className="glass-card p-3 flex items-center gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      ch.channel_type === "telegram" ? "bg-sky-900/40 text-sky-400" : "bg-indigo-900/40 text-indigo-400"
                    }`}>
                      {ch.channel_type === "telegram" ? "Telegram" : "Discord"}
                    </span>
                    {ch.enabled ? (
                      <span className="text-[10px] text-emerald-400">● Active</span>
                    ) : (
                      <span className="text-[10px] text-slate-500">● Disabled</span>
                    )}
                  </div>
                  <div className="text-xs text-slate-500 mt-1">
                    {ch.channel_type === "telegram"
                      ? `Chat ID: ${ch.config.chat_id} · Token: ${ch.config.bot_token}`
                      : `Webhook: ${ch.config.webhook_url}`}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(ch.id)}
                  className="text-xs text-slate-500 hover:text-rose-400 px-2 py-1"
                >
                  Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
