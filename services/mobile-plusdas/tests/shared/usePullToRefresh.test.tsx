// The pull-to-refresh spinner follows only the user's pull: off by default (background polling
// never shows it), on while the pull's refresh runs, and off again even if that refresh fails.
import { act, renderHook } from "@testing-library/react-native";

import { usePullToRefresh } from "@/shared/lib/usePullToRefresh";

function deferred() {
  let resolve!: () => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<void>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("usePullToRefresh", () => {
  it("is off until the user pulls", async () => {
    const { result } = await renderHook(() => usePullToRefresh(() => Promise.resolve()));
    expect(result.current.refreshing).toBe(false);
  });

  it("is on while the pull's refresh runs, then off", async () => {
    const pending = deferred();
    const { result } = await renderHook(() => usePullToRefresh(() => pending.promise));
    let pull: Promise<void> = Promise.resolve();
    await act(async () => {
      pull = result.current.onRefresh();
    });
    expect(result.current.refreshing).toBe(true);
    await act(async () => {
      pending.resolve();
      await pull;
    });
    expect(result.current.refreshing).toBe(false);
  });

  it("turns off when the refresh fails", async () => {
    const pending = deferred();
    const { result } = await renderHook(() => usePullToRefresh(() => pending.promise));
    let pull: Promise<void> = Promise.resolve();
    await act(async () => {
      pull = result.current.onRefresh();
    });
    await act(async () => {
      pending.reject(new Error("offline"));
      await pull.catch(() => undefined);
    });
    expect(result.current.refreshing).toBe(false);
  });
});
