"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { app, BrowserWindow, session, Menu, ipcMain, shell, dialog, Notification, protocol, nativeTheme } = require("electron");
const { runShell } = require("./src/core.js");
const { partitionName, backgroundFor, webPreferences, mainWebPreferences, isServiceUrl, trackWindow } = require("./src/window.js");
const { createHost } = require("./src/host.js");
const { registerHostIpc, HOST_APPEARANCE_CHANNEL, HOST_APPEARANCE_EVENT } = require("./src/ipc.js");
const { launchMode } = require("./src/launch.js");
const { resolveShellAsset, isShellPageUrl } = require("./src/shellprotocol.js");
const {
  registerShellIpc,
  shellSenderAllowed,
  SERVICE_STATE_CHANNEL,
  SHELL_APPEARANCE_CHANNEL,
  SHELL_APPEARANCE_EVENT,
} = require("./src/shellipc.js");
const { createShellApi } = require("./src/shellapi.js");
const { createSettingsStore, appearanceOf } = require("./src/settings.js");
const { createServiceFlow } = require("./src/serviceflow.js");
const { createHostRelay } = require("./src/hostrelay.js");
const { SHELL_START_URL, SHELL_STATUS_URL } = require("./src/shellprotocol.js");

Menu.setApplicationMenu(null);

// themis-shell 协议登记成特权 scheme：只此一处、放在两个分支都经过的位置；privileges 只要 standard 与 secure
protocol.registerSchemesAsPrivileged([{ scheme: "themis-shell", privileges: { standard: true, secure: true } }]);

// 两种窗口走同一个建窗工厂：权限拒绝、新窗口拒绝与 will-navigate 的规则靠同一段代码保证相同。
// 导航判定由调用方给：服务窗口按 origin，外壳窗口按 isShellPageUrl。
function guardedWindow({ partition, prefs, options, allowNavigation }) {
  const userSession = session.fromPartition(partition);
  userSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  userSession.setPermissionCheckHandler(() => false);
  const win = new BrowserWindow({ ...options, webPreferences: prefs });
  const contents = win.webContents;
  contents.setWindowOpenHandler(() => ({ action: "deny" }));
  contents.on("will-navigate", (event, url) => {
    if (!allowNavigation(url)) {
      event.preventDefault();
    }
  });
  return win;
}

// 外壳页分支：用 themis-shell://app/ 加载 desktop/web/dist 的产物，打开首次启动页（此时显示的是桩数据）。
// 页面调 startService(repo) 之后由这里起真服务：握手成功先开服务窗口、再关外壳页窗口。
// 服务在 running 期间自己退出时回到服务状态页：同一个外壳进程里能第二次起服务。
async function runShellPage() {
  // 单实例：同一 userData 只开一份。拿不到锁就在建任何窗口、起任何子进程之前以 0 退出
  if (!app.requestSingleInstanceLock()) {
    app.exit(0);
    return;
  }
  // 拿到锁：第二份被拉起时聚焦还活着的那一个窗口（优先服务窗口，其次外壳页窗口），先 restore 再 focus
  app.on("second-instance", () => {
    const target =
      serviceWindow !== null && !serviceWindow.isDestroyed()
        ? serviceWindow
        : shellWin !== null && !shellWin.isDestroyed()
          ? shellWin
          : null;
    if (target !== null) {
      if (target.isMinimized()) target.restore();
      target.focus();
    }
  });
  const root = path.join(__dirname, "..", "web", "dist");
  if (!fs.existsSync(path.join(root, "index.html"))) {
    process.stderr.write(`ERROR: 找不到外壳页产物 index.html：${path.join(root, "index.html")}\n`);
    app.exit(1);
    return;
  }
  const store = createSettingsStore({ dir: app.getPath("userData") });
  // 启动时只读这一次设置，交给 createShellApi 当内存初值（页面首帧前就能拿到已保存的外观）；
  // 主进程另持一份当前外观，初值取自已读出的设置，之后只在 onAppearanceChange 回调里更新
  const initialSettings = store.load().settings;
  let currentAppearance = appearanceOf(initialSettings);
  // 宿主 IPC 只在这里注册一次：调用经 relay 转给当前服务实例的 host。
  // 同一个进程里第二次起服务不再重复注册——同一通道第二次 handle 会抛错
  const relay = createHostRelay();
  registerHostIpc(ipcMain, relay.host, relay.senderAllowed);
  // 当前外壳页窗口：外壳 IPC、选择框与服务状态事件都读它；换页（首次启动页 / 服务状态页）时换成新的
  let shellWin = null;
  // 设置外壳窗口：只此一个，由宿主接口的 openSettings() 经 createSettingsWindow 开出；关掉它不停服务、不退应用
  let settingsWin = null;
  // 外壳页窗口是不是外壳自己关的：起服务成功与意外退出换页那两次由我们主动关，那时应用不退
  let closedByShell = false;
  // 用户关掉当前外壳窗口时才兑现：外壳自己关的窗口不兑现，接着等下一个外壳窗口
  let userClosedShell;
  const shellClosedByUser = new Promise((resolve) => {
    userClosedShell = resolve;
  });
  let shellTracked = null;
  let serviceWindow = null;
  // 服务自己退出那条路已经在收尾：服务窗口的 closed 不用再收一次服务。
  // 按 run 记：新服务窗口开起来就复位（onRunning 里），收尾回调再比对当前 serviceWindow 是不是自己
  // 那一个窗口——重启之后旧窗口迟到的 closed 被身份检查挡掉，不会误停新 run 的服务、也不会误退出
  let serviceGone = false;
  // 仓库操作（listRepos/selectRepo）：createShellApi 建好时经 onRepoOps 同步交出来，切换编排与宿主注入都读它
  let repoOps = null;

  // 宿主外观同步读取：只认当前服务窗口的 webContents（窗口为 null 或已销毁一律不认），
  // 来源被认才答当前外观对象，其余路径（来源不认、读出错）一律回 null。
  ipcMain.on(HOST_APPEARANCE_CHANNEL, (event) => {
    event.returnValue = null;
    try {
      if (serviceWindow !== null && !serviceWindow.isDestroyed() && event.sender === serviceWindow.webContents) {
        event.returnValue = currentAppearance;
      }
    } catch {
      event.returnValue = null;
    }
  });
  // 外壳外观同步读取：只认当前外壳页窗口或设置窗口的 webContents（窗口为 null 或已销毁不认），
  // 来源被认才答当前外观对象，其余路径一律回 null。
  ipcMain.on(SHELL_APPEARANCE_CHANNEL, (event) => {
    event.returnValue = null;
    try {
      if (
        (shellWin !== null && !shellWin.isDestroyed() && event.sender === shellWin.webContents) ||
        (settingsWin !== null && !settingsWin.isDestroyed() && event.sender === settingsWin.webContents)
      ) {
        event.returnValue = currentAppearance;
      }
    } catch {
      event.returnValue = null;
    }
  });

  // 外壳页窗口的底层建窗：新分区、在该 session 上注册一次协议 handler、用 shell-preload 建窗。
  // 这个 helper 定义在 runShellPage 内部：root 是 runShellPage 的局部变量，这里闭包能直接用。
  function createShellPageWindow(title) {
    const partition = partitionName();
    const userSession = session.fromPartition(partition);
    userSession.protocol.handle("themis-shell", (request) => {
      const resolved = resolveShellAsset(root, request.url);
      return new Response(resolved.body, { status: resolved.status, headers: resolved.headers });
    });
    return guardedWindow({
      partition,
      prefs: mainWebPreferences(partition, path.join(__dirname, "shell-preload.js")),
      options: { title, backgroundColor: backgroundFor(currentAppearance.theme, nativeTheme.shouldUseDarkColors) },
      allowNavigation: isShellPageUrl,
    });
  }

  // 外壳窗口统一走这里：每次取新分区、只在它自己的 session 上注册一次协议 handler。
  // 注册在模块级 protocol 上会 ERR_FAILED；同一个 session 上注册第二次会抛错
  // （Failed to register protocol: themis-shell），所以每开一次窗都现取 partitionName()
  async function openShellWindow(url) {
    const opened = createShellPageWindow("ThemisTally");
    shellWin = opened;
    closedByShell = false;
    const tracked = await trackWindow(opened, () => opened.webContents.loadURL(url));
    tracked.closed.then(() => {
      // 只看当前这一个外壳窗口：被换掉的旧窗口什么时候退都不管
      if (shellTracked !== tracked || closedByShell) return;
      userClosedShell();
    });
    shellTracked = tracked;
    return tracked;
  }

  // 设置窗口：只此一个。标题「设置」；页面加载后 ServiceApp 会把 document.title 设成
  // 「设置 · Themis Tally」，那会盖掉窗口标题——在这个窗口上拦 page-title-updated 并
  // preventDefault，窗口标题保持「设置」（站主 2026-11-19 实测：拦了之后构造时、加载完、
  // 1.5 秒后 getTitle() 都是「设置」，页面里的 document.title 照改）。
  function createSettingsWindow() {
    const opened = createShellPageWindow("设置");
    opened.webContents.on("page-title-updated", (event) => {
      event.preventDefault();
    });
    settingsWin = opened;
    opened.once("closed", () => {
      if (settingsWin === opened) settingsWin = null;
      // 关掉设置窗口：应用不退出、服务不停，焦点回到服务窗口
      if (serviceWindow !== null && !serviceWindow.isDestroyed()) serviceWindow.focus();
    });
    return opened;
  }

  // 握手成功后开服务窗口：控制令牌只经 onRunning 的实参进 createHost 的闭包，不进状态、不进事件
  const flow = createServiceFlow({
    onRunning: async ({ origin, control, repo, bootstrap }) => {
      // createHost 要的是仓库路径，控制器那边只有仓库 id：路径按 id 从设置里查回来
      const settings = store.load().settings;
      const entry = settings.repos.find((item) => item.id === repo) || null;
      const host = createHost({
        origin,
        control,
        repo: entry === null ? repo : entry.path,
        loadMain: async (url) => {
          if (serviceWindow === null || serviceWindow.isDestroyed()) return;
          await serviceWindow.webContents.loadURL(url);
        },
        createSecretWindow: ({ origin: pageOrigin }) => {
          // 凭据窗口另取一个内存分区，用不带 preload 的十键设置：它只装服务给的一次性 HTML 表单
          const credentialPartition = partitionName();
          return guardedWindow({
            partition: credentialPartition,
            allowNavigation: (url) => isServiceUrl(url, pageOrigin),
            prefs: webPreferences(credentialPartition),
            options: { parent: serviceWindow, width: 560, height: 480, title: "录入凭据" },
          });
        },
        createSettingsWindow: () => createSettingsWindow(),
        confirmExternal: async (url) => {
          const result = await dialog.showMessageBox(serviceWindow, {
            type: "question",
            buttons: ["打开", "取消"],
            defaultId: 1,
            cancelId: 1,
            message: "在系统浏览器中打开？",
            detail: url,
            noLink: true,
          });
          return result.response === 0;
        },
        openExternal: async (url) => {
          await shell.openExternal(url);
        },
        showItem: (fullPath) => {
          shell.showItemInFolder(fullPath);
        },
        showNotification: ({ title, body }) => {
          new Notification({ title, body }).show();
        },
        // 保存主题：走既有 saveSettings（写盘成功且外观变了会触发广播），再把结果转成 saveTheme 的信封
        saveTheme: async (pref) => {
          const result = await api.saveSettings({ theme: pref });
          if (result.ok !== true) return { ok: false, reason: result.reason };
          return { ok: true, value: { theme: result.value.settings.theme, density: result.value.settings.density } };
        },
        // 仓库三函数（T064）：listRepos 带正在跑的服务的仓库 id；switchRepo 走切换编排；addRepo 先拆外壳信封再交 host 映射
        listRepos: async () => {
          if (repoOps === null) return { ok: false, reason: "unavailable" };
          return { ok: true, repos: await repoOps.listRepos(repo) };
        },
        switchRepo: async (id) => {
          if (repoOps === null) return { ok: false, reason: "unavailable" };
          return switchRepoEntry(id, repo);
        },
        addRepo: async () => {
          const result = await api.pickRepo();
          // 先拆外壳信封：成功回内层 value（四种形状交给 host.js 映射），失败原样回 {ok:false, reason}
          if (result.ok === true) return result.value;
          return result;
        },
      });
      // 来源检查：只有服务窗口、且它当前显示的确实是服务 origin 下的页面，才准调宿主接口
      const senderAllowed = (event) => {
        const frame = event.senderFrame;
        if (serviceWindow === null || event.sender !== serviceWindow.webContents) return false;
        if (frame === null || frame === undefined) return false;
        return isServiceUrl(frame.url, origin);
      };
      // 当前服务实例的 host 挂进 relay：宿主 IPC 只注册一次，调用转给当前 host
      relay.use(host, senderAllowed);

      // 窗口次序：先建服务窗口，再关外壳页窗口——Electron 关掉最后一个窗口时会自己退出
      const servicePartition = partitionName();
      const opened = guardedWindow({
        partition: servicePartition,
        prefs: mainWebPreferences(servicePartition, path.join(__dirname, "preload.js")),
        options: { backgroundColor: backgroundFor(currentAppearance.theme, nativeTheme.shouldUseDarkColors) },
        allowNavigation: (url) => isServiceUrl(url, origin),
      });
      serviceWindow = opened;
      // 新 run 的服务窗口：复位「已收尾」——上一个 run 意外退出置的位不继承到这一 run
      serviceGone = false;
      let tracked;
      try {
        tracked = await trackWindow(opened, () => opened.webContents.loadURL(bootstrap));
      } catch {
        if (!opened.isDestroyed()) opened.close();
        throw new Error("服务窗口加载失败");
      }
      closedByShell = true;
      if (shellWin !== null && !shellWin.isDestroyed()) shellWin.close();

      // 用户关掉服务窗口就结束服务：以 0 退出才让应用以 0 退出（与带参数那条路同一套规则）
      tracked.closed.then(async () => {
        // 只看当前这一个服务窗口：重启之后旧窗口迟到的 closed 不改新 run 的状态、不触退出码
        if (serviceWindow !== opened) return;
        // 外壳自己关的（意外退出换页的收尾）：不收第二次
        if (serviceGone) return;
        // 服务窗口没了，设置窗口跟着关：关完最后一个窗口应用才退出，退出码规则照旧
        if (settingsWin !== null && !settingsWin.isDestroyed()) settingsWin.close();
        const stop = await flow.stop();
        if (stop.exited && stop.code === 0) {
          app.exit(0);
          return;
        }
        process.stderr.write("ERROR: 服务没有以 0 正常退出\n");
        app.exit(1);
      });
    },
  });
  // 状态一变就发给当前外壳页窗口：只发 state 这一个实参，窗口为空或已销毁就跳过
  flow.subscribe((state, info) => {
    if (shellWin !== null && !shellWin.isDestroyed()) shellWin.webContents.send(SERVICE_STATE_CHANNEL, state);
    // 服务在 running 期间自己退出（不是外壳停的）→ 回服务状态页显示退出码。
    // 「是不是外壳自己结束的」看 info.byShell，不看退出码：外部杀掉的 1 与自己退出的 1 分不出来
    if (state.kind !== "exited" || info.byShell || serviceWindow === null) return;
    serviceGone = true;
    // 已经有外壳窗口开着（服务状态页）：不另开窗口，外壳页自己经事件显示错误
    if (shellWin !== null && !shellWin.isDestroyed()) {
      relay.clear();
      // 设置窗口跟着关：换页的间隙两个旧窗口都收掉，新页面已经在另一个外壳窗口里
      if (settingsWin !== null && !settingsWin.isDestroyed()) settingsWin.close();
      if (!serviceWindow.isDestroyed()) serviceWindow.close();
      return;
    }
    openShellWindow(SHELL_STATUS_URL).then(
      () => {
        // 窗口次序：先建新窗口，再关服务窗口——任何时刻都不出现零窗口
        relay.clear();
        // 新页面开好之后才关设置窗口与服务窗口
        if (settingsWin !== null && !settingsWin.isDestroyed()) settingsWin.close();
        if (!serviceWindow.isDestroyed()) serviceWindow.close();
      },
      () => {
        // 服务状态页开不出来：写一行 ERROR 并以 1 退出
        process.stderr.write(`ERROR: 服务意外退出（退出码 ${state.exitCode}）\n`);
        // 这里没有新窗口顶上，关窗次序照旧：先关设置窗口、再关服务窗口、最后退出
        if (settingsWin !== null && !settingsWin.isDestroyed()) settingsWin.close();
        if (!serviceWindow.isDestroyed()) serviceWindow.close();
        app.exit(1);
      },
    );
  });

  // 切换仓库的编排（独立函数，不进订阅回调、不进服务窗口收尾）：先存盘，成功了才动窗口与服务。
  // 校验或存盘失败原样回、什么都不动；存盘过了立刻回 {ok:true}，收尾在后台跑、自己接住错误
  async function switchRepoEntry(id, runningId) {
    const result = await repoOps.selectRepo(id, runningId, Date.now());
    if (result.ok !== true) return result;
    // 记下旧服务窗口：收尾关的是这一个，不读之后会被清掉的 serviceWindow 变量
    const previousServiceWindow = serviceWindow;
    relay.clear();
    serviceWindow = null;
    // 后台收尾：不等它，先回 {ok:true}。次序固定 stop → reset → 开首次启动页 → 关设置窗口与旧服务窗口
    (async () => {
      try {
        await flow.stop();
      } catch {
        // 收服务失败也继续收尾：不影响已经回给调用方的 {ok:true}
      }
      flow.reset();
      try {
        await openShellWindow(SHELL_START_URL);
      } catch {
        // 切换后首次启动页开不出来：写一行 ERROR 并以 1 退出
        process.stderr.write("ERROR: 切换仓库后首次启动页开不出来\n");
        app.exit(1);
        return;
      }
      if (settingsWin !== null && !settingsWin.isDestroyed()) settingsWin.close();
      if (previousServiceWindow !== null && !previousServiceWindow.isDestroyed()) previousServiceWindow.close();
    })().catch(() => {});
    return { ok: true };
  }

  // 选择框与外部链接确认框挂在当前外壳窗口上
  const api = createShellApi({
    store,
    initialSettings,
    // 建好时同步交出 {listRepos, selectRepo}：切换编排与宿主注入都经 repoOps 调它们
    onRepoOps: (handed) => {
      repoOps = handed;
    },
    service: flow,
    assets: root,
    // 外观变化：更新主进程持有的当前外观，并当场广播给还开着的窗口——服务窗口收宿主事件，
    // 外壳页窗口与设置窗口各收外壳事件；每个窗口发之前自己判 isDestroyed()
    onAppearanceChange: (appearance) => {
      currentAppearance = appearance;
      if (serviceWindow !== null && !serviceWindow.isDestroyed()) serviceWindow.webContents.send(HOST_APPEARANCE_EVENT, appearance);
      if (shellWin !== null && !shellWin.isDestroyed()) shellWin.webContents.send(SHELL_APPEARANCE_EVENT, appearance);
      if (settingsWin !== null && !settingsWin.isDestroyed()) settingsWin.webContents.send(SHELL_APPEARANCE_EVENT, appearance);
    },
    chooseDirectory: async ({ title }) => {
      const options = { title, properties: ["openDirectory"] };
      // 父窗口依次取 shellWin → settingsWin → serviceWindow；都不在就不带窗口调用
      const owner =
        shellWin !== null && !shellWin.isDestroyed()
          ? shellWin
          : settingsWin !== null && !settingsWin.isDestroyed()
            ? settingsWin
            : serviceWindow !== null && !serviceWindow.isDestroyed()
              ? serviceWindow
              : null;
      const result = owner === null ? await dialog.showOpenDialog(options) : await dialog.showOpenDialog(owner, options);
      if (result.canceled || result.filePaths.length === 0) return null;
      return result.filePaths[0];
    },
    chooseFile: async ({ title }) => {
      const options = { title, properties: ["openFile"] };
      // 当前外壳窗口不在（换页的间隙）就退到设置窗口；两个都不在就不带窗口调用
      const owner =
        shellWin !== null && !shellWin.isDestroyed()
          ? shellWin
          : settingsWin !== null && !settingsWin.isDestroyed()
            ? settingsWin
            : null;
      const result = owner === null ? await dialog.showOpenDialog(options) : await dialog.showOpenDialog(owner, options);
      if (result.canceled || result.filePaths.length === 0) return null;
      return result.filePaths[0];
    },
    confirmExternal: async (url) => {
      const options = {
        type: "question",
        buttons: ["打开", "取消"],
        defaultId: 1,
        cancelId: 1,
        message: "在系统浏览器中打开？",
        detail: url,
        noLink: true,
      };
      // 当前外壳窗口不在（换页的间隙）就退到设置窗口；两个都不在就不带窗口调用
      const owner =
        shellWin !== null && !shellWin.isDestroyed()
          ? shellWin
          : settingsWin !== null && !settingsWin.isDestroyed()
            ? settingsWin
            : null;
      const result = owner === null ? await dialog.showMessageBox(options) : await dialog.showMessageBox(owner, options);
      return result.response === 0;
    },
    openExternal: async (url) => {
      await shell.openExternal(url);
    },
    appVersion: app.getVersion(),
  });
  registerShellIpc(ipcMain, api, (event) => {
    // 来源检查读当前外壳窗口；设置窗口开着时也放行（设置窗口里的外壳接口照外壳页窗口的规则）
    if (shellWin !== null && !shellWin.isDestroyed() && shellSenderAllowed(event, shellWin.webContents)) return true;
    if (settingsWin !== null && !settingsWin.isDestroyed() && shellSenderAllowed(event, settingsWin.webContents)) return true;
    return false;
  });
  await openShellWindow(SHELL_START_URL);
  await shellClosedByUser;
  // 外壳页是用户关的：starting 期间先中止子进程（子进程真的退出，不留僵尸），再退出
  const state = flow.state();
  if (state.kind === "starting") await flow.abort();
  else if (state.kind === "running") await flow.stop();
  app.exit(0);
}

app.whenReady().then(async () => {
  const argv = app.isPackaged ? process.argv.slice(1) : process.argv.slice(2);
  if (launchMode(argv) === "shell") {
    await runShellPage();
    return;
  }

  const partition = partitionName();
  const preloadPath = path.join(__dirname, "preload.js");
  let mainWindow = null;
  let serviceOrigin = null;

  // 带参数起服务分支没有设置存储：宿主外观同步读取恒答 null（来源不认也是 null）
  ipcMain.on(HOST_APPEARANCE_CHANNEL, (event) => {
    event.returnValue = null;
    try {
      // 这条分支没有设置存储，没有可读的外观
      event.returnValue = null;
    } catch {
      event.returnValue = null;
    }
  });

  // 来源检查：只有主窗口、且它当前显示的确实是服务 origin 下的页面，才准调宿主接口
  const senderAllowed = (event) => {
    const frame = event.senderFrame;
    if (mainWindow === null || event.sender !== mainWindow.webContents) return false;
    if (frame === null || frame === undefined) return false;
    return isServiceUrl(frame.url, serviceOrigin);
  };

  const openWindow = async ({ bootstrap, origin }) => {
    serviceOrigin = origin;
    const win = guardedWindow({
      partition,
      allowNavigation: (url) => isServiceUrl(url, origin),
      prefs: mainWebPreferences(partition, preloadPath),
      options: { backgroundColor: backgroundFor("dark", nativeTheme.shouldUseDarkColors) },
    });
    mainWindow = win;
    return trackWindow(win, () => win.webContents.loadURL(bootstrap));
  };

  // 控制令牌只经这里进主进程，之后只在 createHost 的闭包里，不进任何页面
  const onServiceReady = ({ origin, control, repo }) => {
    serviceOrigin = origin;
    const host = createHost({
      origin,
      control,
      repo,
      loadMain: async (bootstrap) => {
        await mainWindow.webContents.loadURL(bootstrap);
      },
      createSecretWindow: ({ origin: pageOrigin }) => {
        // 凭据窗口另取一个内存分区，用不带 preload 的十键设置：它只装服务给的一次性 HTML 表单
        const credentialPartition = partitionName();
        return guardedWindow({
          partition: credentialPartition,
          allowNavigation: (url) => isServiceUrl(url, pageOrigin),
          prefs: webPreferences(credentialPartition),
          options: { parent: mainWindow, width: 560, height: 480, title: "录入凭据" },
        });
      },
      confirmExternal: async (url) => {
        const result = await dialog.showMessageBox(mainWindow, {
          type: "question",
          buttons: ["打开", "取消"],
          defaultId: 1,
          cancelId: 1,
          message: "在系统浏览器中打开？",
          detail: url,
          noLink: true,
        });
        return result.response === 0;
      },
      openExternal: async (url) => {
        await shell.openExternal(url);
      },
      showItem: (fullPath) => {
        shell.showItemInFolder(fullPath);
      },
      showNotification: ({ title, body }) => {
        new Notification({ title, body }).show();
      },
    });
    registerHostIpc(ipcMain, host, senderAllowed);
  };

  const code = await runShell({
    argv,
    io: { stdout: process.stdout, stderr: process.stderr },
    openWindow,
    onServiceReady,
    env: process.env,
  });
  app.exit(code);
});
