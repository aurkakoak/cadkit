export type VisibilityState = {
  components: Set<string>;
  hidden: Set<string>;
  isolation: { ids: Set<string>; previousHidden: Set<string> } | null;
};

type VisibilityAction =
  | { type: "reconcile"; ids: string[] }
  | { type: "isolate" | "toggle" | "show" | "hide"; ids: string[] }
  | { type: "showAll" };

export const initialVisibility: VisibilityState = {
  components: new Set(),
  hidden: new Set(),
  isolation: null,
};

export const isIsolated = (state: VisibilityState, ids: string[]) => {
  const targets = new Set(ids);
  return Boolean(
    state.isolation &&
    targets.size === state.isolation.ids.size &&
    [...targets].every((id) => state.isolation!.ids.has(id)),
  );
};

export function visibilityReducer(
  state: VisibilityState,
  action: VisibilityAction,
): VisibilityState {
  if (action.type === "showAll")
    return { ...state, hidden: new Set(), isolation: null };

  if (action.type === "reconcile") {
    const components = new Set(action.ids);
    const surviving = (ids: Set<string>) =>
      new Set([...ids].filter((id) => components.has(id)));
    const hidden = surviving(state.hidden);
    if (!state.isolation) return { components, hidden, isolation: null };
    const ids = surviving(state.isolation.ids);
    const previousHidden = surviving(state.isolation.previousHidden);
    if (!ids.size)
      return { components, hidden: previousHidden, isolation: null };
    // New geometry stays outside solo; existing eye adjustments survive a rebuild.
    for (const id of components) if (!state.components.has(id)) hidden.add(id);
    return { components, hidden, isolation: { ids, previousHidden } };
  }

  const ids = new Set(action.ids.filter((id) => state.components.has(id)));
  if (!ids.size) return state;
  if (action.type === "isolate") {
    if (isIsolated(state, [...ids]))
      return {
        ...state,
        hidden: state.isolation!.previousHidden,
        isolation: null,
      };
    return {
      ...state,
      hidden: new Set([...state.components].filter((id) => !ids.has(id))),
      isolation: {
        ids,
        previousHidden: state.isolation?.previousHidden ?? state.hidden,
      },
    };
  }

  const hidden = new Set(state.hidden);
  const show =
    action.type === "show" ||
    (action.type === "toggle" && [...ids].every((id) => hidden.has(id)));
  for (const id of ids) show ? hidden.delete(id) : hidden.add(id);
  // Eye changes during solo are temporary; its original visibility is retained.
  return { ...state, hidden };
}
