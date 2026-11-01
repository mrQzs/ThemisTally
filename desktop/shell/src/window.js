"use strict";

const crypto = require("node:crypto");

function partitionName() {
  return crypto.randomUUID();
}

function webPreferences(partition) {
  return {
    contextIsolation: true,
    sandbox: true,
    nodeIntegration: false,
    webSecurity: true,
    allowRunningInsecureContent: false,
    webviewTag: false,
    nodeIntegrationInWorker: false,
    nodeIntegrationInSubFrames: false,
    spellcheck: false,
    partition,
  };
}

function isServiceUrl(url, origin) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return false;
  }
  return parsed.origin === origin;
}

module.exports = { partitionName, webPreferences, isServiceUrl };
