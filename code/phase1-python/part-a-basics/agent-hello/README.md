# agent-hello

L01/L02 的课程起步项目。从本目录运行（Python 3.11+）：

```shell
python -X utf8 main.py
```

预期输出：`Message(role='assistant', content='你说的是：Hello Agent!')`。

`main.run()` 从公开包入口 `agent` 导入并调用 `create_response`，打印返回的 `Message`。`agent/core.py` 通过 `from .schemas import Message` 相对导入同包的数据模型。`agent/config.py` 目前是空占位文件，不加载配置。

这个入口不需要 API Key、第三方库或网络。若项目的 pytest 已准备好，可以从本目录运行 `python -m pytest -q` 检查内部模块。
