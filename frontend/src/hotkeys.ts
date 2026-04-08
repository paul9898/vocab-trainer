export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  const tagName = target.tagName;
  return (
    target.isContentEditable ||
    tagName === "INPUT" ||
    tagName === "TEXTAREA"
  );
}


export function shouldIgnoreHotkey(event: KeyboardEvent): boolean {
  return event.metaKey || event.ctrlKey || event.altKey || event.repeat;
}


export function getAnswerHotkeyIndex(event: KeyboardEvent): number | null {
  const byCode: Record<string, number> = {
    Digit1: 0,
    Digit2: 1,
    Digit3: 2,
    Digit4: 3,
    Numpad1: 0,
    Numpad2: 1,
    Numpad3: 2,
    Numpad4: 3,
    KeyA: 0,
    KeyS: 1,
    KeyD: 2,
    KeyF: 3,
    ArrowUp: 0,
    ArrowRight: 1,
    ArrowLeft: 2,
    ArrowDown: 3,
  };

  if (event.code in byCode) {
    return byCode[event.code];
  }

  if (["1", "2", "3", "4"].includes(event.key)) {
    return Number(event.key) - 1;
  }

  const keyCodeMap: Record<number, number> = {
    49: 0,
    50: 1,
    51: 2,
    52: 3,
    97: 0,
    98: 1,
    99: 2,
    100: 3,
  };

  if (event.keyCode in keyCodeMap) {
    return keyCodeMap[event.keyCode];
  }

  if (event.which in keyCodeMap) {
    return keyCodeMap[event.which];
  }

  return null;
}


export function matchesHotkey(event: KeyboardEvent, code: string, key?: string): boolean {
  const keyCodeMap: Record<string, number[]> = {
    Enter: [13],
    Escape: [27],
    Space: [32],
    KeyH: [72],
    KeyR: [82],
  };

  return (
    event.code === code ||
    (key !== undefined && event.key.toLowerCase() === key.toLowerCase()) ||
    Boolean(keyCodeMap[code]?.includes(event.keyCode)) ||
    Boolean(keyCodeMap[code]?.includes(event.which))
  );
}


export function describeKeyEvent(event: KeyboardEvent): string {
  return `key=${event.key || "?"} code=${event.code || "?"} keyCode=${event.keyCode || 0} which=${event.which || 0}`;
}
