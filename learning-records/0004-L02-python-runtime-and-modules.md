# 0004 - L02 Python 运行机制与模块系统

**日期**: 2026-06-27
**课程**: L02 Python 运行机制与模块系统
**状态**: 完成

## 关键知识点

1. **Python 执行流程**：源代码 → 字节码（.pyc）→ PVM 执行
2. **__name__ 机制**：直接运行时为 "__main__"，被 import 时为模块名
3. **模块 vs 包**：模块 = .py 文件，包 = 含 __init__.py 的目录
4. **__init__.py 作用**：定义公开接口、控制 __all__、包级初始化
5. **import 查找顺序**：sys.modules → 内置模块 → sys.path
6. **相对导入 vs 绝对导入**：相对导入只能在包内使用，main.py 用绝对导入
7. **循环导入**：用延迟导入、提取公共模块、TYPE_CHECKING 解决
8. **__all__**：控制 from package import * 的行为

## Agent 开发关联

- Agent 项目通常是多模块结构，需要理解 import 机制
- core.py 和 tools.py 容易形成循环导入
- __init__.py 导出核心类，简化用户导入路径
- 虚拟环境改变 sys.path，影响包的查找

## 面试要点

- Python 执行流程（编译+解释）
- __name__ == "__main__" 的作用
- 循环导入的诊断和解决方案
- __all__ 的作用
- import 查找顺序
