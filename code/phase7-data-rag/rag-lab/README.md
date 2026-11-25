# Phase 7 · 可追溯证据问答

配合[第七阶段 L60–L69](../../../lessons/0080-phase7-data-rag-outline.html)，把旧项目固定问句到政策的映射拆成「文档 → 片段 → 授权检索 → 证据包 → 回答验收」。本目录是合成语料练习，不使用真实企业资料、外部模型、密钥或联网索引。

## 从哪里开始

- [L60 行级访问](../../../lessons/0070-L60-rag-data-access.html)和[L61 可定位分块](../../../lessons/0071-L61-rag-citation-chunks.html)：SQLite 不等同 PostgreSQL RLS。L61 用固定清单将三种本地来源接到授权检索与引文回查；不是通用导入流水线。`pdftotext` 核对了两页合成 PDF，默认仍用预抽取页夹具，不覆盖 OCR 或复杂版面。
- L62–L64：共享 `lab.py` 用内存 SQLite 先筛选授权片段，再对同一个池运行词法、精确余弦和 RRF。词和向量均手工写好；没有真实分词、Embedding、ANN 索引或质量基准。
- L65–L66：重排只改同一批候选的顺序，再按预算打包；用合成变更检查热缓存失效。缓存练习不证明跨进程同步、备份擦除或任意并发下一致。
- L67–L69：区分证据与执行授权，把检索和生成验收分别记录，最后用同一组来源信息做交接。手工期望和确定性替身不代表真实模型表现。

## 复跑本地标准库用例

Pages 仅发布课文和实验说明，不附 Python 文件或夹具。先打开[可信课程源码仓库](https://github.com/Ben-play/ai-agent-learning)，获取与正在学习的课文同版本的源码（查看分支或提交），再从仓库根执行（Python 3.11+）。无需把脚本或资料上传到网站：

```bash
python -I -X utf8 code/phase7-data-rag/rag-lab/tests/test_lab.py -v
python -I -X utf8 code/phase7-data-rag/rag-lab/lifecycle/test_lifecycle.py -v
python -I -X utf8 scripts/check-course-examples.py --suite rag
```

自检只运行课程白名单内片段，不会安装或启动数据库与第三方依赖。各课同时给出可见的起始输入、反例与核对标准；只看到成功标记不足以解释为什么通过。

## 读取契约

宿主注入 `(tenant, user)`，SQLite 查询按租户和授予记录选出可见片段。`search()` 只对这些片段排名；`source()` 按当前权限与精确 `(doc_id, version, locator)` 查找，不把旧引用偷偷指到新版。同一定位键在不同租户可以指向不同记录，跨租户缓存必须额外绑定作用域。`epoch` 是当前实验连接上的粗失效标记，不是分布式版本时钟。

词法基线只算手工词项重合数，向量基线只比较固定三维向量，写入时验证维度和有限性；RRF 融合两个授权候选排名而不是混加两种原始分。先固定语料、权威答案和权限，再比较是否见到所需信息；不拿本例耗时推断生产性能。

## 查看实测对照与交接行

```bash
python -I -X utf8 code/phase7-data-rag/rag-lab/compare_retrieval.py
python -I -X utf8 code/phase7-data-rag/rag-lab/lifecycle/main.py --timing
python -I -X utf8 code/phase7-data-rag/rag-lab/assessment/stage.py --report
```

前两条分开比较 L64 检索和 L65 重排的本机耗时；耗时不是通过条件。最后一条把 L69 的召回缺口、打包缺口、正确值支持度和答复验收分别显示，避免用一个成功标记代替交接。
