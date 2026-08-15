# TapTap 抽卡记录查询插件

通过 TapTap「战绩」公开接口，使用 **TapTap user_id** 查询异环等游戏的抽卡记录与出货统计。无需登录、无需抓包。

## 功能

- `/ck 绑定角色 <user_id>` — 绑定你的 TapTap user_id
- `/ck 解绑` — 解绑
- `/ck 抽卡记录 [游戏ID] [user_id]` — 查询抽卡记录（省略 user_id 使用已绑定账号）
- `/ck 抽卡统计 [游戏ID] [user_id]` — 统计抽卡数据
- `/ck 帮助` — 查看帮助

## 使用步骤

1. **绑定异环角色**：打开战绩页 https://www.taptap.cn/poster/NIYXlFahOXHR ，登录并绑定你的异环角色
2. **获取 TapTap user_id**：登录 https://accounts.taptap.cn/personal-info 查看
3. **绑定账号**：向机器人发送 `/ck 绑定角色 <你的user_id>`
4. **查询**：发送 `/ck 抽卡记录`
5. **刷新数据**：回到战绩页点击「更新数据」按钮后，再重新查询即可看到最新数据

## 原理

插件调用 TapTap 战绩公开接口：

```
GET https://www.taptap.cn/webapiv2/game-record/v1/gacha-record-summary
参数: user_id=<TapTap uid>  app_id=<游戏战绩app_id>  is_preview=false  X-UA=<XUA签名>
请求头: X-CLIENT-XUA  x-requested-with: XMLHttpRequest  ...
```

`X-UA` 由插件自动构造（TapTap 网页端反爬校验字段）。接口为公开只读接口，无需登录即可查询他人战绩。

> 注意：「更新数据」需要登录态，由用户在战绩页手动操作，插件只负责读取。

## 配置项说明

| 配置项 | 说明 |
|-------|------|
| `game_names` | 游戏ID → 显示名称映射（JSON），默认 `{"1":"异环"}` |
| `game_app_ids` | 游戏ID → TapTap 战绩 app_id 映射（JSON），异环为 `714119` |
| `poster_url` | 战绩页（角色绑定页）地址 |
| `default_game_id` | 默认查询的游戏 ID |

如需新增游戏，在战绩页找到该游戏的 app_id 后填入 `game_app_ids` 即可（例如 `{"1":714119,"2":<另一游戏的app_id>}`）。

## 隐私说明

- 用户绑定的 user_id 仅存储在本地的 AstrBot 数据库中
- user_id 只会发送到 TapTap 官方接口
