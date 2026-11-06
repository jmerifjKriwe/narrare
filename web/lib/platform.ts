/** True on Apple platforms, where the command key is the keyboard's ⌘. */
export function isMac(): boolean {
  return /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
}
