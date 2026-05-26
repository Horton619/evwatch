import { app, shell, BrowserWindow, ipcMain } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import { ScrapeQueue } from './scrape-queue'
import {
  configureUpdater,
  checkForUpdates,
  downloadUpdate,
  installUpdate,
} from './updater'
import { probeVenv } from './venv'

let mainWindow: BrowserWindow | null = null
const scrapeQueue = new ScrapeQueue()

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 1024,
    minHeight: 640,
    show: false,
    autoHideMenuBar: true,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#070910',
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
    },
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

function wireIpc(): void {
  ipcMain.handle('app:get-version', () => ({
    version: app.getVersion(),
    venv: probeVenv(),
  }))

  ipcMain.handle('scrape:start', async (_e, args: { mode: 'all' | 'blocked' }) => {
    return scrapeQueue.start(args?.mode ?? 'all')
  })
  ipcMain.handle('scrape:cancel', () => scrapeQueue.cancel())
  ipcMain.handle('scrape:is-running', () => ({ running: scrapeQueue.isRunning() }))

  ipcMain.handle('update:check', () => checkForUpdates())
  ipcMain.handle('update:download', () => downloadUpdate())
  ipcMain.handle('update:install', () => {
    installUpdate()
    return { ok: true }
  })

  // Fan scrape events out to the renderer over typed channels.
  const send = (channel: string, payload: unknown) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send(channel, payload)
    }
  }
  scrapeQueue.on('status', (e) => send('scrape-status', e))
  scrapeQueue.on('log', (e) => send('scrape-log', e))
  scrapeQueue.on('batch-complete', (e) => send('scrape-batch-complete', e))
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId('net.veproductions.evwatch')
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  wireIpc()
  configureUpdater(() => mainWindow)
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
