import { z } from "zod";

const vector = z.tuple([
  z.number().finite(),
  z.number().finite(),
  z.number().finite(),
]);
const revision = z
  .string()
  .min(1)
  .describe(
    "Build revision returned by get_state. Stale geometry commands are rejected.",
  );
const ids = z.array(z.string().min(1)).max(100);
const color = z
  .string()
  .regex(/^#[0-9a-fA-F]{6}$/)
  .default("#f1c789");
const conceptKind = z.enum(["joint", "interface", "fastening"]);
const validationOverride = z
  .string()
  .trim()
  .min(3)
  .max(1000)
  .optional()
  .describe(
    "Explicit reason for exporting despite assembly failures; saved with the artifact report. Read mechanical_report first.",
  );
export const definitions = {
  set_variants: {
    description:
      "Select design alternatives from get_state.project.variants. Builds or restores a cached configuration and returns its new revision. Unspecified choices retain their current values.",
    schema: z.object({ revision, selection: z.record(z.string(), z.string()) }),
  },
  mechanical_report: {
    description:
      "Validate native installed assembly collisions, Joint/Interface/Fastening contracts, fastener stacks and declared access. Returns revision-scoped findings, bounded intended contact, and explicit unverified coverage. Optional Parts restrict findings to a print set while retaining full assembly context. Does not establish loaded strength or every possible insertion path.",
    schema: z.object({
      revision,
      parts: z.array(z.string().min(1)).min(1).max(100).optional(),
      scan_collisions: z.boolean().default(true),
    }),
  },
  inspect_connection: {
    description:
      "Inspect a first-class joint, interface or fastening by its ID from get_state.mechanics: resolved component references, hardware stack, BOM and declared limits. These are engineering definitions; hardware previews do not change native geometry.",
    schema: z.object({ revision, kind: conceptKind, id: z.string().min(1) }),
  },
  select_connection: {
    description:
      "Select a Joint, Interface or Fastening in the app inspector and highlight its participants. Optional focus frames the relationship. Uses IDs from get_state.mechanics.",
    schema: z.object({
      revision,
      kind: conceptKind,
      id: z.string().min(1),
      focus: z.boolean().default(false),
    }),
  },
  set_hardware_view: {
    description:
      "Show all generated fasteners, hide them, or show only the selected fastening. previewProgress 0..1 displaces hardware along declared insertion offsets for presentation; 0 restores installed geometry. This is not an assembly-path proof. Reset to 0 for native measurements.",
    schema: z.object({
      revision,
      mode: z.enum(["all", "hidden", "selected"]).optional(),
      previewProgress: z.number().finite().min(0).max(1).optional(),
    }),
  },
  get_state: {
    description:
      "Read the live UI: project, Parts, assembly tree, component IDs, first-class joints/interfaces/fastenings and hardware BOM (mechanics), selected connection/Part/objects, hardware display/assembly preview, validation, visibility, highlights, measurement, camera and annotations. Geometry is in world millimetres; no triangle payload.",
    schema: z.object({}),
  },
  inspect: {
    description:
      "Inspect component IDs or a Part definition, including material, print pose, bounds and volume. With no arguments, inspect the current UI selection.",
    schema: z.object({ ids: ids.optional(), part: z.string().optional() }),
  },
  select: {
    description:
      "Select up to two installed components, or a Part definition in the inspector. Empty IDs clear selection.",
    schema: z
      .object({
        revision,
        ids: ids.max(2).optional(),
        part: z.string().optional(),
      })
      .refine((p) => !(p.ids && p.part), "Choose IDs or a Part"),
  },
  visibility: {
    description:
      "Show, hide or solo component/assembly IDs. Isolate toggles: the same expanded IDs again restore previous visibility; switching targets retains the original visibility to restore. Eye/show/hide changes during solo are temporary. Show with no IDs exits solo and shows everything. Assembly IDs include their descendants. get_state.isolation reports active IDs and previousHidden, or null.",
    schema: z.object({
      revision,
      action: z.enum(["show", "hide", "isolate"]),
      ids: ids.default([]),
    }),
  },
  highlight: {
    description:
      "Highlight component or assembly bounds without changing the user's selection. Replaces previous highlights; empty IDs clear them.",
    schema: z.object({ revision, ids, color }),
  },
  camera: {
    description:
      "Read or change the live camera. Presets use Z-up world coordinates. fit frames visible objects; zoom is an absolute positive scale. pose restores a camera returned by get_state.",
    schema: z.object({
      preset: z
        .enum(["iso", "front", "rear", "left", "right", "top", "bottom"])
        .optional(),
      fit: z.boolean().optional(),
      zoom: z.number().min(0.001).max(10000).optional(),
      pose: z
        .object({
          position: vector,
          quaternion: z
            .tuple([z.number(), z.number(), z.number(), z.number()])
            .refine(
              (q) => Math.abs(Math.hypot(...q) - 1) < 0.01,
              "Quaternion must have unit length",
            ),
          target: vector,
          zoom: z.number().min(0.001).max(10000),
        })
        .optional(),
    }),
  },
  measure: {
    description:
      "Calculate minimum clearance between two installed components using original CAD geometry. Returns closest points for native solids and marks mesh approximations. show=true also selects the pair and displays the dimension in the UI. Zero may mean contact or overlap.",
    schema: z.object({
      revision,
      ids: z.tuple([z.string(), z.string()]),
      show: z.boolean().default(true),
    }),
  },
  annotate: {
    description:
      "Add or replace a Markdown annotation card by ID. Supply target (component/assembly ID) to attach it to the model and assembly tree, or point for a free annotation. World coordinates are mm; screen coordinates are [0..1,0..1,0]. from positions the card in the same coordinate space; offset overrides it with [dx,dy] screen pixels from the anchor. Long text collapses with an expand control. Target-only notes follow stable IDs across rebuilds; explicit coordinate notes clear on rebuild.",
    schema: z
      .object({
        revision,
        id: z.string().min(1).max(80),
        text: z.string().max(8000).default(""),
        space: z.enum(["world", "screen"]).default("world"),
        point: vector.optional(),
        target: z.string().min(1).optional(),
        offset: z
          .tuple([
            z.number().min(-5000).max(5000),
            z.number().min(-5000).max(5000),
          ])
          .optional(),
        from: vector.optional(),
        color,
      })
      .superRefine((p, ctx) => {
        if (!p.point && !p.target)
          ctx.addIssue({
            code: "custom",
            message: "Supply a point or target ID",
          });
        if (p.target && p.space === "screen")
          ctx.addIssue({
            code: "custom",
            message: "Target annotations use world coordinates",
          });
        if (
          p.space === "screen" &&
          [p.point, p.from]
            .filter(Boolean)
            .some(
              (v) => v[0] < 0 || v[0] > 1 || v[1] < 0 || v[1] > 1 || v[2] !== 0,
            )
        )
          ctx.addIssue({
            code: "custom",
            message: "Screen coordinates must be [0..1, 0..1, 0]",
          });
      }),
  },
  clear_annotations: {
    description:
      "Remove one annotation by ID, or all annotations when omitted.",
    schema: z.object({ id: z.string().optional() }),
  },
  screenshot: {
    description:
      "Capture the live app or viewport, including annotations, as a PNG image the agent can view. Does not capture other applications.",
    schema: z.object({
      target: z.enum(["viewport", "window"]).default("viewport"),
      max_width: z.number().int().min(320).max(2400).default(1600),
    }),
  },
  slicer_settings: {
    description:
      "Read the slicer executable, selected profiles and readiness. Configure these in the app's Print panel.",
    schema: z.object({}),
  },
  slice_parts: {
    description:
      "Export named Parts in their print poses and start a headless slicer job using the app's saved profiles. Returns a job ID; poll slice_status for estimates/artifacts. Does not send to a printer.",
    schema: z.object({
      revision,
      parts: z.array(z.string()).min(1).max(100),
      validation_override: validationOverride,
    }),
  },
  prepare_parts: {
    description:
      "Export named Parts as print-oriented STLs and open them in the configured slicer for manual setup. No slicing or printing is started.",
    schema: z.object({
      revision,
      parts: z.array(z.string()).min(1).max(100),
      validation_override: validationOverride,
    }),
  },
  slice_status: {
    description:
      "Read a slicer job's progress, estimates, report and generated G-code/3MF paths; omit ID to list jobs.",
    schema: z.object({ id: z.string().optional() }),
  },
  cancel_slice: {
    description: "Cancel a running slice job and its slicer process.",
    schema: z.object({ id: z.string() }),
  },
  open_in_slicer: {
    description:
      "Open a completed job's sliced artifacts in the configured slicer application for review. Does not print.",
    schema: z.object({ id: z.string() }),
  },
};

export function validateCommand(method, params) {
  const definition = definitions[method];
  if (!definition) throw new Error(`Unknown operation: ${method}`);
  return definition.schema.parse(params ?? {});
}
