"use strict";

// 宿主接口的中转：registerHostIpc 只注册一次，调用转给当前服务实例的 host。
// 每个服务实例的 host 都是新闭包（控制令牌只在那里面），同一个外壳进程里第二次起服务时
// 不能重复注册 IPC——Electron 对同一通道第二次 handle 会抛错——只把当前指针换成新的。
// 纯模块，不 require electron：接线在 main.js，这里只做替换与兜底。
const HOST_METHODS = ["reauth", "openSecretWindow", "openExternal", "reveal", "notify"];

function createHostRelay() {
  let host = null;
  let senderAllowed = null;

  const relayed = {};
  for (const name of HOST_METHODS) {
    relayed[name] = async (...args) => {
      // 没有当前 host（服务还没起来、或已经收尾）→ forbidden，不抛错
      if (host === null) return { ok: false, reason: "forbidden" };
      return host[name](...args);
    };
  }

  return {
    host: relayed,
    senderAllowed: (event) => {
      if (host === null || senderAllowed === null) return false;
      try {
        return senderAllowed(event);
      } catch {
        // 来源检查自己抛错按不通过：绝不把异常抛给 invoke 的处理器
        return false;
      }
    },
    // 换服务实例：替换而不是叠加，旧 host 从此不再被调
    use: (nextHost, nextSenderAllowed) => {
      host = nextHost;
      senderAllowed = nextSenderAllowed;
    },
    // 服务窗口被外壳关掉：丢掉当前 host 与来源检查，回到「没有当前 host」
    clear: () => {
      host = null;
      senderAllowed = null;
    },
  };
}

module.exports = { createHostRelay, HOST_METHODS };
