from __future__ import annotations

import aiohttp
import json
from typing import Optional

from astrbot.api.all import *


# 内置游戏名称表（可在插件配置中通过 game_names 覆盖）
DEFAULT_GAME_NAMES = {
    "1": "原神",
    "2": "崩坏：星穹铁道",
    "3": "绝区零",
    "4": "异环",
    "5": "无限暖暖",
}


class XhhPlugin(Star):
    """抽卡记录查询插件（抓包通用版）"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context, config)
        self.config = config or {}

    async def initialize(self):
        """插件初始化"""
        logger.info("抽卡记录查询插件已加载!")

    @command_group("xhh")
    def xhh(self):
        """抽卡记录查询插件"""
        pass

    def _game_names(self) -> dict:
        raw = self.config.get("game_names", "")
        if isinstance(raw, dict) and raw:
            return {str(k): str(v) for k, v in raw.items()}
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed:
                    return {str(k): str(v) for k, v in parsed.items()}
            except Exception:
                pass
        return dict(DEFAULT_GAME_NAMES)

    def _game_hint(self) -> str:
        return " ".join(f"{k}={v}" for k, v in self._game_names().items())

    @xhh.command("绑定")
    async def bind(self, event: AstrMessageEvent, token: str):
        """绑定抓包凭证（token/cookie 等）
        用法: /xhh 绑定 <凭证>
        凭证 = 抓包请求中属于你个人的那个值，如 authkey、token、cookie
        """
        token = token.strip()
        if not token:
            yield event.plain_result(
                "⚠️ 请提供你的抓包凭证。\n"
                "获取方式：抓包后，把请求里属于你个人的值（如 authkey、token、cookie）复制给我。"
            )
            return

        await self.put_kv_data(f"xhh_token_{event.get_sender_id()}", token)
        yield event.plain_result("✅ 绑定成功！\n输入 /xhh 记录 查看抽卡记录。")

    @xhh.command("解绑")
    async def unbind(self, event: AstrMessageEvent):
        """解绑账号
        用法: /xhh 解绑
        """
        await self.delete_kv_data(f"xhh_token_{event.get_sender_id()}")
        yield event.plain_result("✅ 已解绑。")

    @xhh.command("记录")
    async def gacha_records(self, event: AstrMessageEvent, game_id: Optional[str] = None):
        """查询抽卡记录
        用法: /xhh 记录 [游戏ID]
        """
        names = self._game_names()
        game_id = self._resolve_game_id(game_id)
        if game_id not in names:
            yield event.plain_result(f"⚠️ 未知游戏ID：{game_id}\n可选：{self._game_hint()}")
            return

        token = await self.get_kv_data(f"xhh_token_{event.get_sender_id()}", None)
        if not token:
            yield event.plain_result("⚠️ 你还没有绑定凭证。\n请先输入 /xhh 绑定 <凭证>")
            return

        data = await self._fetch(game_id, token, offset=0)
        if isinstance(data, str):
            yield event.plain_result(data)
            return

        formatted = _format_records(data)
        if formatted.startswith("{"):
            yield event.plain_result(
                f"📊 {names[game_id]} 抽卡记录\n{json.dumps(data, ensure_ascii=False, indent=2)[:3000]}"
            )
        else:
            yield event.plain_result(f"📊 {names[game_id]} 抽卡记录：\n{formatted}")

    @xhh.command("统计")
    async def gacha_stats(self, event: AstrMessageEvent, game_id: Optional[str] = None):
        """统计抽卡数据
        用法: /xhh 统计 [游戏ID]
        """
        names = self._game_names()
        game_id = self._resolve_game_id(game_id)
        if game_id not in names:
            yield event.plain_result(f"⚠️ 未知游戏ID：{game_id}\n可选：{self._game_hint()}")
            return

        token = await self.get_kv_data(f"xhh_token_{event.get_sender_id()}", None)
        if not token:
            yield event.plain_result("⚠️ 你还没有绑定凭证。\n请先输入 /xhh 绑定 <凭证>")
            return

        data = await self._fetch(game_id, token, offset=0)
        if isinstance(data, str):
            yield event.plain_result(data)
            return

        stats = _format_stats(data)
        if stats.startswith("{"):
            yield event.plain_result(
                f"📊 {names[game_id]} 抽卡统计\n{json.dumps(data, ensure_ascii=False, indent=2)[:3000]}"
            )
        else:
            yield event.plain_result(f"📊 {names[game_id]} 抽卡统计：\n{stats}")

    @xhh.command("帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        """查看插件帮助"""
        yield event.plain_result(
            "🎮 抽卡记录查询插件（抓包版）\n"
            "┌────────────────────────────\n"
            "│ /xhh 绑定 <凭证>   — 绑定个人凭证\n"
            "│ /xhh 解绑         — 解绑\n"
            "│ /xhh 记录 [游戏ID] — 查询抽卡记录\n"
            "│ /xhh 统计 [游戏ID] — 统计抽卡数据\n"
            "└────────────────────────────\n"
            f"游戏ID: {self._game_hint()}\n"
            "\n"
            "📌 使用前需在插件配置中填写抓包得到的接口 URL 和请求头，\n"
            "并在 URL/请求头中用 {token} 标记个人凭证的位置。"
        )

    def _resolve_game_id(self, game_id: Optional[str]) -> str:
        """解析游戏 ID，未指定时使用配置中的默认值"""
        if game_id:
            return str(game_id).strip()
        return str(self.config.get("default_game_id", "1"))

    async def _fetch(self, game_id: str, token: str, offset: int = 0) -> dict | str:
        """请求抓包接口
        URL 模板支持占位符：{token} {game_id} {limit} {offset}
        请求头支持占位符：{token}
        返回解析后的数据 dict；失败时返回错误提示字符串
        """
        api_url = str(self.config.get("api_list_gacha_url", "")).strip()
        if not api_url:
            return "⚠️ 未配置接口地址。请在插件配置中填写 api_list_gacha_url（抓包得到的 URL）。"

        limit = self.config.get("limit", 50)
        url = (
            api_url.replace("{token}", token)
            .replace("{game_id}", game_id)
            .replace("{limit}", str(limit))
            .replace("{offset}", str(offset))
        )

        headers = {}
        try:
            raw = self.config.get("headers_json", "{}")
            headers = json.loads(raw) if raw else {}
        except Exception:
            headers = {}
        headers = {str(k): str(v).replace("{token}", token) for k, v in headers.items()}
        headers.setdefault("Accept", "application/json")
        headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
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
    if isinstance(data.get("result"), dict):
        d = data["result"]
        if isinstance(d.get("records"), list):
            return d["records"]
        if isinstance(d.get("list"), list):
            return d["list"]
    return None
