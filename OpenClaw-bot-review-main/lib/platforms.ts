export function shouldHidePlatformChannel(
  channelName: string,
  channels: Record<string, any>
): boolean {
  return channelName === "wechat-access" && !!channels.wecom && channels.wecom.enabled !== false;
}

export function getPlatformDisplayName(channelName: string): string {
  return channelName === "wechat-access" ? "wecom" : channelName;
}
