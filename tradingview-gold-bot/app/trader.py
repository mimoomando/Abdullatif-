"""
ما يُفعل بالإشارة بعد فهمها.

هنا يلتقي كل شيء: حارس التكرار، وحدود الأمان، وحساب الوقف والهدف
من سعر التنفيذ الفعلي، ثم أمر الوسيط. وكل قرار يُسجَّل بسببه، فإن
لم تُفتح صفقة عُرف لماذا بالضبط.
"""

import logging

from app import risk
from app.brokers.base import BrokerError
from app.dedupe import Dedupe
from app.signals import (BUY, CLOSE, ENTRY_KINDS, SELL, SL_HIT, TP1, TP2, TP3,
                         TP_ANY)

log = logging.getLogger("bridge.trader")


class Trader:
    def __init__(self, settings, broker, notifier=None, dedupe=None):
        self.settings = settings
        self.broker = broker
        self.notifier = notifier
        self.dedupe = dedupe or Dedupe()

    # ── المدخل ──

    def handle(self, signal):
        if not self.settings.enabled:
            return self._skip(signal, "البريدج موقوف: ENABLED=false")

        if not self.dedupe.check_and_add(signal.fingerprint()):
            return self._skip(signal, "تنبيه مكرر وصل مرة أخرى")

        if signal.kind in ENTRY_KINDS:
            return self._open(signal)
        if signal.kind in (TP1, TP_ANY):
            return self._on_first_target(signal)
        if signal.kind == TP2:
            return self._protect(signal, "بلغ الهدف الثاني")
        if signal.kind == TP3:
            return self._close_all(signal, "بلغ الهدف الثالث")
        if signal.kind == SL_HIT:
            return self._on_stop(signal)
        if signal.kind == CLOSE:
            return self._close_all(signal, "أمر إغلاق")
        return self._skip(signal, f"نوع لا يُدار: {signal.kind}")

    # ── فتح الصفقة ──

    def _open(self, signal):
        settings = self.settings
        symbol = settings.broker_symbol(signal.ticker)
        side = risk.side_of(signal)

        # الوسيط الورقي لا سوق له: نعطيه سعر التنبيه ليحاكي التنفيذ
        if hasattr(self.broker, "set_price") and signal.entry:
            self.broker.set_price(symbol, signal.entry)

        risk.check_distance(
            signal.risk_distance, settings.min_stop_distance, settings.max_stop_distance
        )

        info = self.broker.symbol_info(symbol)
        open_positions = self.broker.positions(symbol=symbol, magic=settings.magic)

        same_side = [p for p in open_positions if p.side == side]
        if same_side:
            return self._skip(signal, f"صفقة {side} مفتوحة أصلاً على {symbol}")

        against = [p for p in open_positions if p.side != side]
        if against:
            if not settings.reverse_on_opposite:
                return self._skip(signal, "صفقة معاكسة مفتوحة و REVERSE_ON_OPPOSITE=false")
            for position in against:
                self.broker.close(position)
                log.info("أُغلقت الصفقة المعاكسة %s قبل عكس الاتجاه", position.ticket)
            open_positions = self.broker.positions(symbol=symbol, magic=settings.magic)

        if len(open_positions) >= settings.max_open_positions:
            return self._skip(
                signal,
                f"بلغ حد الصفقات المفتوحة ({settings.max_open_positions})",
            )

        lot = self._lot_for(signal, info)
        money = risk.check_money_at_risk(
            signal.risk_distance, lot, info.value_per_price_unit, settings.max_risk_usd
        )

        reward = risk.pick_reward_distance(signal, settings.target_tp)
        estimate = info.entry_price(side)
        sl_estimate, tp_estimate = risk.stop_and_target(
            side, estimate, signal.risk_distance, reward,
            digits=info.digits, broker_min_distance=info.stops_distance,
        )

        # الوقف يُرسل مع الأمر لا بعده: لحظة واحدة بلا وقف مخاطرة
        # لا داعي لها. ثم يُصحَّح على سعر التنفيذ الحقيقي.
        position = self.broker.market_order(
            symbol, side, lot,
            sl=sl_estimate, tp=tp_estimate,
            comment=f"TV {signal.kind}",
            magic=settings.magic,
        )

        corrected = self._correct_after_fill(position, signal, info, reward)

        summary = {
            "status": "opened",
            "kind": signal.kind,
            "symbol": symbol,
            "side": side,
            "lot": lot,
            "ticket": position.ticket,
            "fill": position.price_open,
            "sl": corrected["sl"],
            "tp": corrected["tp"],
            "risk_distance": round(signal.risk_distance, info.digits),
            "risk_usd": round(money, 2),
            "corrected": corrected["changed"],
        }
        self._announce(
            f"فُتحت صفقة {('شراء' if side == 'buy' else 'بيع')} على {symbol}\n"
            f"الحجم {lot} · التنفيذ {position.price_open}\n"
            f"الوقف {corrected['sl']} · الهدف {corrected['tp'] or 'بلا'}\n"
            f"الخسارة عند الوقف {money:.2f} دولاراً"
        )
        log.info("فُتحت صفقة: %s", summary)
        return summary

    def _correct_after_fill(self, position, signal, info, reward):
        """
        الوقف والهدف يُقاسان من سعر التنفيذ الفعلي.

        بين إرسال التنبيه وتنفيذه يتحرك الذهب، وقد يزيد الانزلاق.
        فما أُرسل مع الأمر كان تقديراً على السعر المعروض، وهنا
        يُصحَّح ليصير بُعد الوقف هو بُعد المؤشر بالضبط.
        """
        sl, tp = risk.stop_and_target(
            position.side, position.price_open, signal.risk_distance, reward,
            digits=info.digits, broker_min_distance=info.stops_distance,
        )
        tolerance = max(info.point, 10 ** -info.digits)
        needs = (abs((position.sl or 0.0) - sl) > tolerance
                 or (tp and abs((position.tp or 0.0) - tp) > tolerance))
        if not needs:
            return {"sl": position.sl, "tp": position.tp or None, "changed": False}
        try:
            updated = self.broker.modify(position, sl=sl, tp=tp)
            return {"sl": updated.sl, "tp": updated.tp or None, "changed": True}
        except BrokerError as exc:
            # الصفقة مفتوحة ومحمية بوقف التقدير: نُبقيها ونُخبر
            log.warning("تعذّر تصحيح الوقف بعد التنفيذ: %s", exc)
            self._announce(f"⚠️ تعذّر تصحيح وقف الصفقة {position.ticket}: {exc}")
            return {"sl": position.sl, "tp": position.tp or None, "changed": False}

    def _lot_for(self, signal, info):
        settings = self.settings
        if settings.risk_percent > 0:
            lot = risk.lot_for_risk(
                self.broker.balance(), settings.risk_percent, signal.risk_distance,
                info.value_per_price_unit,
                volume_step=info.volume_step,
                volume_min=info.volume_min,
                volume_max=min(info.volume_max, settings.max_lot),
            )
        else:
            lot = settings.lot
        lot = risk.normalize_lot(
            lot,
            volume_step=info.volume_step,
            volume_min=info.volume_min,
            volume_max=min(info.volume_max, settings.max_lot),
        )
        return lot

    # ── إدارة الصفقة بعد فتحها ──

    def _positions_of(self, signal):
        symbol = self.settings.broker_symbol(signal.ticker)
        return symbol, self.broker.positions(symbol=symbol, magic=self.settings.magic)

    def _on_first_target(self, signal):
        settings = self.settings
        symbol, positions = self._positions_of(signal)
        if not positions:
            return self._skip(signal, f"بلغ الهدف الأول ولا صفقة مفتوحة على {symbol}")

        info = self.broker.symbol_info(symbol)
        acted = []
        for position in positions:
            if settings.tp1_close_percent > 0:
                part = risk.normalize_lot(
                    position.volume * settings.tp1_close_percent / 100.0,
                    volume_step=info.volume_step,
                    volume_min=info.volume_min,
                    volume_max=position.volume,
                )
                if part < position.volume:
                    self.broker.close(position, volume=part)
                    acted.append(f"أُغلق {part} من {position.ticket}")
                    position = self.broker.positions(symbol=symbol, magic=settings.magic)
                    position = position[0] if position else None
                    if position is None:
                        continue

            if settings.tp1_move_to_breakeven:
                stop = risk.breakeven_stop(position.side, position.price_open, info.digits)
                self.broker.modify(position, sl=stop)
                acted.append(f"نُقل وقف {position.ticket} إلى الدخول {stop}")

        summary = {"status": "managed", "kind": signal.kind, "symbol": symbol,
                   "actions": acted}
        if acted:
            self._announce("بلغ الهدف الأول:\n" + "\n".join(acted))
        log.info("إدارة عند الهدف الأول: %s", summary)
        return summary

    def _protect(self, signal, reason):
        """تأمين الصفقة بنقل وقفها إلى الدخول إن لم يكن هناك."""
        symbol, positions = self._positions_of(signal)
        if not positions:
            return self._skip(signal, f"{reason} ولا صفقة مفتوحة على {symbol}")

        info = self.broker.symbol_info(symbol)
        acted = []
        for position in positions:
            stop = risk.breakeven_stop(position.side, position.price_open, info.digits)
            already = (position.is_buy and position.sl >= stop) or \
                      (not position.is_buy and 0 < position.sl <= stop)
            if already:
                continue
            self.broker.modify(position, sl=stop)
            acted.append(f"نُقل وقف {position.ticket} إلى {stop}")

        if acted:
            self._announce(f"{reason}:\n" + "\n".join(acted))
        return {"status": "managed", "kind": signal.kind, "symbol": symbol,
                "actions": acted}

    def _close_all(self, signal, reason):
        symbol, positions = self._positions_of(signal)
        if not positions:
            return self._skip(signal, f"{reason} ولا صفقة مفتوحة على {symbol}")
        closed = []
        for position in positions:
            self.broker.close(position)
            closed.append(position.ticket)
        self._announce(f"{reason}: أُغلقت الصفقات {closed}")
        log.info("%s: أُغلقت %s", reason, closed)
        return {"status": "closed", "kind": signal.kind, "symbol": symbol,
                "tickets": closed}

    def _on_stop(self, signal):
        """
        تنبيه ضرب الوقف.

        وقف الوسيط أسرع من أي تنبيه، فالصفقة مغلقة غالباً قبل وصوله.
        وإن بقيت مفتوحة — لأن سعر جست ماركتس تخلّف عن سعر الشارت —
        فهذه شبكة الأمان الأخيرة.
        """
        symbol, positions = self._positions_of(signal)
        if not positions:
            return {"status": "noop", "kind": signal.kind, "symbol": symbol,
                    "reason": "ضُرب الوقف والصفقة مغلقة أصلاً"}
        return self._close_all(signal, "تنبيه ضرب الوقف والصفقة ما زالت مفتوحة")

    # ── أدوات ──

    def _skip(self, signal, reason):
        log.info("لم تُنفَّذ [%s]: %s", signal.kind, reason)
        return {"status": "skipped", "kind": signal.kind, "reason": reason}

    def _announce(self, text):
        prefix = "🧪 تجريبي\n" if self.settings.dry_run else ""
        if self.notifier:
            self.notifier.send(prefix + text)
