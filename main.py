from __future__ import annotations

import aiohttp
import json
from typing import Optional

from astrbot.api.all import *


# 小黑盒游戏代码表 (game_id 可根据实际抓包调整)
GAME_NAMES = {
    "1": "原神",
    "2": "崩坏：星穹铁道",
    "3": "绝区零",
    "4": "异环",
    "5": "无限暖暖",
}

GAME_HINT = "1=原神 2=崩铁 3=绝区零 4=异环 5=无限暖暖"


class XhhPlugin(Star):
    """小黑盒抽卡记录查询插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context, config)
        self.config = config or {}

    async def initialize(self):
        """插件初始化"""
        logger.info("小黑盒抽卡记录查询插件已加载!")

    @command_group("xhh")
    def xhh(self):
        """小黑盒抽卡记录查询插件"""
        pass

    @xhh.command("绑定")
    async def bind(self, event: AstrMessageEvent, token: str):
        """绑定小黑盒 user_pkey
        用法: /xhh 绑定 <user_pkey>
        获取方式: 登录小黑盒网页版 xiaoheihe.cn，F12 → Cookie → 找到 user_pkey
        """
        token = token.strip()
        if not token:
            yield event.plain_result(
                "⚠️ 请提供你的 user_pkey。\n"
                "获取方式：登录小黑盒网页版，按 F12 打开开发者工具，\n"
                "在 Application/存储/Cookie 中找到 user_pkey 的值。"
            )
            return

        await self.put_kv_data(f"xhh_pkey_{event.get_sender_id()}", token)
        yield event.plain_result("✅ 小黑盒账号绑定成功！\n输入 /xhh 记录 查看抽卡记录。")

    @xhh.command("解绑")
    async def unbind(self, event: AstrMessageEvent):
        """解绑小黑盒账号
        用法: /xhh 解绑
        """
        await self.delete_kv_data(f"xhh_pkey_{event.get_sender_id()}")
        yield event.plain_result("✅ 已解绑小黑盒账号。")

    @xhh.command("记录")
    async def gacha_records(self, event: AstrMessageEvent, game_id: Optional[str] = None):
        """查询抽卡记录
        用法: /xhh 记录 [游戏ID]  (1=原神 2=崩铁 3=绝区零 4=异环 5=无限暖暖)
        """
        game_id = self._resolve_game_id(game_id)
        if game_id not in GAME_NAMES:
            yield event.plain_result(f"⚠️ 未知游戏ID：{game_id}\n可选值：{GAME_HINT}")
            return

        pkey = await self.get_kv_data(f"xhh_pkey_{event.get_sender_id()}", None)
        if not pkey:
            yield event.plain_result("⚠️ 你还没有绑定小黑盒账号。\n请先输入 /xhh 绑定 <你的user_pkey>")
            return

        data = await self._fetch_records(game_id, pkey)
        if isinstance(data, str):
            yield event.plain_result(data)
            return

        formatted = _format_records(data)
        if formatted.startswith("{"):
            yield event.plain_result(
                f"📊 {GAME_NAMES[game_id]} 抽卡记录\n{json.dumps(data, ensure_ascii=False, indent=2)[:3000]}"
            )
        else:
            yield event.plain_result(f"📊 {GAME_NAMES[game_id]} 抽卡记录：\n{formatted}")

    @xhh.command("统计")
    async def gacha_stats(self, event: AstrMessageEvent, game_id: Optional[str] = None):
        """统计抽卡数据
        用法: /xhh 统计 [游戏ID]  (1=原神 2=崩铁 3=绝区零 4=异环 5=无限暖暖)
        """
        game_id = self._resolve_game_id(game_id)
        if game_id not in GAME_NAMES:
            yield event.plain_result(f"⚠️ 未知游戏ID：{game_id}\n可选值：{GAME_HINT}")
            return

        pkey = await self.get_kv_data(f"xhh_pkey_{event.get_sender_id()}", None)
        if not pkey:
            yield event.plain_result("⚠️ 你还没有绑定小黑盒账号。\n请先输入 /xhh 绑定 <你的user_pkey>")
            return

        data = await self._fetch_records(game_id, pkey)
        if isinstance(data, str):
            yield event.plain_result(data)
            return

        stats = _format_stats(data)
        if stats.startswith("{"):
            yield event.plain_result(
                f"📊 {GAME_NAMES[game_id]} 抽卡统计\n{json.dumps(data, ensure_ascii=False, indent=2)[:3000]}"
            )
        else:
            yield event.plain_result(f"📊 {GAME_NAMES[game_id]} 抽卡统计：\n{stats}")

    @xhh.command("帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        """查看插件帮助"""
        yield event.plain_result(
            "🎮 小黑盒抽卡记录查询插件\n"
            "┌────────────────────────────\n"
            "│ /xhh 绑定 <user_pkey>  — 绑定小黑盒账号\n"
            "│ /xhh 解绑            — 解绑账号\n"
            "│ /xhh 记录 [游戏ID]    — 查询抽卡记录\n"
            "│ /xhh 统计 [游戏ID]    — 统计抽卡数据\n"
            "└────────────────────────────\n"
            f"游戏ID: {GAME_HINT}\n"
            "\n"
            "📌 user_pkey 获取方式：\n"
            "登录小黑盒网页版 xiaoheihe.cn，按 F12 打开开发者工具，\n"
            "在 Application/存储/Cookie 中找到 user_pkey 的值。"
        )

    def _resolve_game_id(self, game_id: Optional[str]) -> str:
        """解析游戏 ID，未指定时使用配置中的默认值"""
        if game_id:
            return str(game_id).strip()
        return str(self.config.get("default_game_id", "4"))

    async def _fetch_records(self, game_id: str, pkey: str) -> dict | str:
        """请求抽卡记录接口
        返回解析后的数据 dict；失败时返回错误提示字符串
        """
        api_url = self.config.get(
            "api_list_gacha_url",
            "https://api.xiaoheihe.cn/gacha/app/get_records",
        )
        limit = self.config.get("limit", 50)

        params = {
            "game_id": game_id,
            "limit": limit,
            "offset": 0,
        }

        headers = {}
        try:
            headers = json.loads(self.config.get("headers_json", "{}"))
        except Exception:
            pass

        headers.setdefault("Accept", "application/json")
        headers.setdefault("Content-Type", "application/json")

        # 认证头：根据配置决定使用方式
        if self.config.get("use_pkey_as_auth", False):
            headers["Authorization"] = pkey
        else:
            headers["x-user-token"] = pkey
        headers["x-user-pkey"] = pkey

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    api_url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return f"❌ 请求失败：HTTP {resp.status}"
                    return await resp.json()
        except aiohttp.ClientError as e:
            return f"❌ 网络错误：{str(e)}"
        except Exception as e:
            return f"❌ 请求异常：{str(e)}"


def _format_records(data: dict) -> str:
    """解析抽卡记录数据并格式化输出
    返回格式化文本；如果无法解析则返回原始 JSON 字符串
    """
    try:
        records = _extract_records(data)

        if records is None:
            return json.dumps(data, ensure_ascii=False)

        lines = []
        for i, rec in enumerate(records[-10:], 1):  # 只显示最近的10条
            if not isinstance(rec, dict):
                continue
            # 尝试常见字段名
            name = rec.get("name") or rec.get("item_name") or rec.get("goods_name") or "未知物品"
            rank = rec.get("rank") or rec.get("rarity") or rec.get("quality") or ""
            pool = rec.get("pool_name") or rec.get("pool") or rec.get("card_pool") or ""
            time_str = rec.get("time") or rec.get("create_time") or rec.get("gacha_time") or ""

            rank_display = ""
            if rank:
                try:
                    r = int(rank)
                    rank_display = "⭐" * r
                except (ValueError, TypeError):
                    rank_display = str(rank)

            line = f"{i}. {name} {rank_display}"
            if pool:
                line += f" [{pool}]"
            if time_str:
                line += f" ({str(time_str)[:16]})"
            lines.append(line)

        if not lines:
            return "暂无抽卡记录"

        return "\n".join(lines)
    except Exception:
        return json.dumps(data, ensure_ascii=False)


def _format_stats(data: dict) -> str:
    """统计抽卡数据
    返回格式化文本；如果无法解析则返回原始 JSON 字符串
    """
    try:
        records = _extract_records(data)

        if records is None:
            return json.dumps(data, ensure_ascii=False)

        total = len(records)
        high_quality = 0
        pools: dict[str, int] = {}

        for rec in records:
            if not isinstance(rec, dict):
                continue
            rank = rec.get("rank") or rec.get("rarity") or rec.get("quality")
            try:
                if rank is not None and int(rank) >= 5:
                    high_quality += 1
            except (ValueError, TypeError):
                pass

            pool = rec.get("pool_name") or rec.get("pool") or rec.get("card_pool") or "未分类"
            pools[pool] = pools.get(pool, 0) + 1

        lines = [
            f"总抽取次数: {total}",
            f"五星/传说物品: {high_quality}",
            f"出率: {high_quality / total * 100:.2f}%" if total else "出率: 0%",
            "",
            "📂 卡池分布:",
        ]
        for pool, count in pools.items():
            lines.append(f"  {pool}: {count} 次")

        return "\n".join(lines)
    except Exception:
        return json.dumps(data, ensure_ascii=False)


def _extract_records(data: dict) -> list | None:
    """从接口返回数据中提取抽卡记录列表"""
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("records"), list):
        return data["records"]
    if isinstance(data.get("list"), list):
        return data["list"]
    if isinstance(data.get("data"), dict):
        d = data["data"]
        if isinstance(d.get("records"), list):
            return d["records"]
        if isinstance(d.get("list"), list):
            return d["list"]
    return None
