const { contextBridge } = require('electron');
contextBridge.exposeInMainWorld('helApp', { version: '1.2.0' });
