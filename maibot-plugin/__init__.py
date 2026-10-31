"""maimai_bridge：麦麦 × DeepSeek Harness 桥。

这个文件让插件目录成为一个 Python 包，``plugin.py`` 里的相对导入
（``from .config import ...``）才有意义。

PluginLoader 实际上是这么加载的：

.. code-block:: python

    spec = importlib.util.spec_from_file_location(
        module_name, str(plugin_path),
        submodule_search_locations=[str(plugin_dir)],
    )

``submodule_search_locations`` 让 ``plugin.py`` 具备包的语义，所以相对导入
可用；这里再放一个 ``__init__.py``，是为了让静态检查工具、本地离线测试
（``import maimai_bridge.plugin``）也能按包正确解析。
"""
