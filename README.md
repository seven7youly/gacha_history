# 抽卡记录查询插件 (xhh_gacha)

抓包通用版抽卡记录查询插件。通过你在 App 中抓包得到的接口，查询抽卡记录与统计。

> 早期版本曾依赖小黑盒（xiaoheihe.cn）旧接口，但该接口已下线（返回 404），现改为通用的「抓包配置」模式。

## 功能

- `/xhh 绑定 <凭证>` — 绑定你的个人凭证（抓包请求里属于你的值，如 authkey / token / cookie）
- `/xhh 解绑` — 解绑凭证
- `/xhh 记录 [游戏ID]` — 查询抽卡记录
- `/xhh 统计 [游戏ID]` — 统计抽卡数据
- `/xhh 帮助` — 查看帮助

## 安装

1. 将 `xhh_gacha` 目录放入 AstrBot 的 `plugins/` 目录
2. 在 WebUI 中启用插件
3. 在插件的「配置」弹窗中填入抓包得到的接口 URL 和请求头（配置项定义见 `_conf_schema.json`）

## 抓包步骤（以 TapTap App 为例）

1. 电脑安装代理软件：**HTTP Toolkit** / **Charles** / **Fiddler**，并让手机连接该代理（需安装证书）
2. 手机打开 TapTap App → 进入游戏的「工具箱 → 抽卡记录」，打开你的抽卡记录页面
3. 在代理软件里过滤出页面加载时的网络请求，找到**返回抽卡数据的那一条**（响应是 JSON、且包含 `records` / `list` / 物品名称等字段）
4. 复制该请求的 **URL** 和 **请求头**（Referer、Cookie、token 等）

## 配置方法

| 配置项 | 说明 |
|-------|------|
| `api_list_gacha_url` | 抓包得到的接口 URL。支持占位符：`{token}` `{game_id}` `{limit}` `{offset}` |
| `headers_json` | 抓包得到的请求头（JSON 格式）。支持占位符：`{token}` |
| `game_names` | 游戏ID → 显示名称的映射（JSON 格式） |
| `default_game_id` | 默认查询的游戏 ID |
| `limit` | 单次请求最大条数 |

**关键：把请求中属于你个人的值替换成 `{token}` 占位符**，这样每个用户用 `/xhh 绑定 <凭证>` 绑定自己的值后，插件会自动替换。

### 示例

抓到的 URL：
```
https://api.taptap.cn/webapiv2/gacha/records?uid=123456&page_size=20&authkey=ABC123XYZ
```

其中 `authkey=ABC123XYZ` 是个人凭证，改为：
```
https://api.taptap.cn/webapiv2/gacha/records?uid=123456&page_size={limit}&authkey={token}
```

抓到的请求头（JSON）：
```json
{
  "User-Agent": "Mozilla/5.0 ...",
  "Cookie": "session=ABC123XYZ"
}
```
若 Cookie 中的值属于个人，可改为 `"Cookie": "session={token}"`。

配置完成后，用户发送 `/xhh 绑定 <自己的authkey>`，再 `/xhh 记录` 即可。

## 解析逻辑说明

插件会尝试从响应中提取记录列表（兼容 `records` / `list` / `data.records` / `result.records` 等常见结构），再解析常见字段（名称、稀有度、卡池、时间）。如果解析失败，会原样输出响应 JSON 前 3000 字符，方便你对照调整。

## 隐私说明

- 用户绑定的凭证仅存储在本地的 AstrBot 数据库中
- 凭证只会被发送到你配置的接口地址
