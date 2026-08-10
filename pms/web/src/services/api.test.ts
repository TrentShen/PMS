import { describe, expect, it } from "vitest";
import { formatError } from "./api";

describe("formatError", () => {
  it("detail 为字符串时直接返回", () => {
    const err = { response: { data: { detail: "评分必须是 0.25 的倍数" } } };
    expect(formatError(err, "操作失败")).toBe("评分必须是 0.25 的倍数");
  });

  it("detail 为 { errors: [...] } 时用全角分号拼接", () => {
    const err = { response: { data: { detail: { errors: ["姓名不能为空", "工号重复"] } } } };
    expect(formatError(err, "操作失败")).toBe("姓名不能为空；工号重复");
  });

  it("无 detail 时回退到 err.message，再回退到 fallback", () => {
    expect(formatError(new Error("Network Error"), "操作失败")).toBe("Network Error");
    expect(formatError({}, "操作失败")).toBe("操作失败");
  });
});
