# 桌面宠物 Python 版

这是一个直接在 Windows 桌面运行的独立桌宠，不需要浏览器。现在有两套入口：

- `pet_app.py`：新版 PySide6 工程入口，适合继续做成熟功能和后续打包。
- `desktop_pet.py`：纯标准库备用入口，不依赖第三方库。

## 安装依赖

先创建并安装虚拟环境依赖：

```text
install-deps.bat
```

如果要完全复现这次配置好的环境，可以改用：

```text
.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
```

如果网络安装暂时不可用，仍然可以跑备用版：

```text
run-legacy.bat
```

## 运行

安装依赖后双击 `run-pet.bat`，或运行：

```text
.venv\Scripts\python.exe pet_app.py
```

以后打包独立软件可以从这里开始：

```text
build-app.bat
```

## 代码结构

新版 PySide6 入口仍然保留在 `pet_app.py`，但主要代码已经拆到 `pet/` 包里：

```text
pet/
  config.py          # 路径、外部命令和运行配置
  model.py           # 宠物状态、主题、神态和物理更新
  qt_app.py          # Qt 应用启动、自检和冒烟测试
  single_instance.py # 单实例锁
  utils.py           # 通用文本、颜色和数值工具
  agent/             # Agent 会话、RPC 进程和面板状态
  ui/                # 宠物窗口、控制面板、Agent 工作台和通用按钮
```

`desktop_pet.py` 仍然是纯标准库备用入口，尽量保持独立，主线功能优先放在 `pet/` 包内维护。

## 已保留的功能

- 自动 / 手动神态：待机、开心、兴奋、好奇、调皮、紧绷、思考、安宁、困倦、惊讶
- 8 套配色主题
- 真实时间、手动时间、加速一天的昼夜节律
- 系统繁忙度滑杆
- 打字感知：会监听键盘输入，也可以在控制台文本框里打字
- 左键拖动、点一下戳它、身上来回划抚摸
- 声音开关
- 专注过久后的深呼吸陪伴

## 操作

- 左键拖动宠物：移动桌宠
- 左键点一下：戳它
- 鼠标在宠物身上来回划：抚摸它
- 右键宠物：打开宠物控制台
- 控制台里的“隐藏”只隐藏控制台，不关闭宠物
