// 契约测试不看这台机器上线用的 QUIZS_*（协调人走 quizs 之后设在用户级环境变量里，第 145 轮）：要用的场景在请求里自己带。
// 不清掉的话，探针继承它们，名册里的协调人在重放时会真的去找 Quizs 与证书，结果随机器、随证书到没到期而变（第 148 轮）。
for (const name of ["QUIZS_CMD", "QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION"]) delete process.env[name];
