const { contextBridge, ipcRenderer } = require("electron");
contextBridge.exposeInMainWorld("cadkit", {
  load: () => ipcRenderer.invoke("cadkit:load"),
  rebuild: () => ipcRenderer.invoke("cadkit:rebuild"),
  measure: (params) => ipcRenderer.invoke("cadkit:measure", params),
  exportPart: (name) => ipcRenderer.invoke("cadkit:export", name),
  openLink: (url) => ipcRenderer.invoke("cadkit:open-link", url),
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
