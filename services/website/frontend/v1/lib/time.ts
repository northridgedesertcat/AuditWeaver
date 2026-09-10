export function formatTimestamp(epochMs: number): string {
  if (!epochMs || isNaN(epochMs)) return "未知时间";
  const date = new Date(epochMs);
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function formatRelative(epochMs: number): string {
  if (!epochMs || isNaN(epochMs)) return "未知时间";
  const now = Date.now();
  const diff = now - epochMs;

  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  if (hours < 24) return `${hours} 小时前`;
  if (days < 7) return `${days} 天前`;

  return formatDate(epochMs);
}

export function formatDate(epochMs: number): string {
  if (!epochMs || isNaN(epochMs)) return "未知时间";
  const date = new Date(epochMs);
  return date.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function formatTimeOnly(epochMs: number): string {
  if (!epochMs || isNaN(epochMs)) return "--:--";
  const date = new Date(epochMs);
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateTimeShort(epochMs: number): string {
  if (!epochMs || isNaN(epochMs)) return "未知时间";
  const date = new Date(epochMs);
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}