# RPG Maker Viewer

一个基于 Python 标准库的 RPG Maker 地图与数据查看器。  
可在浏览器中查看地图、事件、图鉴、技能机制和导出文本攻略，不需要打开 RPG Maker 编辑器。

支持多游戏管理（历史游戏库）、MV/MZ 资源解密缓存、VX/VX Ace 数据读取与基础地图渲染。

---

## 1. 当前功能总览

### 1.1 游戏库管理
- 支持注册多个游戏并持久化到 `games_registry.json`。
- 每个游戏记录以下信息：
  - 名称（可改名）
  - 封面（可选，本地路径或 URL）
  - EXE 路径
  - Data 路径
  - 引擎类型（`mv` / `vx` / `vxace`）
  - 添加时间、更新时间
- 支持：
  - 设为当前游戏
  - 删除游戏
  - 路径可用性检测（路径失效会在列表标记）

### 1.2 地图浏览与渲染
- 地图树浏览（层级结构 + 地图名搜索）。
- 地图画布支持：
  - 鼠标拖拽平移
  - 滚轮/按钮缩放
  - 事件类型标记（宝箱/传送/战斗/对话/其他）
- 异步渲染能力：
  - 地图背景（视差图）异步加载
  - 瓦片材质异步加载后叠加绘制
  - 事件第一页角色帧异步绘制到地图
- 通行度叠层（目前仅 MV/MZ 启用）。

### 1.3 事件解析与详情面板
- 事件页解析：触发条件、出现条件、指令文本。
- 事件页可折叠/展开。
- 指令内容区滚轮独立滚动，不会带动整个右侧面板。
- 指令中的引用可点击跳转/联动：
  - 物品、武器、防具、技能、怪物
  - 传送目标地图
  - 敌群与遇敌信息

### 1.4 多窗口浮动详情
- 物品/怪物/技能等详情使用浮动窗口展示。
- 支持同时打开多个窗口。
- 支持拖拽移动（窗口标题栏拖拽）。
- 每个窗口独立关闭。
- 敌群/遇敌详情保持在右侧详情区内联展示（不弹窗）。

### 1.5 图鉴系统（武器/防具/物品/技能/怪物）
- 分类浏览 + 分类内搜索。
- 图标异步加载（IconSet）。
- 怪物可显示大图（存在素材时）。
- 技能详情支持：
  - 基础属性（范围、命中、消耗、成功率等）
  - MV 公式原文与可读化说明
  - VX 旧版技能机制字段（legacy damage）
- 提供“刷新图鉴”按钮，缓存会按“当前游戏 + 更新时间”自动失效。

### 1.6 搜索模式（已分离）
- 地图界面顶部搜索：执行全图事件指令搜索。
- 图鉴界面顶部搜索：仅筛选当前图鉴分类。

### 1.7 导出
- 支持导出当前地图或全部地图为 Markdown 文本攻略。

### 1.8 MV/MZ 资源解密缓存
- 注册 MV 游戏时自动扫描加密资源：
  - `.rpgmvp` `.rpgmvm` `.rpgmvo`
  - `.png_` `.m4a_` `.ogg_`
- 优先用 Python 内建解密（读取 `System.json` 的 `encryptionKey`）。
- Python 失败时可自动回退 Java 解密器（若检测到 JAR）。
- 输出缓存目录：`<游戏根目录>/data_cache/decrypted/`
- 当前不支持 `nw.pak` 通用解包。

---

## 2. 支持的游戏类型

- RPG Maker MV / MZ
  - `www/data/MapInfos.json` 或 `data/MapInfos.json`
- RPG Maker VX Ace
  - `Data/*.rvdata2` 或 `Game.rgss3a`
- RPG Maker VX
  - `Data/*.rvdata` 或 `Game.rgss2a` / `Game.rgssad`

---

## 3. 环境要求

- Python 3.10+
- Windows 下推荐使用 `game_tool.bat`
- Java（可选，仅用于 MV/MZ 资源解密回退）

不依赖第三方 Python 包（项目包含必要的本地 vendored 解析代码）。

---

## 4. 快速开始

### 4.1 方式 A（推荐，Windows）

使用 `game_tool.bat`：

- 直接双击：启动 Viewer
- 拖拽一个或多个 `*.exe` 到 bat：批量注册游戏

`game_tool.bat` 会先做数据标记检测，识别成功才会调用：

```bash
python rpgmv_viewer.py --register-exe "<exe_path>"
```

> 说明：仓库当前使用 `game_tool.bat`，它就是“启动 + 拖拽注册”合并入口。

### 4.2 方式 B（命令行）

启动服务：

```bash
python3 rpgmv_viewer.py
```

注册游戏：

```bash
python3 rpgmv_viewer.py --register-exe "D:\\Games\\MyGame\\Game.exe"
```

---

## 5. 命令行参数

`rpgmv_viewer.py` 支持：

- `--register-exe <path>`
  - 注册游戏并退出（供 bat 或脚本调用）
- `--name <display_name>`
  - 注册时指定显示名（可选）
- `--no-activate`
  - 注册后不切换为当前游戏
- `--no-browser`
  - 启动服务时不自动打开浏览器

---

## 6. Web API（当前版本）

### 6.1 游戏库
- `GET /api/games`
  - 返回游戏列表、当前活动游戏、可用性标记、warning 信息
- `POST /api/games/register-exe`
  - 注册游戏
- `POST /api/games/pick-exe`
  - 由后端弹系统文件选择框选择 EXE
- `POST /api/games/select`
  - 切换当前游戏
- `PATCH /api/games/<id>`
  - 更新名称/封面
- `DELETE /api/games/<id>`
  - 删除游戏

### 6.2 地图与数据
- `GET /api/tree`
- `GET /api/map/<id>`
- `GET /api/search?q=<keyword>`
- `GET /api/common_event/<id>`
- `GET /api/encyclopedia`
- `GET /api/export?map=<id>`
- `GET /api/export?all=1`

### 6.3 资产与封面
- `GET /api/assets/meta`
  - 返回图标集信息（路径、规格）
- `GET /api/assets/file?rel=<relative_path>`
  - 按相对路径读取资产（有路径安全校验）
- `GET /api/cover?path=<absolute_or_saved_path>`
  - 读取游戏封面

---

## 7. 游戏库文件说明

默认文件：`games_registry.json`

结构示例：

```json
{
  "version": 1,
  "active_game_id": "uuid",
  "games": []
}
```

损坏恢复策略：
- 如果 JSON 损坏，会自动备份为：
  - `games_registry.broken.<timestamp>.json`
- 然后自动重建空注册表，服务继续可用。

---

## 8. 资源解密（MV/MZ）补充说明

### 8.1 Python 内建解密
- 读取 `System.json` 中 `encryptionKey`
- 处理加密资源头与前 16 字节 XOR
- 写入 `data_cache/decrypted`

### 8.2 Java 回退
- 自动寻找 JAR：
  1. 环境变量 `RPGMV_JAVA_DECRYPTER_JAR`
  2. `Java-RPG-Maker-MV-Decrypter-master/**/target/*.jar`
- 调用命令：

```bash
java -jar <jar> decrypt <game_root> <output_dir> false true auto
```

### 8.3 已知限制
- 仅支持资源解密，不支持 `nw.pak` 通用解包。

---

## 9. 当前已知兼容性说明

- VX/VX Ace 地图渲染已接入，但与 MV 的瓦片规则并非完全相同。
- 通行度覆盖层仅在 MV/MZ 下计算与显示。
- 当素材缺失时，前端会显示占位或状态提示，不会让服务崩溃。

---

## 10. 项目结构（核心）

```text
RPGMaker-MV-Viewer/
  rpgmv_viewer.py
  game_tool.bat
  games_registry.json
  viewer/
    app_state.py
    game_registry.py
    game_discovery.py
    data_loader.py
    vx_adapter.py
    rgss_archive.py
    mv_mz_resource_unpack.py
    java_mv_decrypter.py
    assets.py
    database.py
    interpreter.py
    encyclopedia.py
    exporter.py
    server.py
    static/
      index.html
      app.js
      styles.css
  tests/
```

---

## 11. 常见问题排查

### 11.1 拖拽 EXE 后提示不支持
检查游戏目录是否存在下列任一标记：
- `www/data/MapInfos.json`
- `data/MapInfos.json`
- `Data/MapInfos.rvdata2` / `Data/Map*.rvdata2`
- `Data/MapInfos.rvdata` / `Data/Map*.rvdata`
- `Game.rgss3a` / `Game.rgss2a` / `Game.rgssad`

### 11.2 图鉴或地图显示旧数据
- 点击图鉴“刷新”
- 或重新切换一次当前游戏（会触发缓存失效）

### 11.3 MV/MZ 资源解密失败
- 确认 `System.json` 存在且有合法 `encryptionKey`
- 若 Python 路径失败，可安装 Java 并提供可用解密 JAR

### 11.4 游戏路径失效
- 在“管理游戏库”中会标记“路径失效”
- 需要重新注册或修正路径

---

## 12. 测试

运行全部单元测试：

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## 13. 免责声明

本项目仅用于学习、研究、数据分析与攻略整理。  
请勿用于侵犯版权、非法传播或其他违法用途。

