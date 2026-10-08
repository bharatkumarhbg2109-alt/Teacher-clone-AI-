const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  onStatusUpdate: (callback) =>
    ipcRenderer.on('status-update', (_, data) => callback(data)),
  onProgressUpdate: (callback) =>
    ipcRenderer.on('progress-update', (_, data) => callback(data)),
});
