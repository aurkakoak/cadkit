const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("cadkit", {
  load: () => ipcRenderer.invoke("cadkit:load"),
  launcherState: () => ipcRenderer.invoke("cadkit:launcher-state"),
  chooseProject: () => ipcRenderer.invoke("cadkit:choose-project"),
  openProject: (target) => ipcRenderer.invoke("cadkit:open-project", target),
  closeProject: () => ipcRenderer.invoke("cadkit:close-project"),
  createProject: (template) =>
    ipcRenderer.invoke("cadkit:create-project", template),
  pinProject: (id, pinned) =>
    ipcRenderer.invoke("cadkit:pin-project", id, pinned),
  removeProject: (id) => ipcRenderer.invoke("cadkit:remove-project", id),
  locateProject: (id) => ipcRenderer.invoke("cadkit:locate-project", id),
  pickProjectPython: () => ipcRenderer.invoke("cadkit:pick-project-python"),
  saveProjectPreview: (params) =>
    ipcRenderer.invoke("cadkit:save-project-preview", params),
  setVariants: (values) => ipcRenderer.invoke("cadkit:set-variants", values),
  warmVariants: (revision) =>
    ipcRenderer.invoke("cadkit:warm-variants", revision),
  rebuild: () => ipcRenderer.invoke("cadkit:rebuild"),
  measure: (params) => ipcRenderer.invoke("cadkit:measure", params),
  mechanicalReport: (params) =>
    ipcRenderer.invoke("cadkit:mechanical-report", params),
  exportPart: (name, validation_override) =>
    ipcRenderer.invoke("cadkit:export", name, validation_override),
  openLink: (url) => ipcRenderer.invoke("cadkit:open-link", url),
  renderAction: (action, params) =>
    ipcRenderer.invoke("cadkit:render-action", action, params),
  slicerSettings: () => ipcRenderer.invoke("cadkit:slicer-settings"),
  saveSlicer: (values) => ipcRenderer.invoke("cadkit:slicer-save", values),
  pickSlicerFile: (key) => ipcRenderer.invoke("cadkit:slicer-pick", key),
  slicerAction: (method, params) =>
    ipcRenderer.invoke("cadkit:slicer-action", method, params),
  revealSlice: (id) => ipcRenderer.invoke("cadkit:slicer-reveal", id),
  copyMcpConfig: () => ipcRenderer.invoke("cadkit:mcp-config"),
  onControl: (callback) => {
    const listener = async (_event, request) => {
      try {
        ipcRenderer.send("cadkit:control-result", {
          id: request.id,
          result: await callback(request),
        });
      } catch (error) {
        ipcRenderer.send("cadkit:control-result", {
          id: request.id,
          error: String(error.message ?? error),
        });
      }
    };
    ipcRenderer.on("cadkit:control", listener);
    return () => ipcRenderer.removeListener("cadkit:control", listener);
  },
  onEvent: (callback) => {
    const listener = (_event, value) => callback(value);
    ipcRenderer.on("cadkit:event", listener);
    return () => ipcRenderer.removeListener("cadkit:event", listener);
  },
});
