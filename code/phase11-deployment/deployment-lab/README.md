# Phase 11 · 受控部署与持续迭代实验

配合[阶段 11 L93–L98](../../../lessons/0113-phase11-deployment-outline.html)。复用合成客服工单、离线证据及 Phase 5 的本地草稿，不接真实模型、凭证、工单或云服务。Pages 只发布说明与课件，不发 Python、数据库、镜像或报告；运行前先获取[可信课程仓库](https://github.com/Ben-play/ai-agent-learning)同版本源码。

## 标准库：本地验收

从仓库根用 Python 3.11+ 执行，不加 `-O`：

```bash
python -I -X utf8 scripts/check-course-examples.py --suite deployment
python -B -X utf8 -m unittest discover -s code/phase11-deployment/deployment-lab -v
```

- L93/95：`host.py` 是顺序宿主；`transport.py` 用真实本地父子进程与 JSON 行交换，无端口。`business.sqlite` 保存 Phase 5 checkpoint 和草稿回执，`review.sqlite` 保存完整绑定的决定与课堂撤权。Phase 7 授权证据由合成夹具和持久撤权重建，候选额外元数据不参与授权。进程退出、依赖不可用、拒绝和提交后丢回复各有独立观察；本地临时目录自动清理。
- L94/96：看实际执行的 Phase 8 门禁和冻结合成流量的控制组/候选，不以镜像标签、汇总数字或回传成功作为晋级依据。L94 的制品字节和写入 schema 2 是假设合同，与 L97 两个实际子进程共用的 SQLite schema 1 不同；L96 的故障信号也不声称来自 L97 的任务。模拟耗时不取代线上尾延迟。
- L97/98：[回滚检查点](../../../lessons/0111-L97-rollback-pending-approvals.html#stage-practice-deployment-rollback)跟踪同一候选的未确认结果、停止分发、退出和旧版接手，读取两库版本与原审批，核对无需重审和原回执的零写重放；[最终交接](../../../lessons/0112-L98-incident-evaluation-iteration.html#stage-practice-deployment-handoff)还要检查 L96 有序案组的独立指纹，以及 L98 原请求作用域和精确引文的脱敏验收。

## 可选真实 HTTP／容器演练：本环境未实跑

先准备已授权的本地 Docker 环境。下列命令只适用于个人隔离机器和新建的专用合成卷；不要绑定外部 IP、放在共享主机、用 host 网络，或接生产资源。服务没有真实认证，启动时选定的 `LAB_PROFILE` 是课堂角色；`reviewer` 容器运行期间，能访问本机端口的程序也能以这个课堂角色调用。生产应另做可信身份、独立审批、网络隔离、依赖锁定、并发与恢复验收。

从仓库根在 Bash 中构建；Dockerfile 专用 ignore 只允许列明的课程源码进入上下文。基础镜像标签和依赖范围是教学输入，不是已验证的构建物摘要或锁。每轮只创建一次卷：不传名称，由 Docker 分配新名称，保存在当前终端的 `LAB_VOLUME`。不要把这一步用于本轮的进程替换，也不要用上轮已有卷开始新一轮。

```bash
docker build -f code/phase11-deployment/deployment-lab/Dockerfile -t support-lab:p11 . &&
    LAB_VOLUME=$(docker volume create) && test -n "$LAB_VOLUME" &&
    MSYS2_ARG_CONV_EXCL='--mount=' docker run -d --name support-lab-p11 --network bridge -p 127.0.0.1:8000:8000 --mount="source=$LAB_VOLUME,target=/state" support-lab:p11
```

构建失败先停止。若未获得卷名或启动失败，不继续发送请求；检查当前容器名称、端口和卷状态。后续替换均在同一终端使用这一卷名。

新容器启动后，在支持真实 `curl` 的终端请求固定教学习题：

```bash
curl -fsS http://127.0.0.1:8000/lab/ask -H 'Content-Type: application/json' -d '{"topic":"export"}'
curl -fsS http://127.0.0.1:8000/lab/stage -H 'Content-Type: application/json' -d '{"job":"export","topic":"export","revision":1}'
```

保存返回的 `binding`，先停止并移除本轮课堂容器（不删除卷），再开同卷的故障容器。下例的 `MSYS2_ARG_CONV_EXCL` 防止 Windows Git Bash 改写挂载值内的容器路径。不要同时启动两个写入进程，不要在容器仍写入时只复制主 SQLite 文件。

```bash
test -n "$LAB_VOLUME" && docker stop support-lab-p11 && docker rm support-lab-p11 &&
    MSYS2_ARG_CONV_EXCL='--mount=' docker run -d --name support-lab-p11 --network bridge -p 127.0.0.1:8000:8000 --mount="source=$LAB_VOLUME,target=/state" -e LAB_PROFILE=reviewer -e LAB_OUTAGE=1 support-lab:p11
```

确认新进程启动后再发请求：

```bash
curl -fsS http://127.0.0.1:8000/lab/inspect -H 'Content-Type: application/json' -d '{"job":"export"}'
```

`inspect` 的 `binding` 应与原值相同。把实际绑定逐字段放到 `{ "binding": {...}, "decision": "approve" }`，以 JSON 发往 `POST /lab/review`；向 `POST /lab/recover` 发 `{ "binding": {...} }`，故障进程预期 `503`，不返回回执。再停止并移除故障容器；按同一命令重新启动，但不加 `LAB_OUTAGE=1`，仍使用当前 `LAB_VOLUME`，不要再次创建卷。用同一个绑定发送两次 `recover`，预期分别为 `saved` 与 `replayed`、原稿和回执相同。独立库读回可核对已提交行数；零次新增 INSERT 尝试还需要写入入口的观察。标准库验收有这两类证据，若容器操作只核对响应，应在报告注明。结束时停止并移除课堂容器；是否删除明确命名的合成卷由操作者另行决定。

## 真实部署前置：仍阻断

即使全套标准库和同机容器验收通过，也不能代替 [Phase 8 工程基线](../../phase8-agent-engineering/engineering-lab/README.md) 与 [L87 真实图兼容性](../../../lessons/0100-L87-migration-fallback.html#stage-practice-checkpoint-compatibility)。在获准且锁定的 Phase 6 环境中先通过原图用例，再独立验证 Phase 6 原快照和 Phase 10 应用夹具两份报告。此处没有真实晋级或生产开关。单机 SQLite、顺序进程、合成配额与模拟指标均不证明跨进程抢占、断电恢复、生产认证、多机限流或在线 p95。
