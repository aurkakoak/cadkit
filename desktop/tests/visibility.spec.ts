import { test, expect } from "@playwright/test";
import {
  initialVisibility,
  visibilityReducer as reduce,
} from "../src/visibility";

test("solo survives new geometry and restores visibility when its last target disappears", () => {
  let state = reduce(initialVisibility, {
    type: "reconcile",
    ids: ["a", "b", "c"],
  });
  state = reduce(state, { type: "hide", ids: ["b"] });
  state = reduce(state, { type: "isolate", ids: ["a", "c"] });
  state = reduce(state, { type: "reconcile", ids: ["a", "b", "d"] });
  expect([...state.hidden]).toEqual(["b", "d"]);
  expect([...state.isolation!.ids]).toEqual(["a"]);
  state = reduce(state, { type: "reconcile", ids: ["b", "d"] });
  expect([...state.hidden]).toEqual(["b"]);
  expect(state.isolation).toBeNull();
});

test("eye changes during solo are temporary and never mutate its saved visibility", () => {
  let state = reduce(initialVisibility, {
    type: "reconcile",
    ids: ["a", "b", "c"],
  });
  state = reduce(state, { type: "hide", ids: ["b"] });
  state = reduce(state, { type: "isolate", ids: ["b"] });
  state = reduce(state, { type: "toggle", ids: ["a"] });
  state = reduce(state, { type: "hide", ids: ["b"] });
  state = reduce(state, { type: "reconcile", ids: ["a", "b", "c"] });
  expect([...state.hidden].sort()).toEqual(["b", "c"]);
  state = reduce(state, { type: "isolate", ids: ["b"] });
  expect([...state.hidden]).toEqual(["b"]);
  expect(state.isolation).toBeNull();
});
