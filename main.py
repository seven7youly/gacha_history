from __future__ import annotations

import aiohttp
import json
import uuid
from typing import Optional

from astrbot.api.all import *


# 内置游戏名称表（可在插件配置中通过 game_names 覆盖）
DEFAULT_GAME_NAMES = {
    "1": "异环",
}

# 内置游戏对应的 TapTap 战绩 app_id（可在配置中通过 game_app_ids 覆盖）
DEFAULT_GAME_APP_IDS = {
    "1": 714119,  # 异环
}

# 异环角色绑定页（战绩页）
DEFAULT_POSTER_URL = "https://www.taptap.cn/poster/NIYXlFahOXHR"

GACHA_SUMMARY_URL = "https://www.taptap.cn/webapiv2/game-record/v1/gacha-record-summary"


class XhhPlugin(Star):
    """TapTap 战绩抽卡记录查询插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context, config)
        self.config = config or {}
        # 每次运行随机生成一个 web 端 UUID，用于构造 X-UA
        self._ua_uuid = str(uuid.uuid4())

    async def initialize(self):
        """插件初始化"""
        logger.info("TapTap 抽卡记录查询插件已加载!")

    @command_group("xhh")
    def xhh(self):
        """TapTap 战绩抽卡记录查询"""
        pass

    def _game_names(self) -> dict:
        raw = self.config.get("game_names", "")
        parsed = self._try_json_dict(raw)
        if parsed:
            return {str(k): str(v) for k, v in parsed.items()}
        return dict(DEFAULT_GAME_NAMES)

    def _game_app_ids(self) -> dict:
        raw = self.config.get("game_app_ids", "")
        parsed = self._try_json_dict(raw)
        if parsed:
            return {str(k): v for k, v in parsed.items()}
        return dict(DEFAULT_GAME_APP_IDS)

    def _poster_url(self) -> str:
        return str(self.config.get("poster_url", DEFAULT_POSTER_URL)).strip() or DEFAULT_POSTER_URL

    @staticmethod
    def _try_json_dict(raw) -> dict | None:
        if isinstance(raw, dict) and raw:
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed:
                    return parsed
            except Exception:
                pass
        return None

    def _game_hint(self) -> str:
        return " ".join(f"{k}={v}" for k, v in self._game_names().items())

    def _make_xua(self) -> str:
        """构造 TapTap 网页端 X-UA 签名串（需再经 URL 编码放入查询参数）"""
        parts = {
            "V": "1",
            "PN": "WebActivity",
            "VN_CODE": "1",
            "LANG": "zh-CN",
            "LOC": "CN",
            "PLT": "PC",
            "DS": "web",
            "UID": self._ua_uuid,
            "DT": "PC",
            "OS": "Windows",
            "OSV": "10.0",
        }
        return "&".join(f"{k}={v}" for k, v in parts.items())

    def _headers(self, xua: str) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-CLIENT-XUA": xua,
            "x-requested-with": "XMLHttpRequest",
            "Accept": "application/json, text/plain, */*",
        }

    @xhh.command("绑定角色")
    async def bind_role(self, event: AstrMessageEvent, user_id: str):
        """绑定 TapTap 角色
        用法: /xhh 绑定角色 <TapTap user_id>
        获取 user_id: 登录 https://accounts.taptap.cn/personal-info 查看
        绑定异环角色: 打开战绩页并绑定角色后即可查询
        """
        user_id = user_id.strip()
        if not user_id:
            yield event.plain_result(
                "⚠️ 请提供你的 TapTap user_id。\n"
                "获取方式：登录 https://accounts.taptap.cn/personal-info 查看 user_id。"
            )
            return

        await self.put_kv_data(f"xhh_user_{event.get_sender_id()}", user_id)
        yield event.plain_result(
            f"✅ 已绑定 TapTap user_id：{user_id}\n"
            f"若还没绑定异环角色，请打开 {self._poster_url()} 绑定后再查询。"
        )

    @xhh.command("解绑")
    async def unbind(self, event: AstrMessageEvent):
        """解绑 TapTap 账号
        用法: /xhh 解绑
        """
        await self.delete_kv_data(f"xhh_user_{event.get_sender_id()}")
        yield event.plain_result("✅ 已解绑。")

    @xhh.command("抽卡记录")
    async def gacha_records(self, event: AstrMessageEvent, game_id: Optional[str] = None, user_id: Optional[str] = None):
        """查询抽卡记录
        用法: /xhh 抽卡记录 [游戏ID] [TapTap user_id]
        省略 user_id 时使用已绑定的账号
        """
        names = self._game_names()
        game_id = self._resolve_game_id(game_id)
        if game_id not in names:
            yield event.plain_result(f"⚠️ 未知游戏ID：{game_id}\n可选：{self._game_hint()}")
            return

        uid = (user_id or "").strip() or await self.get_kv_data(
            f"xhh_user_{event.get_sender_id()}", None
        )
        if not uid:
            yield event.plain_result("⚠️ 未绑定 TapTap 账号。\n请先输入 /xhh 绑定角色 <user_id>")
            return

        data = await self._fetch_summary(game_id, uid)
        if isinstance(data, str):
            yield event.plain_result(data)
            return

        formatted = _format_records(data)
        yield event.plain_result(f"📊 {names[game_id]} 抽卡记录：\n{formatted}")

    @xhh.command("抽卡统计")
    async def gacha_stats(self, event: AstrMessageEvent, game_id: Optional[str] = None, user_id: Optional[str] = None):
        """统计抽卡数据
        用法: /xhh 抽卡统计 [游戏ID] [TapTap user_id]
        """
        names = self._game_names()
        game_id = self._resolve_game_id(game_id)
        if game_id not in names:
            yield event.plain_result(f"⚠️ 未知游戏ID：{game_id}\n可选：{self._game_hint()}")
            return

        uid = (user_id or "").strip() or await self.get_kv_data(
            f"xhh_user_{event.get_sender_id()}", None
        )
        if not uid:
            yield event.plain_result("⚠️ 未绑定 TapTap 账号。\n请先输入 /xhh 绑定角色 <user_id>")
            return

        data = await self._fetch_summary(game_id, uid)
        if isinstance(data, str):
            yield event.plain_result(data)
            return

        formatted = _format_stats(data)
        yield event.plain_result(f"📊 {names[game_id]} 抽卡统计：\n{formatted}")

    @xhh.command("帮助")
    async def help_cmd(self, event: AstrMessageEvent):
        """查看插件帮助"""
        yield event.plain_result(
            "🎮 TapTap 抽卡记录查询插件\n"
            "┌────────────────────────────\n"
            "│ /xhh 绑定角色 <user_id> — 绑定 TapTap 账号\n"
            "│ /xhh 解绑            — 解绑\n"
            "│ /xhh 抽卡记录 [游戏ID] — 查询抽卡记录\n"
            "│ /xhh 抽卡统计 [游戏ID] — 统计抽卡数据\n"
            "└────────────────────────────\n"
            f"游戏ID: {self._game_hint()}\n"
            "\n"
            "📌 使用步骤：\n"
            "① 打开战绩页绑定异环角色: " + self._poster_url() + "\n"
            "② 获取 user_id: https://accounts.taptap.cn/personal-info\n"
            "③ 发送 /xhh 绑定角色 <user_id>\n"
            "④ 数据刷新: 回战绩页点『更新数据』按钮后重新查询"
        )

    def _resolve_game_id(self, game_id: Optional[str]) -> str:
        if game_id:
            return str(game_id).strip()
        return str(self.config.get("default_game_id", "1"))

    async def _fetch_summary(self, game_id: str, user_id: str) -> dict | str:
        """请求 TapTap 抽卡记录汇总接口
        返回解析后的数据 dict（含 summary）；失败时返回错误提示字符串
        """
        app_ids = self._game_app_ids()
        app_id = app_ids.get(game_id)
        if app_id is None:
            return "⚠️ 该游戏未配置 TapTap app_id，请在插件配置中填写 game_app_ids。"

        xua = self._make_xua()
        params = {
            "user_id": user_id,
            "app_id": app_id,
            "is_preview": "false",
            "X-UA": xua,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    GACHA_SUMMARY_URL,
                    params=params,
                    headers=self._headers(xua),
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        return f"❌ 请求失败：HTTP {resp.status}"
                    raw = await resp.json()
        except aiohttp.ClientError as e:
            return f"❌ 网络错误：{str(e)}"
        except Exception as e:
            return f"❌ 请求异常：{str(e)}"

        if not isinstance(raw, dict):
            return f"❌ 返回格式异常：{str(raw)[:200]}"
        if not raw.get("success"):
            msg = (raw.get("data") or {}).get("msg") if isinstance(raw.get("data"), dict) else None
            return f"❌ TapTap 接口返回错误：{msg or raw.get('error') or '未知错误'}"

        data = raw.get("data") or {}
        summary = data.get("summary")
        if not isinstance(summary, dict):
            return "⚠️ 返回数据中没有 summary 字段，请检查 user_id 是否正确、是否已在战绩页绑定角色。"
        return summary


def _extract_summary(data: dict) -> dict:
    return data if isinstance(data, dict) else {}


def _format_records(summary: dict) -> str:
    """格式化抽卡记录（按卡池分组展示）"""
    summary = _extract_summary(summary)
    sections = summary.get("sections") or []
    if not sections:
        return "暂无抽卡记录（若刚绑定角色，请回战绩页点击『更新数据』后再查询）"

    lines = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        banner = sec.get("banner_name") or sec.get("banner_type") or "未知卡池"
        lines.append(f"🏷️ {banner}")
        if sec.get("up_character"):
            lines.append(f"   UP: {sec['up_character']}")
        if sec.get("pity_range_text"):
            lines.append(f"   保底区间: {sec['pity_range_text']}")

        items = sec.get("items") or []
        for idx, it in enumerate(items, 1):
            if not isinstance(it, dict):
                continue
            name = it.get("item_name") or "未知物品"
            rarity = it.get("item_rarity") or it.get("item_rarity") or ""
            pity = it.get("item_count") or ""
            time_ts = it.get("pull_time") or 0
            time_str = _fmt_time(time_ts)
            line = f"   {idx}. {name} {rarity}"
            if pity:
                line += f" (第{pity}抽)"
            if time_str:
                line += f" {time_str}"
            lines.append(line)

        if sec.get("total_pull_count") is not None:
            lines.append(f"   ── 共{sec['total_pull_count']}抽, SSR {sec.get('ssr_count', '?')}个")

    if len(lines) == 0:
        return "暂无抽卡记录"
    return "\n".join(lines)


def _format_stats(summary: dict) -> str:
    """格式化抽卡统计"""
    summary = _extract_summary(summary)

    overview = summary.get("overview")
    lines = []
    if isinstance(overview, dict):
        total = overview.get("total_pull_count") or 0
        ssr = overview.get("total_ssr_count") or 0
        lines.append(f"总抽取次数: {total}")
        lines.append(f"SSR 数量: {ssr}")
        lines.append(f"SSR 出率: {ssr / total * 100:.2f}%" if total else "SSR 出率: 0%")
        if overview.get("banner_count") is not None:
            lines.append(f"卡池数量: {overview['banner_count']}")
    else:
        # 无 overview 时根据 sections 汇总
        sections = summary.get("sections") or []
        total = sum(int(s.get("total_pull_count") or 0) for s in sections if isinstance(s, dict))
        ssr = sum(int(s.get("ssr_count") or 0) for s in sections if isinstance(s, dict))
        lines.append(f"总抽取次数: {total}")
        lines.append(f"SSR 数量: {ssr}")
        lines.append(f"SSR 出率: {ssr / total * 100:.2f}%" if total else "SSR 出率: 0%")

    stats = summary.get("stats")
    if isinstance(stats, list) and stats:
        lines.append("")
        lines.append("📂 各卡池保底统计:")
        for st in stats:
            if not isinstance(st, dict):
                continue
            title = st.get("title") or st.get("key") or "卡池"
            total_pull = st.get("total_pull_count") or 0
            pity = ""
            if st.get("min_pity") is not None and st.get("max_pity") is not None:
                pity = f", 保底区间 {st['min_pity']}-{st['max_pity']}"
            lines.append(f"  {title}: {total_pull}抽, 平均保底 {st.get('avg_pity', '?')}{pity}")

    if len(lines) == 0:
        return "暂无统计数据"

    last_updated = summary.get("last_updated") or 0
    if last_updated:
        lines.append("")
        lines.append(f"🕒 数据更新于: {_fmt_time(last_updated)}")
    return "\n".join(lines)


def _fmt_time(ts) -> str:
    """时间戳转可读字符串（秒级）"""
    if not ts:
        return ""
    try:
        ts = int(ts)
        if ts > 10**12:  # 毫秒
            ts = ts // 1000
        import datetime
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""
